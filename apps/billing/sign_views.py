"""Links in quote and contract emails: the client reviews and approves/signs without signing in or a portal account.

/quote/<token>/      the quote: Download PDF, Accept (typed name + tick) or Decline (with a reason)
/quote/<token>/pdf/  the PDF
/sign/<token>/       the contract: read it, type name + title, tick, Sign

Same rules as the invoice pay link (pay_views.py): long random token, drafts open only for signed-in staff (preview),
private no-cache headers, rate limits on the buttons. Every decision is stored with the typed name, the IP and — for
contracts — a fingerprint of the exact text that was signed, and is copied to the support inbox.
"""
from decimal import Decimal

from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.core import mail
from apps.core.audit import audit
from apps.core.models import Setting

from .models import Contract, Invoice, InvoiceLine, Quote, invoice_link
from .pay_views import _private, _rate_ok, _unavailable


def _obj(request, model, token):
    if Setting.get("billing.public_links", "true") == "false" or len(token) < 20:
        return None
    o = model.objects.select_related("client").filter(public_token=token, archived_at__isnull=True).first()
    if o is None or (o.status in ("Draft", "Cancelled") and not request.user.is_authenticated):
        return None
    return o


def _brand():
    from apps.core.branding import login_brand, logo_url
    return {**login_brand(), "company": Setting.get("company.name", "") or "Weststar MSP", "logo_url": logo_url()}


def _notify(what, detail, link):
    to = Setting.get("email.support_address")
    if to:
        mail.send(to, what, "email/portal_staff_notice", {"what": what, "detail": detail, "link": f"{settings.APP_URL}{link}"}, background=True)


def deposit_pct() -> Decimal:
    try:
        return Decimal(Setting.get("billing.quote_deposit_pct", "0") or 0)
    except Exception:  # noqa: BLE001
        return Decimal(0)


def _pct_txt(pct: Decimal) -> str:
    t = f"{pct:f}"
    return t.rstrip("0").rstrip(".") if "." in t else t


def make_deposit_invoice(q: Quote) -> Invoice | None:
    """When a quote with a deposit is accepted: a deposit invoice, already marked Sent so the client can pay it right away."""
    from apps.core.numbering import next_number
    pct = deposit_pct()
    if pct <= 0 or not q.total or Setting.get("billing.quote_deposit_invoice", "true") == "false":
        return None
    if q.deposit_invoice_id:
        return q.deposit_invoice
    amount = (q.total * pct / 100).quantize(Decimal("0.01"))
    today = timezone.localdate()
    inv = Invoice.objects.create(number=next_number("invoice"), client=q.client, status="Sent", invoice_date=today, due_date=today,
                                 scope=f"Deposit for quote {q.number}", notes=q.scope[:2000] if q.scope else "")
    pct_txt = _pct_txt(pct)
    InvoiceLine.objects.create(invoice=inv, description=f"{pct_txt}% deposit — quote {q.number}", qty=1, rate=amount, taxable=False, sort_order=0)
    inv.recalc()
    Quote.objects.filter(pk=q.pk).update(deposit_invoice=inv)
    return inv


