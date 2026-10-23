"""Getting paid: Pay now (Stripe Checkout), AutoPay (card or bank account kept at Stripe and charged
when invoices go out), payments recorded by staff, and Stripe webhooks keeping it all in sync."""
import hashlib
import logging
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core import mail
from apps.core.audit import audit
from apps.core.models import Setting
from apps.crm.models import Client

from . import stripe_api
from .models import AutoPayLink, Invoice, Payment, StripeEvent

log = logging.getLogger("weststar.payments")
OPEN = ["Sent", "Viewed", "Partial", "Overdue"]


def cents(amount) -> int:
    return int((Decimal(amount) * 100).quantize(Decimal(1)))


def autopay_on() -> bool:
    return Setting.get("autopay.enabled", "true") != "false" and stripe_api.configured()


def _int(key, default):
    try:
        return max(1, int(Setting.get(key, "") or default))
    except ValueError:
        return default


# ── Stripe customers and saved payment methods ──
def ensure_customer(client: Client) -> str:
    if client.stripe_customer_id:
        return client.stripe_customer_id
    email = client.email or next((c.email for c in client.contacts.filter(archived_at__isnull=True).exclude(email="").order_by("-is_primary")), "")
    cus = stripe_api.call("POST", "customers", {"name": client.name, "email": email or None, "metadata": {"client_id": client.pk}},
                          idempotency_key=f"ws1-customer-{client.pk}")
    Client.objects.filter(pk=client.pk).update(stripe_customer_id=cus["id"])
    client.stripe_customer_id = cus["id"]
    return cus["id"]


def save_method(client: Client, pm_id: str, by: str = "") -> None:
    """Keeps a payment method on file for AutoPay (only Stripe's id, type, brand and last 4)."""
    pm = stripe_api.call("GET", f"payment_methods/{pm_id}")
    kind = pm.get("type", "card")
    info = pm.get(kind) or {}
    brand = info.get("brand") or info.get("bank_name") or ""
    Client.objects.filter(pk=client.pk).update(
        autopay_method_id=pm_id, autopay_method_type=kind, autopay_brand=str(brand)[:30], autopay_last4=str(info.get("last4") or "")[:4],
        autopay_enabled=True, autopay_enrolled_at=timezone.now(), autopay_last_error="")
    try:
        stripe_api.call("POST", f"customers/{client.stripe_customer_id or ensure_customer(client)}",
                        {"invoice_settings": {"default_payment_method": pm_id}})
    except stripe_api.StripeError:
        pass
    # Unpaid invoices get charged on the next AutoPay run
    Invoice.objects.filter(client=client, status__in=OPEN).update(autopay_attempts=0, autopay_next_at=None, autopay_error="")
    audit(None, "autopay_on", "client", client.pk, f"AutoPay turned on for {client.name}{' by ' + by if by else ''}", area="billing")


def turn_off(client: Client, by: str = "", detach=True) -> None:
    pm = client.autopay_method_id
    Client.objects.filter(pk=client.pk).update(autopay_enabled=False, autopay_method_id="", autopay_method_type="", autopay_brand="", autopay_last4="")
    if pm and detach and stripe_api.configured():
        try:
            stripe_api.call("POST", f"payment_methods/{pm}/detach")
        except stripe_api.StripeError:
            pass
    audit(None, "autopay_off", "client", client.pk, f"AutoPay turned off for {client.name}{' by ' + by if by else ''}", area="billing")


# ── Checkout (Stripe's hosted page) ──
def checkout_pay(invoice: Invoice, success_url: str, cancel_url: str, save_for_autopay=False) -> str:
    bal = invoice.balance
    if bal <= 0:
        raise stripe_api.StripeError("This invoice is already paid.")
    cus = ensure_customer(invoice.client)
    data = {"mode": "payment", "customer": cus, "success_url": success_url + ("&" if "?" in success_url else "?") + "session={CHECKOUT_SESSION_ID}",
            "cancel_url": cancel_url, "client_reference_id": f"invoice-{invoice.pk}",
            "line_items": [{"quantity": 1, "price_data": {"currency": "usd", "unit_amount": cents(bal),
                                                          "product_data": {"name": f"Invoice {invoice.number}", "description": invoice.client.name}}}],
            "payment_intent_data": {"metadata": {"invoice_id": invoice.pk, "client_id": invoice.client_id, "autopay": "1" if save_for_autopay else "0"},
                                    "description": f"Invoice {invoice.number}"},
            "metadata": {"invoice_id": invoice.pk, "client_id": invoice.client_id, "autopay": "1" if save_for_autopay else "0"}}
    if save_for_autopay:
        data["payment_intent_data"]["setup_future_usage"] = "off_session"
    return stripe_api.call("POST", "checkout/sessions", data)["url"]


