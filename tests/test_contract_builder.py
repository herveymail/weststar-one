"""Billing › Contracts › New agreement: MSA and managed-services contracts are written from a form, sent and e-signed."""
from decimal import Decimal as D

import pytest
from django.test import Client as Browser

from apps.billing import contract_builder as builder
from apps.billing.models import Contract
from apps.core.models import Setting
from apps.crm.models import Client, Contact

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db

MSP = {"kind": "Managed", "term_months": "12", "auto_renew": "on", "notice_days": "60", "include_msa": "on", "increase_pct": "3",
       "services": ["help_desk", "monitoring", "security"], "service_notes": "Quarterly dark-web scan",
       "users": "12", "user_rate": "95", "servers": "2", "server_rate": "150", "flat_fee": "100", "setup_fee": "500",
       "overage_rate": "150", "after_hours_rate": "225", "exclusions": "Printer toner", "our_signer": "Casey Hervey", "our_title": "Owner"}


@pytest.fixture
def acct(client):
    Setting.put("company.name", "Weststar MSP")
    Setting.put("security.require_mfa", "nobody")
    Setting.put("helpdesk.open", "07:00")
    Setting.put("helpdesk.close", "16:30")
    signed_in(client, make_user("acct@example.com", role="admin"))
    return client


@pytest.fixture
def acme():
    c = Client.objects.create(name="Acme Dental", state="TX", net_terms=15)
    Contact.objects.create(client=c, name="Dr. Lee", email="lee@acme.test", is_primary=True)
    return c


def test_managed_services_contract_is_written_from_the_form(acct, acme):
    r = acct.post("/billing/contract/build/", {**MSP, "client": acme.pk})
    c = Contract.objects.get()
    assert r["Location"] == f"/billing/contract/{c.pk}/"
    assert (c.type, c.status, c.monthly_rate, c.name) == ("Managed", "Draft", D("1540.00"), "Managed Services Agreement — Acme Dental")
    assert c.number and c.built
    s = c.scope
    for want in ("Managed Services Schedule", "12 users × $95 per user per month", "2 servers × $150 per server per month", "Monthly fee: $1,540",
                 "One-time onboarding fee: $500", "Help desk:", "Quarterly dark-web scan", "1 year (12 months)", "at least 60 days", "increases by 3%",
                 "After-hours rate: $225", "Printer toner", "Mon–Fri · 7 AM – 4:30 PM", "one signature covers both", "Onsite visits are not part"):
        assert want in s, want
    t = c.terms
    for want in ("Master Services Agreement", "Weststar MSP", "Acme Dental", "State of Texas", "El Paso County", "within 15 days of the invoice date",
                 "LAST" not in t and "12 MONTHS", "Electronic signatures"):
        assert want is True or want in t, want
    assert "{" not in s and "{" not in t                     # every placeholder was filled
    page = acct.get(f"/billing/contract/{c.pk}/").content.decode()
    assert "Send for e-signature" in page and "Change details" in page and "$1,540.00" in page


def test_price_is_required_and_an_msa_alone_needs_none(acct, acme):
    bad = {k: v for k, v in MSP.items() if k not in ("users", "user_rate", "servers", "server_rate", "flat_fee")}
    r = acct.post("/billing/contract/build/", {**bad, "client": acme.pk})
    assert r.status_code == 422 and b"Add a price" in r.content and not Contract.objects.exists()
    r = acct.post("/billing/contract/build/", {"kind": "MSA", "client": acme.pk, "notice_days": "30", "our_signer": "Casey Hervey"})
    msa = Contract.objects.get()
    assert r.status_code == 302 and (msa.type, msa.scope, msa.monthly_rate) == ("MSA", "", None) and "## 13. Limitation of liability" in msa.terms
    # a managed contract under that MSA refers to it instead of repeating the terms
    acct.post("/billing/contract/build/", {**MSP, "client": acme.pk, "msa": msa.pk})
    sched = Contract.objects.exclude(pk=msa.pk).get()
    assert sched.terms == "" and sched.msa == msa and "a Schedule under the Master Services Agreement" in sched.scope and not sched.include_msa


