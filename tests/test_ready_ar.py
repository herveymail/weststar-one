"""Ready to bill, Receivables (aging + statements) and automatic payment reminders."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.billing import reminders
from apps.billing.models import Invoice, InvoiceLine, InvoiceReminder
from apps.core import mail
from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.helpdesk.models import Ticket, TicketSignoff, TimeEntry
from apps.tools.models import MileageTrip

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def staff(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin")
    signed_in(client, u)
    return u


@pytest.fixture
def bf():
    c = Client.objects.create(name="Break Fix Co", plan="Break/fix", hourly_rate=Decimal("120"), email="ap@bf.test", net_terms=15)
    Contact.objects.create(client=c, name="Bo", email="bo@bf.test", role="Billing")
    return c


def _work(c, user, minutes, wt="Remote", when=None, n=1):
    t = Ticket.objects.create(number=f"T-{c.pk}-{n}", subject=f"Job {n}", client=c, status="Resolved")
    TimeEntry.objects.create(ticket=t, user=user, minutes=minutes, work_type=wt, work_date=when or timezone.localdate())
    return t


def test_ready_to_bill_creates_one_draft_per_client(client, staff, bf):
    Setting.put("billing.mileage_rate", "0.70")
    managed = Client.objects.create(name="Managed Co", plan="Managed")
    t = _work(bf, staff, 90, "On-site")
    TimeEntry.objects.create(ticket=t, user=staff, minutes=30, work_type="Remote", work_date=timezone.localdate())
    _work(bf, staff, 60, n=2)
    _work(managed, staff, 45)
    TimeEntry.objects.create(ticket=t, user=staff, minutes=600, work_date=timezone.localdate(), billable=False)
    MileageTrip.objects.create(user=staff, trip_date=timezone.localdate(), trip="Office → BF", miles=Decimal("20"), client=bf, billable=True)
    TicketSignoff.objects.create(ticket=t, type="completion", parts_desc="SSD", parts_amount=Decimal("89"))
    page = client.get("/billing/ready/")
    assert page.status_code == 200 and b"Break Fix Co" in page.content and b"Managed Co" in page.content
    assert b"usually covered by the contract" in page.content
    r = client.post("/billing/ready/", {"action": "create", "client": [bf.pk]})
    assert r.status_code == 302
    inv = Invoice.objects.get(client=bf)
    lines = list(inv.lines.order_by("sort_order"))
    assert inv.status == "Draft" and len(lines) == 4
    assert lines[0].qty == Decimal("2.00") and lines[0].rate == Decimal("120") and "On-site 1.5 h" in lines[0].description
    assert lines[2].description.startswith("Mileage") and lines[2].qty == Decimal("20") and lines[3].rate == Decimal("89") and lines[3].taxable
    assert inv.subtotal == Decimal("240") + Decimal("120") + Decimal("14") + Decimal("89")
    assert inv.due_date == timezone.localdate() + timedelta(days=15)
    assert not TimeEntry.objects.filter(ticket__client=bf, billable=True, invoice__isnull=True).exists()
    # nothing is billed twice
    client.post("/billing/ready/", {"action": "create", "client": [bf.pk]})
    assert Invoice.objects.filter(client=bf).count() == 1
    assert b"Managed Co" in client.get("/billing/ready/").content and b"Break Fix Co" not in client.get("/billing/ready/").content
    client.post("/billing/ready/", {"action": "nocharge", "client": managed.pk})
    assert b"Nothing waiting" in client.get("/billing/ready/").content


def test_send_all_new_drafts(client, staff, bf, monkeypatch):
    _work(bf, staff, 60)
    client.post("/billing/ready/", {"action": "create", "client": [bf.pk]})
    inv = Invoice.objects.get(client=bf)
    page = client.get(f"/billing/ready/?made={inv.pk}")
    assert b"New drafts" in page.content and b"bo@bf.test" in page.content
    sent = []
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.append((to, tpl, ctx["link"], bool(kw.get("attachments")))) or True)
    client.post("/billing/ready/", {"action": "send", "inv": [inv.pk]})
    inv.refresh_from_db()
    assert inv.status == "Sent" and sent[0][0] == ["bo@bf.test"] and sent[0][1] == "email/invoice" and "/pay/" in sent[0][2] and sent[0][3]


def _inv(c, due, total="100", status="Sent", n="INV-1"):
    inv = Invoice.objects.create(number=n, client=c, status=status, invoice_date=due - timedelta(days=30), due_date=due)
    InvoiceLine.objects.create(invoice=inv, description="Work", qty=1, rate=Decimal(total), taxable=False)
    inv.recalc()
    inv.save()
    return inv


def test_aging_and_statement(client, staff, bf, monkeypatch):
    today = timezone.localdate()
    _inv(bf, today + timedelta(days=5), "100", n="INV-1")
    _inv(bf, today - timedelta(days=45), "200", n="INV-2")
    _inv(bf, today - timedelta(days=120), "300", n="INV-3")
    _inv(bf, today - timedelta(days=10), "999", status="Draft", n="INV-4")
    page = client.get("/billing/ar/")
    assert page.status_code == 200 and b"$600.00" in page.content and b"$300.00" in page.content and b"999" not in page.content
    st = client.get(f"/billing/ar/statement/{bf.pk}/")
    assert b"INV-3" in st.content and b"120 days late" in st.content and b"/pay/" in st.content
    got = {}
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: got.update(to=to, tpl=tpl, n=len(ctx["invoices"]), total=ctx["total"]) or True)
    client.post(f"/billing/ar/statement/{bf.pk}/", {"to": "bo@bf.test", "message": "Hi"})
    assert got == {"to": ["bo@bf.test"], "tpl": "email/statement", "n": 3, "total": Decimal("600")}


def test_reminders(bf, monkeypatch):
    sent = []
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.append(subject) or True)
    today = timezone.localdate()
    noon = timezone.make_aware(datetime.combine(today, datetime.min.time()).replace(hour=12))
    soon = _inv(bf, today + timedelta(days=2), n="INV-A")
    late = _inv(bf, today - timedelta(days=16), n="INV-B")
    assert reminders.run(noon) == "off" and not sent
    Setting.put("billing.reminders_on", "true")
    assert reminders.run(noon.replace(hour=2)) == "outside sending hours"
    reminders.run(noon)
    assert sorted(sent) == ["Invoice INV-A reminder", "Past due: invoice INV-B"]
    # INV-B is 16 days late: only the 14-day reminder went out; the 7-day one is marked skipped, never sent later
    assert set(InvoiceReminder.objects.filter(invoice=late).values_list("step", flat=True)) >= {"after14", "after7", "due", "before3"}
    sent.clear()
    reminders.run(noon)
    assert sent == []  # nothing twice
    # AutoPay clients and paid invoices get nothing
    Client.objects.filter(pk=bf.pk).update(autopay_enabled=True)
    InvoiceReminder.objects.all().delete()
    reminders.run(noon)
    assert sent == []
    assert soon.pk
