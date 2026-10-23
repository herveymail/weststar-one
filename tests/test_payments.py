import hashlib
import hmac
import json
import time
from datetime import date
from decimal import Decimal

import pytest

from apps.billing import payments, stripe_api
from apps.billing.models import Invoice, InvoiceLine, Payment
from apps.core.models import Setting
from apps.crm.models import Client
from apps.portal.models import PortalUser

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db
PW = "Correct-horse-battery-9"


class FakeStripe:
    """Records calls and answers like Stripe for the few endpoints we use."""

    def __init__(self):
        self.calls, self.decline = [], False

    def __call__(self, method, path, data=None, idempotency_key=""):
        self.calls.append((method, path, data or {}, idempotency_key))
        if path == "customers":
            return {"id": "cus_test"}
        if path == "checkout/sessions":
            return {"id": "cs_1", "url": "https://checkout.stripe.com/c/pay/cs_1"}
        if path.startswith("checkout/sessions/"):
            return self.session
        if path.startswith("payment_methods/") and method == "GET":
            return {"id": "pm_new", "type": "card", "card": {"brand": "visa", "last4": "4242"}}
        if path == "payment_intents":
            if self.decline:
                raise stripe_api.StripeError("Your card was declined.", "card_declined", "insufficient_funds", 402,
                                             {"type": "card_error", "payment_intent": {"id": "pi_bad", "status": "requires_payment_method"}})
            return {"id": f"pi_{len(self.calls)}", "status": "succeeded", "amount": data["amount"], "amount_received": data["amount"],
                    "payment_method_types": ["card"], "latest_charge": {"receipt_url": "https://pay.stripe.com/receipts/x"}}
        return {}