def checkout_setup(client: Client, success_url: str, cancel_url: str) -> str:
    cus = ensure_customer(client)
    return stripe_api.call("POST", "checkout/sessions", {
        "mode": "setup", "currency": "usd", "customer": cus, "client_reference_id": f"client-{client.pk}",
        "success_url": success_url + ("&" if "?" in success_url else "?") + "session={CHECKOUT_SESSION_ID}", "cancel_url": cancel_url,
        "metadata": {"client_id": client.pk, "purpose": "autopay"}, "setup_intent_data": {"metadata": {"client_id": client.pk}}})["url"]


def finish_checkout(session_id: str, expect_client: Client | None = None) -> str:
    """Called on the return page and by the webhook. Returns what happened in plain words."""
    s = stripe_api.call("GET", f"checkout/sessions/{session_id}", {"expand": ["payment_intent.latest_charge", "setup_intent"]})
    meta = s.get("metadata") or {}
    client = Client.objects.filter(pk=meta.get("client_id") or 0).first()
    if client is None or (expect_client is not None and client.pk != expect_client.pk):
        return ""
    if s.get("mode") == "setup":
        si = s.get("setup_intent") or {}
        if si.get("status") == "succeeded" and si.get("payment_method"):
            if client.autopay_method_id != si["payment_method"]:
                save_method(client, si["payment_method"], by="the client")
            return "AutoPay is on."
        return ""
    pi = s.get("payment_intent") or {}
    inv = Invoice.objects.filter(pk=meta.get("invoice_id") or 0, client=client).first()
    if not inv or not pi:
        return ""
    p = record_intent(pi, inv, "online")
    if meta.get("autopay") == "1" and pi.get("payment_method") and pi.get("status") in ("succeeded", "processing"):
        if client.autopay_method_id != pi["payment_method"]:
            save_method(client, pi["payment_method"], by="the client")
    if p and p.status == "Pending":
        return "Thanks! Your bank payment is processing. It usually clears in a few business days."
    return "Thank you — your payment went through." if p else ""


def record_intent(pi: dict, invoice: Invoice, source: str) -> Payment | None:
    """A Stripe PaymentIntent → a Payment (once). Succeeded/processing only."""
    status = {"succeeded": "Succeeded", "processing": "Pending"}.get(pi.get("status", ""))
    if not status:
        return None
    charge = pi.get("latest_charge") if isinstance(pi.get("latest_charge"), dict) else {}
    pm_types = pi.get("payment_method_types") or ["card"]
    with transaction.atomic():
        p = Payment.objects.select_for_update().filter(stripe_payment_intent=pi["id"]).first()
        if p:
            if p.status != status and p.status != "Refunded":
                p.status = status
                p.receipt_url = charge.get("receipt_url") or p.receipt_url
                p.save()
                if status == "Succeeded":
                    transaction.on_commit(lambda: send_receipt(p))
            return p
        p = Payment(client=invoice.client, invoice=invoice, amount=Decimal(pi.get("amount_received") or pi.get("amount") or 0) / 100,
                    method="Bank account (ACH)" if "us_bank_account" in pm_types and "card" not in pm_types else "Card",
                    paid_on=timezone.localdate(), reference=pi["id"], status=status, source=source, stripe_payment_intent=pi["id"],
                    receipt_url=charge.get("receipt_url") or "")
        if charge.get("payment_method_details", {}).get("type") == "us_bank_account":
            p.method = "Bank account (ACH)"
        p.save()
        Invoice.objects.filter(pk=invoice.pk).update(autopay_error="")
    if status == "Succeeded":
        transaction.on_commit(lambda: send_receipt(p))
    audit(None, "payment", "invoice", invoice.pk, f"{'AutoPay' if source == 'autopay' else 'Online'} payment ${p.amount} on {invoice} ({status.lower()})", area="billing")
    return p


