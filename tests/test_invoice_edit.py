"""Editing invoices: what you change is what gets saved, and the balance / status always follow the facts."""
from datetime import timedelta
from decimal import Decimal as D

import pytest
from django.utils import timezone

from apps.billing.models import Invoice, InvoiceLine, Payment
from apps.crm.models import Client

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


@pytest.fixture
def acct(client):
    signed_in(client, make_user("acct@example.com", role="accounting"))
    return client


def make_invoice(status="Sent", due_in=30, lines=((2, 100),), **kw):
    c = kw.pop("client", None) or Client.objects.create(name="Acme")
    inv = Invoice.objects.create(number=kw.pop("number", "INV-1"), client=c, status=status, invoice_date=TODAY - timedelta(days=5),
                                 due_date=TODAY + timedelta(days=due_in), tax_rate=D("0"), **kw)
    for i, (q, r) in enumerate(lines):
        InvoiceLine.objects.create(invoice=inv, description=f"Line {i}", qty=q, rate=r, sort_order=i)
    inv.recalc()
    return inv


def post(inv, lines=None, extra=(), **over):
    """The edit form as the browser sends it: every existing line, plus any extra (description, qty, rate) rows."""
    lines = list(inv.lines.all()) if lines is None else lines
    d = {"client": inv.client_id, "status": "Sent" if inv.status in Invoice.COMPUTED else inv.status, "invoice_date": str(inv.invoice_date),
         "due_date": str(inv.due_date), "tax_rate": "0", "scope": "", "notes": "",
         "lines-TOTAL_FORMS": str(len(lines) + len(extra)), "lines-INITIAL_FORMS": str(len(lines)), "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "500"}
    for i, ln in enumerate(lines):
        d.update({f"lines-{i}-id": ln.pk, f"lines-{i}-invoice": inv.pk, f"lines-{i}-description": ln.description, f"lines-{i}-qty": str(ln.qty), f"lines-{i}-rate": str(ln.rate)})
    for j, (desc, q, r) in enumerate(extra, len(lines)):
        d.update({f"lines-{j}-invoice": inv.pk, f"lines-{j}-description": desc, f"lines-{j}-qty": q, f"lines-{j}-rate": r})
    d.update(over)
    return d


def test_changing_a_line_on_a_paid_invoice_reopens_the_balance(acct):
    inv = make_invoice()
    Payment.objects.create(invoice=inv, amount=D("200"), paid_on=TODAY)
    inv.refresh_from_db()
    assert inv.status == "Paid"
    ln = inv.lines.get()
    r = acct.post(f"/m/invoices/{inv.pk}/", post(inv, **{"lines-0-rate": "150"}))
    assert r.status_code == 204, r.content[:400]
    inv.refresh_from_db()
    assert (inv.total, inv.amount_paid, inv.status, inv.balance) == (D("300.00"), D("200.00"), "Partial", D("100.00"))
    acct.post(f"/m/invoices/{inv.pk}/", post(inv, **{"lines-0-rate": "50"}))   # and back down below what was paid
    inv.refresh_from_db()
    assert (inv.total, inv.status) == (D("100.00"), "Paid") and ln.pk == inv.lines.get().pk


def test_moving_the_due_date_clears_or_sets_overdue(acct):
    inv = make_invoice(status="Overdue", due_in=-10)
    acct.post(f"/m/invoices/{inv.pk}/", post(inv, due_date=str(TODAY + timedelta(days=14))))
    inv.refresh_from_db()
    assert inv.status == "Sent"
    acct.post(f"/m/invoices/{inv.pk}/", post(inv, due_date=str(TODAY - timedelta(days=1))))
    inv.refresh_from_db()
    assert inv.status == "Overdue"


def test_status_cannot_be_typed_to_paid_and_the_paid_amount_is_not_a_form_field(acct):
    inv = make_invoice()
    html = acct.get(f"/m/invoices/{inv.pk}/", HTTP_HX_REQUEST="true").content.decode()
    assert 'name="amount_paid"' not in html and "use Record payment" in html and ">Open (Sent)<" in html
    r = acct.post(f"/m/invoices/{inv.pk}/", post(inv, status="Paid", amount_paid="200"))
    assert r.status_code == 422                       # "Paid" isn't something you pick
    inv.refresh_from_db()
    assert inv.status == "Sent" and not inv.amount_paid


def test_money_typed_with_dollar_signs_and_commas_saves(acct):
    inv = make_invoice()
    r = acct.post(f"/m/invoices/{inv.pk}/", post(inv, extra=[("Server", "", "$1,250.50")]))
    assert r.status_code == 204, r.content[:400]
    inv.refresh_from_db()
    assert inv.total == D("1450.50") and inv.lines.get(description="Server").qty == 1   # blank quantity means one


def test_a_bad_line_says_so_instead_of_silently_not_saving(acct):
    inv = make_invoice()
    r = acct.post(f"/m/invoices/{inv.pk}/", post(inv, extra=[("Cable", "abc", "12")]))
    html = r.content.decode()
    assert r.status_code == 422 and "Not saved yet" in html and "Enter a number" in html
    r = acct.post(f"/m/invoices/{inv.pk}/", post(inv, due_date=str(inv.invoice_date - timedelta(days=1))))
    assert r.status_code == 422 and b"due date is before the invoice date" in r.content


def test_new_lines_go_to_the_bottom_in_the_order_typed(acct):
    inv = make_invoice(lines=((1, 10), (1, 20), (1, 30)))
    acct.post(f"/m/invoices/{inv.pk}/", post(inv, extra=[("Fourth", "1", "40"), ("Fifth", "1", "50")]))
    assert [ln.description for ln in inv.lines.all()] == ["Line 0", "Line 1", "Line 2", "Fourth", "Fifth"]


def test_removing_a_line_updates_the_total(acct):
    inv = make_invoice(lines=((1, 10), (1, 20)))
    acct.post(f"/m/invoices/{inv.pk}/", post(inv, **{"lines-1-DELETE": "on"}))
    inv.refresh_from_db()
    assert inv.total == D("10.00") and inv.lines.count() == 1


def test_moving_a_payment_fixes_both_invoices(acct):
    a = make_invoice()
    b = make_invoice(number="INV-2", client=a.client)
    p = Payment.objects.create(invoice=a, amount=D("200"), paid_on=TODAY)
    p.invoice = b
    p.save()
    a.refresh_from_db(), b.refresh_from_db()
    assert (a.status, a.amount_paid, b.status, b.amount_paid) == ("Sent", D("0"), "Paid", D("200"))


def test_record_payment_starts_with_the_balance_and_refuses_a_void_invoice(acct):
    inv = make_invoice()
    Payment.objects.create(invoice=inv, amount=D("50"), paid_on=TODAY)
    html = acct.get(f"/m/payments/new/?invoice_id={inv.pk}", HTTP_HX_REQUEST="true").content.decode()
    assert 'value="150.00"' in html
    void = make_invoice(number="INV-V", status="Void", client=inv.client)
    r = acct.post("/m/payments/new/", {"invoice": void.pk, "amount": "10", "method": "Check", "paid_on": str(TODAY), "status": "Succeeded"})
    assert r.status_code == 422 and b"is void" in r.content


def test_voiding_or_archiving_an_invoice_puts_its_time_back_in_ready_to_bill(acct):
    from apps.billing import ready
    from apps.helpdesk.models import Ticket, TimeEntry
    c = Client.objects.create(name="Break Fix Co", hourly_rate=D("100"))
    u = make_user("t@example.com")
    t = Ticket.objects.create(number="T-1", subject="Printer", client=c, billable=True)
    TimeEntry.objects.create(ticket=t, user=u, minutes=60, work_date=TODAY, billable=True)
    inv = ready.create_drafts([c.pk], TODAY)[0]
    assert not ready.collect(TODAY)
    acct.post(f"/m/invoices/{inv.pk}/", post(inv, status="Void"))
    inv.refresh_from_db()
    assert inv.status == "Void" and len(ready.collect(TODAY)) == 1


def test_recurring_invoices_use_the_number_settings():
    from apps.billing.models import RecurringInvoice, RecurringLine
    from apps.core.jobs import overdue_invoices, recurring_invoices
    from apps.core.models import Setting
    Setting.put("numbers.invoice_prefix", "WS-")
    c = Client.objects.create(name="Acme")
    s = RecurringInvoice.objects.create(name="Monthly", client=c, next_run=TODAY, tax_rate=D("0"))
    RecurringLine.objects.create(schedule=s, description="Plan", qty=1, rate=100)
    recurring_invoices()
    assert Invoice.objects.get().number.startswith("WS-")
    # an invoice that is past due but fully paid is not "overdue"
    inv = make_invoice(status="Sent", due_in=-3, client=c)
    Invoice.objects.filter(pk=inv.pk).update(amount_paid=inv.total)
    overdue_invoices()
    inv.refresh_from_db()
    assert inv.status == "Sent"