def test_send_sign_lock_and_pdf(acct, acme, monkeypatch):
    from apps.core import mail
    sent = {}
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.update(link=ctx["link"]) or True)
    acct.post("/billing/contract/build/", {**MSP, "client": acme.pk})
    c = Contract.objects.get()
    r = acct.post(f"/billing/contract/{c.pk}/send/", {"to": "lee@acme.test", "subject": "Please sign", "message": "Hi"})
    c.refresh_from_db()
    assert r.status_code == 302 and c.status == "Sent" and c.our_signed_at and c.our_signer == "Casey Hervey"
    path = sent["link"][sent["link"].index("/sign/"):]
    guest = Browser()
    page = guest.get(path).content.decode()
    assert "Managed Services Schedule" in page and "<h3>4. Fees</h3>" in page and "Casey Hervey" in page and "Download PDF" in page
    assert guest.get(path + "pdf/").content[:5] == b"%PDF-"
    r = guest.post(path, {"name": "Dana Lee", "title": "Owner", "agree": "1"})
    c.refresh_from_db()
    assert r.status_code == 302 and c.status == "Active" and c.signatures.get().signed_name == "Dana Lee"
    # signed: no more changes
    assert acct.get(f"/billing/contract/{c.pk}/build/").status_code == 302
    r = acct.post(f"/m/contracts/{c.pk}/", {"name": c.name, "client": acme.pk, "type": "Managed", "status": "Active", "scope": "Something else", "terms": c.terms,
                                            "auto_renew": "on", "start_date": str(c.start_date)})
    c.refresh_from_db()
    assert r.status_code == 422 and b"This agreement is signed" in r.content and "Managed Services Schedule" in c.scope
    from apps.billing.contract_views import pdf_bytes
    assert pdf_bytes(c)[:5] == b"%PDF-"
    page = acct.get(f"/billing/contract/{c.pk}/").content.decode()
    assert "Signed by Dana Lee" in page and "Change details" not in page and "Send for e-signature" not in page


def test_a_draft_can_be_changed_and_rebuilt(acct, acme):
    acct.post("/billing/contract/build/", {**MSP, "client": acme.pk})
    c = Contract.objects.get()
    assert b'value="95.00"' in acct.get(f"/billing/contract/{c.pk}/build/").content
    acct.post(f"/billing/contract/{c.pk}/build/", {**MSP, "client": acme.pk, "users": "20", "term_months": ""})
    c.refresh_from_db()
    assert c.monthly_rate == D("2300.00") and "20 users" in c.scope and "month to month" in c.scope and "no early-termination charge" in c.scope
    assert builder.monthly_total(c) == D("2300.00") and Contract.objects.count() == 1


def test_msa_wording_can_be_changed_in_settings(acct, acme):
    Setting.put("legal.msa", "## Our Agreement\nBetween {company} and {client}, under {state} law.")
    acct.post("/billing/contract/build/", {"kind": "MSA", "client": acme.pk, "notice_days": "30"})
    assert Contract.objects.get().terms == "## Our Agreement\nBetween Weststar MSP and Acme Dental, under Texas law."