# ── charging the card on file ──
def charge_invoice(invoice: Invoice, *, source="autopay", by=None) -> Payment | None:
    c = invoice.client
    if not c.autopay_method_id:
        raise stripe_api.StripeError("No card or bank account on file.")
    bal = invoice.balance
    if bal <= 0:
        return None
    key = f"ws1-{source}-{invoice.pk}-{invoice.autopay_attempts}-{cents(bal)}" + (f"-{timezone.now():%Y%m%d%H%M}" if source == "staff" else "")
    Client.objects.filter(pk=c.pk).update(autopay_last_attempt_at=timezone.now())
    try:
        pi = stripe_api.call("POST", "payment_intents", {
            "amount": cents(bal), "currency": "usd", "customer": ensure_customer(c), "payment_method": c.autopay_method_id,
            "off_session": True, "confirm": True, "description": f"Invoice {invoice.number}", "expand": ["latest_charge"],
            "payment_method_types": [c.autopay_method_type or "card"],
            "metadata": {"invoice_id": invoice.pk, "client_id": c.pk, "autopay": "1"}}, idempotency_key=key)
    except stripe_api.StripeError as e:
        pi = (e.payload or {}).get("payment_intent") or {}
        _failed(invoice, str(e), e.decline_code or e.code)
        if not pi:
            raise
        return None
    p = record_intent(pi, invoice, "autopay" if source == "autopay" else "online")
    if p is None:
        _failed(invoice, f"Stripe status: {pi.get('status')}", "")
    else:
        Client.objects.filter(pk=c.pk).update(autopay_last_status="success" if p.status == "Succeeded" else "processing", autopay_last_error="")
    if by is not None and p:
        audit(None, "payment", "invoice", invoice.pk, f"{by.name} charged the card on file ${p.amount} for {invoice}", area="billing", user=by)
    return p


def _failed(invoice: Invoice, message: str, code: str):
    retry_days, max_tries = _int("autopay.retry_days", 3), _int("autopay.max_attempts", 4)
    n = invoice.autopay_attempts + 1
    give_up = n >= max_tries
    Invoice.objects.filter(pk=invoice.pk).update(autopay_attempts=n, autopay_error=message[:255],
                                                 autopay_next_at=None if give_up else timezone.now() + timedelta(days=retry_days))
    Client.objects.filter(pk=invoice.client_id).update(autopay_last_status="failed", autopay_last_error=message[:255])
    invoice.autopay_attempts = n
    transaction.on_commit(lambda: send_failed(invoice, message, give_up))
    log.warning("AutoPay failed for %s (%s): %s", invoice, code, message)


def run_autopay() -> dict:
    """Background job: charge open invoices for clients on AutoPay (old setting: right when sent, or on the due date)."""
    if not autopay_on():
        return {"skipped": "AutoPay is off or Stripe isn't set up"}
    now, today = timezone.now(), timezone.localdate()
    qs = Invoice.objects.select_related("client").filter(
        status__in=OPEN, archived_at__isnull=True, client__autopay_enabled=True, autopay_attempts__lt=_int("autopay.max_attempts", 4)).exclude(client__autopay_method_id="")
    if Setting.get("autopay.timing", "immediate") == "due_date":
        qs = qs.filter(due_date__lte=today)
    done = {"charged": 0, "pending": 0, "failed": 0}
    for inv in qs[:50]:
        if inv.autopay_next_at and inv.autopay_next_at > now:
            continue
        if inv.payments.filter(status="Pending", archived_at__isnull=True).exists():
            continue  # a bank payment is still clearing
        try:
            p = charge_invoice(inv)
            done["charged" if p and p.status == "Succeeded" else "pending" if p else "failed"] += 1
        except stripe_api.StripeError:
            done["failed"] += 1
    return done


# ── emails ──
def _billing_people(client: Client) -> list[str]:
    from apps.portal.models import PortalUser
    to = [u.email for u in PortalUser.objects.filter(client=client, is_active=True) if u.can("billing")]
    if not to:
        to = [c.email for c in client.contacts.filter(archived_at__isnull=True, role="Billing").exclude(email="")] or ([client.email] if client.email else [])
    return list(dict.fromkeys(to))[:5]