@pytest.fixture
def fake(monkeypatch, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Setting.put("stripe.secret_key", "sk_test_123", secret=True)
    Setting.put("security.require_mfa", "nobody")
    f = FakeStripe()
    monkeypatch.setattr(stripe_api, "call", f)
    return f


@pytest.fixture
def inv():
    c = Client.objects.create(name="Zubkoff", email="ap@zub.test")
    i = Invoice.objects.create(client=c, number="INV-1", status="Sent", invoice_date=date.today(), due_date=date.today())
    InvoiceLine.objects.create(invoice=i, description="Support", qty=1, rate=Decimal("141.82"))
    i.recalc()
    i.refresh_from_db()
    return i


def portal(client, c):
    u = PortalUser(client=c, name="Pat", email="pat@zub.test", can_billing=True)
    u.set_password(PW)
    u.save()
    assert client.post("/client-portal/login/", {"email": u.email, "password": PW}).status_code == 302
    return u


def test_staff_payment_updates_invoice(inv):
    Payment.objects.create(invoice=inv, amount=Decimal("100"), method="Check", paid_on=date.today())
    inv.refresh_from_db()
    assert inv.amount_paid == Decimal("100") and inv.status == "Partial" and inv.payments.get().client == inv.client
    p2 = Payment.objects.create(invoice=inv, amount=Decimal("41.82"), method="Cash", paid_on=date.today())
    inv.refresh_from_db()
    assert inv.status == "Paid"
    p2.archived_at = p2.created_at
    p2.save()
    inv.refresh_from_db()
    assert inv.status == "Partial" and inv.amount_paid == Decimal("100")


def test_portal_pay_now_and_return(client, fake, inv):
    portal(client, inv.client)
    r = client.post(f"/client-portal/invoices/{inv.pk}/", {"autopay": "1"})
    assert r.status_code == 302 and r["Location"].startswith("https://checkout.stripe.com/")
    data = fake.calls[-1][2]
    assert data["line_items"][0]["price_data"]["unit_amount"] == 14182 and data["payment_intent_data"]["setup_future_usage"] == "off_session"
    fake.session = {"mode": "payment", "metadata": {"client_id": str(inv.client_id), "invoice_id": str(inv.pk), "autopay": "1"},
                    "payment_intent": {"id": "pi_ok", "status": "succeeded", "amount_received": 14182, "payment_method": "pm_new",
                                       "payment_method_types": ["card"], "latest_charge": {"receipt_url": "https://pay.stripe.com/r"}}}
    r = client.get(f"/client-portal/invoices/{inv.pk}/?session=cs_1")
    assert b"payment went through" in r.content
    client.get(f"/client-portal/invoices/{inv.pk}/?session=cs_1")  # reload: still one payment
    inv.refresh_from_db()
    inv.client.refresh_from_db()
    assert inv.status == "Paid" and Payment.objects.count() == 1 and Payment.objects.get().source == "online"
    assert inv.client.autopay_enabled and inv.client.autopay_label == "Visa ending 4242"


def test_other_clients_session_is_ignored(client, fake, inv):
    portal(client, inv.client)
    other = Client.objects.create(name="Other")
    fake.session = {"mode": "payment", "metadata": {"client_id": str(other.pk), "invoice_id": str(inv.pk)},
                    "payment_intent": {"id": "pi_x", "status": "succeeded", "amount_received": 100}}
    client.get(f"/client-portal/invoices/{inv.pk}/?session=cs_1")
    assert not Payment.objects.exists()


def test_autopay_setup_in_portal_and_turn_off(client, fake, inv):
    portal(client, inv.client)
    r = client.post("/client-portal/autopay/", {"action": "setup"})
    assert r["Location"].startswith("https://checkout.stripe.com/") and fake.calls[-1][2]["mode"] == "setup"
    fake.session = {"mode": "setup", "metadata": {"client_id": str(inv.client_id)}, "setup_intent": {"status": "succeeded", "payment_method": "pm_new"}}
    assert b"AutoPay is on" in client.get("/client-portal/autopay/?session=cs_1").content
    client.post("/client-portal/autopay/", {"action": "off"})
    inv.client.refresh_from_db()
    assert not inv.client.autopay_enabled and ("POST", "payment_methods/pm_new/detach", {}, "") in fake.calls


def test_autopay_job_charges_and_retries(fake, inv):
    Client.objects.filter(pk=inv.client_id).update(autopay_enabled=True, autopay_method_id="pm_1", autopay_method_type="card", autopay_last4="1004",
                                                  stripe_customer_id="cus_1")
    fake.decline = True
    assert payments.run_autopay()["failed"] == 1
    inv.refresh_from_db()
    assert inv.autopay_attempts == 1 and inv.autopay_next_at and "declined" in inv.autopay_error
    assert payments.run_autopay() == {"charged": 0, "pending": 0, "failed": 0}  # waits for the retry day
    Invoice.objects.filter(pk=inv.pk).update(autopay_next_at=None)
    fake.decline = False
    assert payments.run_autopay()["charged"] == 1
    inv.refresh_from_db()
    p = inv.payments.get()
    assert inv.status == "Paid" and p.source == "autopay" and p.receipt_url
    assert fake.calls[-1][2]["off_session"] is True and fake.calls[-1][3].startswith(f"ws1-autopay-{inv.pk}-1-")


def test_autopay_gives_up_after_max(fake, inv):
    Setting.put("autopay.max_attempts", "2")
    Client.objects.filter(pk=inv.client_id).update(autopay_enabled=True, autopay_method_id="pm_1", stripe_customer_id="cus_1")
    fake.decline = True
    for _ in range(3):
        Invoice.objects.filter(pk=inv.pk).update(autopay_next_at=None)
        payments.run_autopay()
    inv.refresh_from_db()
    assert inv.autopay_attempts == 2 and inv.autopay_next_at is None


def _signed(payload: bytes, secret="whsec_abc"):
    t = str(int(time.time()))
    sig = hmac.new(secret.encode(), f"{t}.".encode() + payload, hashlib.sha256).hexdigest()
    return f"t={t},v1={sig}"


def test_webhook_signature_and_refund(client, fake, inv):
    Setting.put("stripe.webhook_secret", "whsec_abc", secret=True)
    p = Payment.objects.create(invoice=inv, amount=inv.total, method="Card", paid_on=date.today(), stripe_payment_intent="pi_9", source="online")
    inv.refresh_from_db()
    assert inv.status == "Paid"
    body = json.dumps({"id": "evt_1", "type": "charge.refunded", "data": {"object": {"payment_intent": "pi_9", "refunded": True}}}).encode()
    assert client.post("/stripe/webhook/", body, content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=bad").status_code == 400
    assert client.post("/stripe/webhook/", body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_signed(body)).status_code == 200
    p.refresh_from_db()
    inv.refresh_from_db()
    assert p.status == "Refunded" and inv.status == "Sent"
    assert client.post("/stripe/webhook/", body, content_type="application/json", HTTP_STRIPE_SIGNATURE=_signed(body)).status_code == 200  # duplicate ok


def test_staff_autopay_box_link_and_charge(client, fake, inv):
    signed_in(client, make_user(role="admin"))
    r = client.get(f"/clients/{inv.client_id}/?tab=Invoices")
    assert b"Send AutoPay setup link" in r.content
    r = client.post(f"/clients/{inv.client_id}/autopay/", {"action": "link", "to": ""}, follow=True)
    assert b"/client-portal/autopay/link/" in r.content
    token = r.content.split(b"/client-portal/autopay/link/")[1].split(b"/")[0].decode()
    client.logout()
    page = client.get(f"/client-portal/autopay/link/{token}/")
    assert page.status_code == 200 and b"Set up AutoPay" in page.content
    assert client.post(f"/client-portal/autopay/link/{token}/")["Location"].startswith("https://checkout.stripe.com/")
    fake.session = {"mode": "setup", "metadata": {"client_id": str(inv.client_id)}, "setup_intent": {"status": "succeeded", "payment_method": "pm_new"}}
    assert b"all set" in client.get(f"/client-portal/autopay/link/{token}/?session=cs_1").content
    assert client.get(f"/client-portal/autopay/link/{token}/").status_code == 410  # one use
    signed_in(client, make_user(email="a2@x.test", role="admin"))
    r = client.post(f"/clients/{inv.client_id}/autopay/", {"action": "charge", "invoice": inv.pk}, follow=True)
    inv.refresh_from_db()
    assert inv.status == "Paid" and b"Charged" in r.content
