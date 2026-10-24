from datetime import date
from decimal import Decimal

import pytest

from apps.billing.models import Invoice, InvoiceLine, Quote, QuoteLine
from apps.core import mail
from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.portal.models import PortalUser

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def inv():
    c = Client.objects.create(name="Acme", email="ap@acme.test")
    Contact.objects.create(client=c, name="Pat Lee", email="pat@acme.test", role="Billing")
    i = Invoice.objects.create(client=c, number="INV-9", status="Draft", invoice_date=date.today(), due_date=date.today())
    InvoiceLine.objects.create(invoice=i, description="Support <b>", qty=2, rate=Decimal("50"))
    i.recalc()
    return i


def test_document_page_pdf_and_send(client, inv, monkeypatch):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user(role="admin"))
    r = client.get(f"/billing/invoice/{inv.pk}/")
    assert r.status_code == 200 and b"wsdoc-kind" in r.content and b"Support &lt;b&gt;" in r.content and b"$100.00" in r.content
    p = client.get(f"/billing/invoice/{inv.pk}/pdf/")
    assert p.status_code == 200 and p.content[:5] == b"%PDF-" and "INV-9" in p["Content-Disposition"]
    page = client.get(f"/billing/invoice/{inv.pk}/send/")
    assert b"Hi Pat," in page.content and b"View &amp; pay invoice" in page.content
    sent = {}
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.update(to=to, subject=subject, tpl=tpl, **kw) or True)
    r = client.post(f"/billing/invoice/{inv.pk}/send/", {"to": "pat@acme.test", "subject": "Invoice INV-9", "message": "Hi", "attach": "1"})
    inv.refresh_from_db()
    assert r.status_code == 302 and inv.status == "Sent" and sent["tpl"] == "email/invoice"
    assert sent["attachments"][0][0] == "Invoice-INV-9.pdf" and sent["attachments"][0][1][:5] == b"%PDF-"
    assert b"/billing/invoice/" in client.get("/m/invoices/").content  # rows open the document


def test_quote_document_and_portal_pdf(client, inv):
    q = Quote.objects.create(client=inv.client, number="QT-1", status="Sent", quote_date=date.today())
    QuoteLine.objects.create(quote=q, description="Firewall", qty=1, rate=Decimal("900"))
    q.recalc()
    pu = PortalUser(client=inv.client, name="Pat", email="pat@acme.test", can_billing=True)
    pu.set_password("Correct-horse-battery-9")
    pu.save()
    client.post("/client-portal/login/", {"email": "pat@acme.test", "password": "Correct-horse-battery-9"})
    assert client.get(f"/client-portal/quote/{q.pk}/pdf/").content[:5] == b"%PDF-"
    assert client.get(f"/client-portal/invoice/{inv.pk}/pdf/").status_code == 404  # still a draft
    other = Client.objects.create(name="Other")
    oi = Invoice.objects.create(client=other, number="INV-X", status="Sent", invoice_date=date.today(), due_date=date.today())
    assert client.get(f"/client-portal/invoice/{oi.pk}/pdf/").status_code == 404