def test_hourly_contract_and_baa(acct, acme):
    r = acct.post("/billing/contract/build/", {"kind": "Break/fix", "client": acme.pk, "notice_days": "30", "include_msa": "on", "after_hours_rate": "225", "trip_fee": "75"})
    assert r.status_code == 422 and b"Add the hourly rate" in r.content
    acct.post("/billing/contract/build/", {"kind": "Break/fix", "client": acme.pk, "notice_days": "30", "include_msa": "on", "overage_rate": "150",
                                           "after_hours_rate": "225", "trip_fee": "75", "included_hours": "1", "service_notes": "Remote work is billed in 15-minute steps"})
    h = Contract.objects.get(type="Break/fix")
    for want in ("Hourly Services Schedule", "Standard rate: $150 per hour", "After-hours rate: $225", "Onsite trip charge: $75", "Minimum charge: 1 hour per onsite visit",
                 "15-minute steps", "no monthly fee", "confirm it is complete", "30 days' written notice"):
        assert want in h.scope, want
    assert h.name == "Hourly Services Agreement — Acme Dental" and h.monthly_rate is None and "Master Services Agreement" in h.terms and "{" not in h.scope
    acct.post("/billing/contract/build/", {"kind": "BAA", "client": acme.pk, "notice_days": "30", "include_msa": "on"})
    b = Contract.objects.get(type="BAA")
    for want in ("Business Associate Agreement", 'Acme Dental ("Covered Entity")', 'Weststar MSP ("Business Associate")', "45 CFR 164.410", "no later than 10 days",
                 "164.502(e)(1)(ii)", "164.524", "164.526", "164.528", "Secretary of Health and Human Services", "return or destroy"):
        assert want in b.terms, want
    assert b.scope == "" and not b.include_msa and "{" not in b.terms
    page = acct.get(f"/billing/contract/{b.pk}/").content.decode()
    assert "Business Associate Agreement" in page and "Create recurring billing" not in page


def test_recurring_billing_from_a_signed_contract(acct, acme):
    from apps.billing.models import Invoice, RecurringInvoice
    from apps.portal.models import ContractSignature
    acct.post("/billing/contract/build/", {**MSP, "client": acme.pk})
    c = Contract.objects.get()
    assert "Once the client signs" in acct.get(f"/billing/contract/{c.pk}/").content.decode()
    acct.post(f"/billing/contract/{c.pk}/billing/")                      # not signed yet: nothing happens
    assert not RecurringInvoice.objects.exists()
    ContractSignature.objects.create(contract=c, signed_name="Dana Lee", content_hash="x")
    Contract.objects.filter(pk=c.pk).update(status="Active")
    assert "Create recurring billing" in acct.get(f"/billing/contract/{c.pk}/").content.decode()
    acct.post(f"/billing/contract/{c.pk}/billing/")
    acct.post(f"/billing/contract/{c.pk}/billing/")                      # twice: still one of each
    r, inv = RecurringInvoice.objects.get(), Invoice.objects.get()
    assert (r.total, r.status, r.client, r.next_run.day) == (D("1540.00"), "Active", acme, 1)
    assert [(ln.description, ln.qty, ln.rate) for ln in r.lines.all()] == [("Managed services — per user", 12, D("95.00")), ("Managed services — per server", 2, D("150.00")),
                                                                           ("Managed services — base monthly fee", 1, D("100.00"))]
    assert (inv.total, inv.status) == (D("500.00"), "Draft")
    c.refresh_from_db()
    page = acct.get(f"/billing/contract/{c.pk}/").content.decode()
    assert c.recurring == r and c.setup_invoice == inv and inv.number in page and "Create recurring billing" not in page


def test_included_hours_never_say_unlimited(acct, acme):
    acct.post("/billing/contract/build/", {**MSP, "client": acme.pk, "included_hours": "10"})
    s = Contract.objects.get().scope
    assert "nlimited" not in s and "not metered" not in s
    for want in ("up to a combined total of 10 hours of our time per month", "Help desk: Remote help desk support", "includes up to 10 hours of Covered Services per month",
                 "Work that is not covered or beyond the included hours: $150 per hour"):
        assert want in s, want
    # without included hours it is still the unlimited plan
    c = Contract.objects.get()
    acct.post(f"/billing/contract/{c.pk}/build/", {**MSP, "client": acme.pk})
    c.refresh_from_db()
    assert "Help desk: Unlimited remote help desk support" in c.scope and "not metered" in c.scope and "{" not in c.scope
