"""Account flags, the client text-message log, offboarding, and blocking email senders."""
import io
import zipfile
from datetime import timedelta
from decimal import Decimal as D

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone

from apps.core.models import Setting
from apps.crm.models import Client, ClientFlag, ClientText, Contact, Offboarding
from apps.helpdesk import inbound, services
from apps.helpdesk.models import Ticket, TimeEntry

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db
TODAY = timezone.localdate()


@pytest.fixture
def boss(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user("boss@example.com", role="admin")
    signed_in(client, u)
    return u


def test_flags_show_on_the_client_and_its_tickets_and_keep_history(client, boss):
    c = Client.objects.create(name="Acme")
    t = services.create_ticket(subject="Printer", client=c)
    client.post(f"/clients/{c.pk}/flags/", {"label": "Past due — get approval before any work", "level": "stop", "note": "Ask Casey"})
    client.post(f"/clients/{c.pk}/flags/", {"label": "Old promo", "level": "info", "expires_on": str(TODAY - timedelta(days=1))})
    assert b"Past due" in client.get(f"/clients/{c.pk}/").content
    page = client.get(f"/tickets/{t.pk}/?classic=1").content.decode()
    assert "Past due" in page and "Ask Casey" in page and "Old promo" not in page
    f = ClientFlag.objects.get(label__startswith="Past due")
    client.post(f"/clients/{c.pk}/flags/", {"clear": f.pk, "clear_note": "Paid up"})
    assert "Past due" not in client.get(f"/tickets/{t.pk}/?classic=1").content.decode()
    hist = client.get(f"/clients/{c.pk}/flags/").content.decode()
    assert "Paid up" in hist and "cleared by Boss" in hist


def test_text_messages_are_filed_with_screenshots(client, boss, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    c = Client.objects.create(name="Acme")
    t = services.create_ticket(subject="After hours", client=c)
    png = SimpleUploadedFile("shot.png", b"\x89PNG\r\n\x1a\n" + b"0" * 64, content_type="image/png")
    r = client.post(f"/clients/{c.pk}/texts/", {"happened_on": str(TODAY), "summary": "Asked for a reset", "contact_name": "Jo", "their_number": "602-555-0100",
                                                "ticket": t.number, "files": png})
    assert r.status_code == 302
    row = ClientText.objects.get()
    assert (row.staff, row.ticket, row.uploads.count()) == (boss, t, 1)
    html = client.get(f"/clients/{c.pk}/texts/").content.decode()
    assert "Asked for a reset" in html and "602-555-0100" in html and f"/files/{row.uploads.get().pk}/" in html
    assert t.messages.filter(kind="event", body__contains="Text messages filed").exists()
    assert b"Add the screenshots" in client.post(f"/clients/{c.pk}/texts/", {"happened_on": str(TODAY), "summary": "x"}).content
    from django.test import Client as Browser
    other = signed_in(Browser(), make_user("tech@example.com", role="tech"))
    assert other.post(f"/clients/{c.pk}/texts/{row.pk}/delete/").status_code == 403


def test_offboarding_checklist_from_start_to_former_client(client, boss, settings, tmp_path):
    from apps.billing.models import Contract, RecurringInvoice
    settings.MEDIA_ROOT = tmp_path
    c = Client.objects.create(name="Acme & Sons", hourly_rate=D("100"))
    Contact.objects.create(client=c, name="Jo", email="jo@acme.test")
    t = services.create_ticket(subject="Printer", client=c, details="It is broken")
    services.add_message(t, user=boss, kind="reply", body="Fixed it")
    services.add_message(t, user=boss, kind="note", body="SECRET INTERNAL NOTE")
    TimeEntry.objects.create(ticket=t, user=boss, minutes=120, work_date=TODAY, billable=True)
    RecurringInvoice.objects.create(name="Monthly", client=c, next_run=TODAY)
    Contract.objects.create(name="MSA", client=c, status="Active")
    client.post(f"/clients/{c.pk}/offboarding/", {"action": "start", "last_day": str(TODAY + timedelta(days=30)), "reason": "Slow payer"})
    ob = Offboarding.objects.get()
    assert c.flags.get().label == "Offboarding" and "Offboarding" in client.get(f"/tickets/{t.pk}/?classic=1").content.decode()
    page = client.get(f"/clients/{c.pk}/offboarding/").content.decode()
    assert "$200.00" in page and "Monthly" in page and "MSA" in page and "Return passwords" in page
    # final invoice, stop billing, export
    r = client.post(f"/clients/{c.pk}/offboarding/", {"action": "final_invoice"})
    assert r["Location"].startswith("/billing/invoice/") and c.invoices.get().total == D("200.00")
    client.post(f"/clients/{c.pk}/offboarding/", {"action": "stop_billing"})
    assert RecurringInvoice.objects.get().status == "Paused" and Contract.objects.get().status == "Cancelled"
    z = zipfile.ZipFile(io.BytesIO(client.get(f"/clients/{c.pk}/offboarding/export/").content))
    names = z.namelist()
    assert {"README.txt", "client.csv", "contacts.csv", "tickets.csv", "invoices.csv", f"tickets/{t.number}.txt"} <= set(names)
    body = z.read(f"tickets/{t.number}.txt").decode()
    assert "Fixed it" in body and "SECRET INTERNAL NOTE" not in body
    assert "stripe" not in z.read("client.csv").decode().lower()
    # can't finish until every step is ticked
    client.post(f"/clients/{c.pk}/offboarding/", {"action": "finish"})
    assert Offboarding.objects.get().status == "Open"
    for key, _t, _h in Offboarding.STEPS:
        client.post(f"/clients/{c.pk}/offboarding/", {"action": "step", "key": key, "done": "1", "note": f"did {key}"})
    assert ob.step_rows.filter(done_by=boss).count() == 6
    client.post(f"/clients/{c.pk}/offboarding/", {"action": "finish"})
    c.refresh_from_db()
    assert c.status == "Former" and Offboarding.objects.get().status == "Done"
    assert [f.label for f in c.active_flags] == ["Former client — do not service"]


def test_only_managers_can_offboard(client):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user("tech@example.com", role="tech"))
    c = Client.objects.create(name="Acme")
    assert client.post(f"/clients/{c.pk}/offboarding/", {"action": "start"}).status_code == 403
    assert client.get(f"/clients/{c.pk}/offboarding/export/").status_code == 403


def test_blocked_senders_never_make_tickets(client, boss):
    def mail(sender, subject="Backup job failed"):
        return (f"From: Old Vendor <{sender}>\r\nTo: support@weststar.test\r\nSubject: {subject}\r\nMessage-ID: <{subject.replace(' ', '')}-{sender}>\r\n\r\nError 42\r\n").encode()
    row = inbound.process_message(mail("alerts@oldvendor.com"))
    t = row.ticket
    assert row.result == "ticket"
    other = inbound.process_message(mail("noc@mail.oldvendor.com", "Disk full")).ticket
    assert "Block alerts@oldvendor.com" in client.get(f"/tickets/{t.pk}/?classic=1").content.decode()
    client.post(f"/tickets/{t.pk}/block-sender/", {"what": "domain"})
    t.refresh_from_db(), other.refresh_from_db()
    assert (t.status, other.status) == ("Closed", "Closed")        # the domain block covers its subdomains too
    assert Setting.get("tickets.blocked_senders") == "oldvendor.com"
    again = inbound.process_message(mail("alerts@oldvendor.com", "Still failing"))
    sub = inbound.process_message(mail("noc@mail.oldvendor.com", "Disk fuller"))
    assert (again.result, sub.result) == ("skipped", "skipped") and "blocked sender" in again.note and Ticket.objects.count() == 2
    assert inbound.process_message(mail("jo@goodclient.com", "Help")).result == "ticket"