def send_receipt(p: Payment):
    mail.send(_billing_people(p.client), f"Payment received — {p.invoice.number}", "email/payment_receipt",
              {"p": p, "inv": p.invoice, "link": f"{settings.PORTAL_BASE}/invoices/{p.invoice_id}/",
               "message": Setting.get("billing.paid_message", "") or "Thank you for your payment!"})


def send_failed(inv: Invoice, message: str, give_up: bool):
    c = inv.client
    mail.send(_billing_people(c), f"We couldn't charge your {c.autopay_label or 'payment method'} — {inv.number}", "email/autopay_failed",
              {"inv": inv, "c": c, "message": message, "give_up": give_up, "retry_days": _int("autopay.retry_days", 3),
               "link": f"{settings.PORTAL_BASE}/autopay/"})
    staff = Setting.get("company.billing_email", "") or Setting.get("email.support_address", "")
    if staff:
        mail.send(staff, f"AutoPay failed: {c.name} {inv.number}", "email/portal_staff_notice",
                  {"what": f"AutoPay failed for {c.name} ({inv.number}, ${inv.balance})", "detail": message + ("\nNo more automatic retries." if give_up else ""),
                   "link": f"{settings.APP_URL}/clients/{c.pk}/?tab=Invoices"})


# ── setup links (no portal login needed) ──
def make_link(client: Client, by=None, days=7) -> str:
    raw = secrets.token_urlsafe(32)
    AutoPayLink.objects.create(client=client, token_hash=hashlib.sha256(raw.encode()).hexdigest(), created_by=by,
                               expires_at=timezone.now() + timedelta(days=days))
    return f"{settings.PORTAL_BASE}/autopay/link/{raw}/"


def find_link(raw: str) -> AutoPayLink | None:
    return AutoPayLink.objects.select_related("client").filter(token_hash=hashlib.sha256((raw or "").encode()).hexdigest(), used_at__isnull=True,
                                                               expires_at__gt=timezone.now()).first()


# ── webhooks ──
def handle_event(event: dict) -> str:
    eid, etype = event.get("id", ""), event.get("type", "")
    if not eid or StripeEvent.objects.filter(event_id=eid).exists():
        return "duplicate"
    obj = (event.get("data") or {}).get("object") or {}
    result = "ignored"
    if etype in ("checkout.session.completed", "checkout.session.async_payment_succeeded", "checkout.session.async_payment_failed"):
        result = finish_checkout(obj["id"]) or "ok"
    elif etype in ("payment_intent.succeeded", "payment_intent.processing"):
        p = Payment.objects.filter(stripe_payment_intent=obj.get("id")).first()
        inv = p.invoice if p else Invoice.objects.filter(pk=(obj.get("metadata") or {}).get("invoice_id") or 0).first()
        if inv:
            pi = stripe_api.call("GET", f"payment_intents/{obj['id']}", {"expand": ["latest_charge"]})
            record_intent(pi, inv, p.source if p else ("autopay" if (obj.get("metadata") or {}).get("autopay") == "1" else "online"))
            result = "ok"
    elif etype == "payment_intent.payment_failed":
        p = Payment.objects.filter(stripe_payment_intent=obj.get("id")).first()
        if p and p.status == "Pending":  # a bank payment bounced
            p.status = "Failed"
            p.note = ((obj.get("last_payment_error") or {}).get("message") or "Payment failed")[:255]
            p.save()
            _failed(p.invoice, p.note, "")
            result = "ok"
    elif etype == "charge.refunded":
        p = Payment.objects.filter(stripe_payment_intent=obj.get("payment_intent") or "-").first()
        if p and obj.get("refunded"):
            p.status = "Refunded"
            p.save()
            result = "ok"
    elif etype == "payment_method.detached":
        c = Client.objects.filter(autopay_method_id=obj.get("id") or "-").first()
        if c:
            turn_off(c, by="Stripe (card removed)", detach=False)
            result = "ok"
    StripeEvent.objects.create(event_id=eid, type=etype[:80])
    return result