def quote_page(request, token):
    from apps.core import legal
    from apps.core.net import client_ip
    from apps.portal.models import QuoteApproval

    q = _obj(request, Quote, token)
    if q is None:
        return _unavailable(request)
    error = ""
    expired = bool(q.expires_on and q.expires_on < timezone.localdate() and q.status == "Sent")
    if request.method == "POST" and q.status == "Sent" and not expired:
        decision, name = request.POST.get("decision"), request.POST.get("name", "").strip()[:200]
        comment = request.POST.get("comment", "").strip()[:2000]
        if not request.user.is_authenticated and not _rate_ok(f"quote:{client_ip(request)}", 20, 3600):
            error = "Too many tries — please wait a bit."
        elif request.user.is_authenticated:
            error = "This is the client's page — you're signed in as staff, so nothing was recorded."
        elif decision == "accepted" and not (name and request.POST.get("agree")):
            error = "Type your full name and tick the box to accept."
        elif decision == "declined" and not name:
            error = "Type your name so we know who declined."
        elif decision in ("accepted", "declined"):
            with transaction.atomic():
                # Lock the row so a double-click can't record two decisions.
                cur = Quote.objects.select_for_update().get(pk=q.pk)
                if cur.status == "Sent":
                    QuoteApproval.objects.create(quote=q, portal_user=None, decision=decision, signed_name=name, total=q.total,
                                                 comment=comment, ip=client_ip(request)[:64])
                    Quote.objects.filter(pk=q.pk).update(status="Accepted" if decision == "accepted" else "Declined", updated_at=timezone.now())
                    dep = make_deposit_invoice(q) if decision == "accepted" else None
                else:
                    dep = None
            audit(None, f"quote_{decision}", "quotes", q.pk, f"{name} {decision} {q} from the email link", area="billing")
            extra = f"\nDeposit invoice {dep.number} created." if dep else ""
            _notify(f"Quote {q.number} {decision} by {name} ({q.client.name})", (comment or "") + extra, f"/billing/quote/{q.pk}/")
            return redirect(f"/quote/{token}/?done={decision}")
    q.refresh_from_db()
    dep = q.deposit_invoice if q.deposit_invoice_id else None
    pct = deposit_pct()
    return _private(render(request, "billing/quote_public.html", {
        **_brand(), "q": q, "lines": q.lines.all(), "client": q.client, "base": f"{settings.APP_URL}/quote/{token}/",
        "approval": q.approvals.order_by("-created_at").first(), "error": error, "expired": expired, "done": request.GET.get("done", ""),
        "is_draft": q.status == "Draft", "staff": request.user.is_authenticated,
        "deposit": (q.total * pct / 100).quantize(Decimal("0.01")) if pct > 0 and q.total else None, "deposit_pct": _pct_txt(pct),
        "deposit_link": invoice_link(dep) if dep and dep.status not in ("Paid", "Void") else "", "deposit_inv": dep,
        "legal_html": legal.html("quote_terms", q.client)}))


def quote_pdf(request, token):
    from .documents import filename, pdf
    q = _obj(request, Quote, token)
    if q is None:
        return _unavailable(request)
    r = HttpResponse(pdf(q, "quote"), content_type="application/pdf")
    r["Content-Disposition"] = f'attachment; filename="{filename(q, "quote")}"'
    return _private(r)


def contract_page(request, token):
    from apps.core.net import client_ip
    from apps.portal.models import ContractSignature
    from apps.portal.views import _contract_hash

    c = _obj(request, Contract, token)
    if c is None:
        return _unavailable(request)
    error = ""
    if request.method == "POST" and c.status == "Sent":
        name, ttl = request.POST.get("name", "").strip()[:200], request.POST.get("title", "").strip()[:200]
        if request.user.is_authenticated:
            error = "This is the client's page — you're signed in as staff, so nothing was recorded."
        elif not _rate_ok(f"sign:{client_ip(request)}", 20, 3600):
            error = "Too many tries — please wait a bit."
        elif not (name and request.POST.get("agree")):
            error = "Type your full name and tick the box to sign."
        else:
            with transaction.atomic():
                cur = Contract.objects.select_for_update().get(pk=c.pk)
                if cur.status == "Sent":
                    ContractSignature.objects.create(contract=c, portal_user=None, signed_name=name, signed_title=ttl,
                                                     content_hash=_contract_hash(c), ip=client_ip(request)[:64])
                    Contract.objects.filter(pk=c.pk).update(status="Active", start_date=c.start_date or timezone.localdate(), updated_at=timezone.now())
            audit(None, "contract_signed", "contracts", c.pk, f"{name} signed {c} from the email link", area="billing")
            _notify(f"Contract signed: {c} ({c.client.name})", f"Signed by {name}{', ' + ttl if ttl else ''}", f"/m/contracts/{c.pk}/")
            return redirect(f"/sign/{token}/?done=1")
    c.refresh_from_db()
    from apps.core import legal
    state, county = legal.jurisdiction(c.client)
    return _private(render(request, "billing/contract_public.html", {
        **_brand(), "c": c, "client": c.client, "signature": c.signatures.order_by("-created_at").first(), "error": error,
        "done": request.GET.get("done"), "is_draft": c.status == "Draft", "staff": request.user.is_authenticated,
        "law": f"This agreement is governed by the laws of the State of {state}" + (f"; any dispute will be heard in {county} County, {state}." if county else ".")}))
