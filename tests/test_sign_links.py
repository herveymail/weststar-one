"""Quote approval and contract signing from the email link — no sign-in, no portal account."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.test import Client as Browser

from apps.billing.models import Contract, Invoice, Quote, QuoteLine, contract_link, quote_link
from apps.core import mail
from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.portal.models import ContractSignature, QuoteApproval

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def acme():
    c = Client.objects.create(name="Acme", email="ap@acme.test", state="AZ")
    Contact.objects.create(client=c, name="Pat Lee", email="pat@acme.test", role="Billing", is_primary=True)
    return c


@pytest.fixture
def quote(acme):
    q = Quote.objects.create(client=acme, number="QT-7", status="Sent", quote_date=date.today(), expires_on=date.today() + timedelta(days=30))
    QuoteLine.objects.create(quote=q, description="Firewall", qty=1, rate=Decimal("1000"))
    q.recalc()
    return q


def _path(link):
    return "/" + link.split("/", 3)[3]


def test_quote_email_uses_the_public_link(client, quote, monkeypatch):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user(role="admin"))
    sent = {}
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.update(link=ctx["link"], tpl=tpl) or True)
    client.post(f"/billing/quote/{quote.pk}/send/", {"to": "pat@acme.test", "subject": "Quote", "message": "Hi", "attach": "1"})
    quote.refresh_from_db()
    assert sent["tpl"] == "email/quote" and "/quote/" in sent["link"] and quote.public_token in sent["link"]


def test_accept_quote_without_signing_in(quote, monkeypatch):
    notes = []
    monkeypatch.setattr(mail, "send", lambda to, subject, *a, **kw: notes.append(subject) or True)
    Setting.put("email.support_address", "help@weststar.test")
    anon = Browser()
    path = _path(quote_link(quote))
    page = anon.get(path)
    assert page.status_code == 200 and b"QT-7" in page.content and b"Accept quote" in page.content and b"Terms &amp; Conditions" in page.content
    assert page["X-Robots-Tag"].startswith("noindex")
    assert anon.get(path + "pdf/").content[:5] == b"%PDF-"
    # name + tick are required
    r = anon.post(path, {"decision": "accepted", "name": "Pat Lee"})
    assert r.status_code == 200 and b"tick the box" in r.content
    r = anon.post(path, {"decision": "accepted", "name": "Pat Lee", "agree": "1"})
    assert r.status_code == 302
    quote.refresh_from_db()
    a = QuoteApproval.objects.get(quote=quote)
    assert quote.status == "Accepted" and a.signed_name == "Pat Lee" and a.decision == "accepted" and a.total == Decimal("1000.00")
    assert any("QT-7 accepted" in s for s in notes)
    assert quote.deposit_invoice is None  # no deposit set
    # a second click records nothing more
    anon.post(path, {"decision": "declined", "name": "Pat"})
    assert QuoteApproval.objects.filter(quote=quote).count() == 1


def test_deposit_invoice_on_accept(quote):
    Setting.put("billing.quote_deposit_pct", "50")
    anon = Browser()
    path = _path(quote_link(quote))
    assert b"Deposit (50%)" in anon.get(path).content
    anon.post(path, {"decision": "accepted", "name": "Pat Lee", "agree": "1"})
    quote.refresh_from_db()
    dep = quote.deposit_invoice
    assert dep and dep.status == "Sent" and dep.total == Decimal("500.00") and dep.client == quote.client
    page = anon.get(path)
    assert b"Pay deposit" in page.content and dep.public_token.encode() in page.content
    Setting.put("billing.quote_deposit_invoice", "false")
    q2 = Quote.objects.create(client=quote.client, number="QT-8", status="Sent", quote_date=date.today())
    QuoteLine.objects.create(quote=q2, description="X", qty=1, rate=Decimal("100"))
    q2.recalc()
    anon.post(_path(quote_link(q2)), {"decision": "accepted", "name": "Pat", "agree": "1"})
    assert Quote.objects.get(pk=q2.pk).deposit_invoice is None and Invoice.objects.count() == 1


def test_decline_quote_with_reason(quote):
    anon = Browser()
    path = _path(quote_link(quote))
    anon.post(path, {"decision": "declined", "name": "Pat", "comment": "Too pricey"})
    quote.refresh_from_db()
    assert quote.status == "Declined" and QuoteApproval.objects.get(quote=quote).comment == "Too pricey"


def test_quote_link_rules(client, quote):
    anon = Browser()
    path = _path(quote_link(quote))
    assert anon.get("/quote/not-the-right-token-at-all/").status_code == 404
    Quote.objects.filter(pk=quote.pk).update(expires_on=date.today() - timedelta(days=1))
    page = anon.get(path)
    assert b"expired" in page.content and b"Accept quote" not in page.content
    anon.post(path, {"decision": "accepted", "name": "Pat", "agree": "1"})
    assert Quote.objects.get(pk=quote.pk).status == "Sent"
    Quote.objects.filter(pk=quote.pk).update(status="Draft", expires_on=None)
    assert anon.get(path).status_code == 404  # drafts: staff preview only
    Setting.put("security.require_mfa", "nobody")
    staff = signed_in(client, make_user(role="admin"))
    assert b"still a draft" in staff.get(path).content
    Quote.objects.filter(pk=quote.pk).update(status="Sent")
    staff.post(path, {"decision": "accepted", "name": "Me", "agree": "1"})  # staff can't accept for the client
    assert Quote.objects.get(pk=quote.pk).status == "Sent"
    Setting.put("billing.public_links", "false")
    assert anon.get(path).status_code == 404


def test_contract_send_and_sign(client, acme, monkeypatch):
    c = Contract.objects.create(client=acme, name="Managed Services", number="CT-3", status="Draft", monthly_rate=Decimal("800"), terms="Be nice.")
    Setting.put("security.require_mfa", "nobody")
    staff = signed_in(client, make_user(role="admin"))
    page = staff.get(f"/billing/contract/{c.pk}/send/")
    assert page.status_code == 200 and b"pat@acme.test" in page.content and b"Review &amp; sign" in page.content
    assert b"Send for signature" in staff.get(f"/m/contracts/{c.pk}/", HTTP_HX_REQUEST="true").content
    sent = {}
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.update(to=to, link=ctx["link"], tpl=tpl) or True)
    r = staff.post(f"/billing/contract/{c.pk}/send/", {"to": "pat@acme.test", "subject": "Please sign", "message": "Hi"})
    c.refresh_from_db()
    assert r.status_code == 302 and c.status == "Sent" and sent["tpl"] == "email/contract" and sent["link"] == contract_link(c)
    staff.post("/logout/")
    anon = Browser()
    path = _path(sent["link"])
    page = anon.get(path)
    assert page.status_code == 200 and b"Managed Services" in page.content and b"Be nice." in page.content and b"State of Arizona" in page.content
    r = anon.post(path, {"name": "Pat Lee"})
    assert b"tick the box" in r.content
    r = anon.post(path, {"name": "Pat Lee", "title": "Owner", "agree": "1"})
    assert r.status_code == 302
    c.refresh_from_db()
    s = ContractSignature.objects.get(contract=c)
    assert c.status == "Active" and c.start_date == date.today() and s.signed_title == "Owner" and len(s.content_hash) == 64
    assert b"Signed by Pat Lee" in anon.get(path).content
    anon.post(path, {"name": "Again", "agree": "1"})
    assert ContractSignature.objects.filter(contract=c).count() == 1


def test_contract_link_rules(acme):
    c = Contract.objects.create(client=acme, name="NDA", status="Draft")
    anon = Browser()
    path = _path(contract_link(c))
    assert anon.get(path).status_code == 404  # draft
    Contract.objects.filter(pk=c.pk).update(status="Cancelled")
    assert anon.get(path).status_code == 404
    assert anon.get("/sign/short/").status_code == 404
