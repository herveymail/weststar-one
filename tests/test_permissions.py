import pytest

from apps.billing.models import Invoice
from apps.core.models import AuditLog, Setting
from apps.crm.models import Client
from apps.hr.models import Employee, TimeOffRequest

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_mfa_policy():
    Setting.put("security.require_mfa", "nobody")


def test_tech_cannot_open_billing_or_settings(client):
    signed_in(client, make_user(role="tech"))
    assert client.get("/m/invoices/").status_code == 403
    assert client.get("/settings/audit/").status_code == 403
    assert client.get("/hr/").status_code == 403
    assert client.get("/tickets/").status_code == 200


def test_menu_hides_what_you_cannot_open(client):
    signed_in(client, make_user(role="tech"))
    html = client.get("/").content.decode()
    assert 'href="/m/invoices/"' not in html and 'href="/tickets/"' in html


def test_viewer_cannot_change_tickets(client):
    from apps.helpdesk.models import Ticket
    t = Ticket.objects.create(number="T-1", subject="x")
    signed_in(client, make_user(role="viewer"))
    assert client.post(f"/tickets/{t.pk}/update/", {"status": "Closed"}).status_code == 403
    assert client.post(f"/tickets/{t.pk}/message/", {"body": "hi"}).status_code == 403


def test_secrets_not_in_lists_and_reveal_is_audited(client):
    from apps.core.models import set_secret
    admin = make_user("boss@example.com", role="admin")
    e = Employee(name="Pat")
    set_secret(e, "ssn", "123-45-6789")
    e.save()
    signed_in(client, admin)
    assert b"123-45-6789" not in client.get("/hr/").content
    assert b"123-45-6789" not in client.get(f"/m/employees/{e.pk}/").content
    r = client.post(f"/m/employees/{e.pk}/reveal/ssn/")
    assert b"123-45-6789" in r.content
    assert AuditLog.objects.filter(action="reveal", entity="employees").exists()


def test_tech_cannot_reveal_hr_secret(client):
    e = Employee.objects.create(name="Pat")
    signed_in(client, make_user(role="tech"))
    assert client.post(f"/m/employees/{e.pk}/reveal/ssn/").status_code == 403


def test_time_off_is_private_and_cannot_be_self_approved(client):
    """M3: you see only your own requests, can't set the status, and can't edit once approved."""
    me, other = make_user("me@example.com"), make_user("other@example.com")
    mine = TimeOffRequest.objects.create(user=me, starts_on="2026-11-02", ends_on="2026-11-03", hours=8)
    theirs = TimeOffRequest.objects.create(user=other, starts_on="2026-11-02", ends_on="2026-11-03", hours=8)
    signed_in(client, me)
    assert client.get(f"/m/pto/{theirs.pk}/").status_code == 404
    form = client.get(f"/m/pto/{mine.pk}/").content.decode()
    assert 'name="status"' not in form
    client.post(f"/m/pto/{mine.pk}/", {"kind": "Vacation", "starts_on": "2026-11-02", "ends_on": "2026-11-04", "hours": "16", "status": "Approved"})
    mine.refresh_from_db()
    assert mine.status == "Pending" and mine.hours == 16
    TimeOffRequest.objects.filter(pk=mine.pk).update(status="Approved")
    assert client.post(f"/m/pto/{mine.pk}/", {"kind": "Vacation", "starts_on": "2026-11-02", "ends_on": "2026-11-09", "hours": "60"}).status_code == 403


def test_my_hr_shows_only_my_rows_even_for_hr(client):
    hr = make_user("hr@example.com", role="manager", hr_access=True)
    other = make_user("other@example.com")
    TimeOffRequest.objects.create(user=other, starts_on="2026-11-02", ends_on="2026-11-03", hours=8, reason="SECRET-REASON")
    signed_in(client, hr)
    r = client.get("/my-hr/?tab=pto", HTTP_HX_REQUEST="true")
    assert b"SECRET-REASON" not in r.content


def test_audit_log_only_shows_areas_you_can_see(client):
    """M2: managers without H/R access don't see H/R audit entries."""
    AuditLog.objects.create(action="reveal", entity="employees", area="hr", summary="HR-ONLY-ENTRY")
    AuditLog.objects.create(action="update", entity="clients", area="clients", summary="CLIENT-ENTRY")
    mgr = make_user("mgr@example.com", role="manager")
    signed_in(client, mgr)
    html = client.get("/settings/audit/").content
    assert b"CLIENT-ENTRY" in html and b"HR-ONLY-ENTRY" not in html


def test_invoice_number_and_totals_are_calculated(client):
    c = Client.objects.create(name="Acme")
    signed_in(client, make_user("acct@example.com", role="accounting"))
    r = client.post("/m/invoices/new/", {
        "client": c.pk, "status": "Draft", "invoice_date": "2026-10-01", "due_date": "2026-10-31", "tax_rate": "8.6", "amount_paid": "0",
        "subtotal": "1", "total": "999999",  # ignored: totals always come from the lines
        "lines-TOTAL_FORMS": "2", "lines-INITIAL_FORMS": "0", "lines-MIN_NUM_FORMS": "0", "lines-MAX_NUM_FORMS": "1000",
        "lines-0-description": "Labor", "lines-0-qty": "2", "lines-0-rate": "125", "lines-0-taxable": "",
        "lines-1-description": "Switch", "lines-1-qty": "1", "lines-1-rate": "100", "lines-1-taxable": "on",
    })
    assert r.status_code == 204, r.content[:500]
    inv = Invoice.objects.get()
    assert inv.number == "INV-1001"
    from decimal import Decimal as D
    assert (inv.subtotal, inv.tax_amount, inv.total) == (D("350.00"), D("8.60"), D("358.60"))


def test_new_numbers_follow_prefix_and_padding(client):
    from apps.core.numbering import next_number
    Setting.put("numbers.ticket_prefix", "ITDS-")
    Setting.put("numbers.ticket_padding", "5")
    from apps.core.models import Counter
    Counter.at_least("ticket", 917)
    assert next_number("ticket") == "ITDS-00918"
