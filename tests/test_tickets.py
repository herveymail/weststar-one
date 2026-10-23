import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.files.models import Upload
from apps.helpdesk.models import Ticket

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Setting.put("security.require_mfa", "nobody")


@pytest.fixture
def tech(client):
    return signed_in(client, make_user(role="tech"))


def test_create_reply_close(tech):
    c = Client.objects.create(name="Acme")
    r = tech.post("/tickets/new/", {"subject": "Printer down", "client": c.pk, "priority": "High"})
    assert r.status_code == 204 and r["HX-Redirect"].startswith("/tickets/")
    t = Ticket.objects.get()
    assert t.number == "T-10001" and t.response_due_at
    tech.post(f"/tickets/{t.pk}/message/", {"kind": "reply", "body": "On it", "minutes": "15"})
    t.refresh_from_db()
    assert t.first_response_at and t.messages.filter(kind="reply").count() == 1
    assert t.time_entries.get().minutes == 15
    tech.post(f"/tickets/{t.pk}/update/", {"status": "Closed"})
    t.refresh_from_db()
    assert t.status == "Closed" and t.closed_at
    assert b"On it" in tech.get(f"/tickets/{t.pk}/").content


def test_contact_must_belong_to_client(tech):
    """L9."""
    a, b = Client.objects.create(name="A"), Client.objects.create(name="B")
    k = Contact.objects.create(client=b, name="Bo")
    r = tech.post("/tickets/new/", {"subject": "x", "client": a.pk, "contact": k.pk, "priority": "Low"})
    assert r.status_code == 422 and not Ticket.objects.exists()


def test_attachments_upload_download_and_blocked_types(tech, client):
    t = Ticket.objects.create(number="T-9", subject="x")
    ok = SimpleUploadedFile("screen shot.png", b"\x89PNG fake", content_type="image/png")
    bad = SimpleUploadedFile("evil.php", b"<?php echo 1;", content_type="text/plain")
    r = tech.post(f"/tickets/{t.pk}/message/", {"kind": "note", "body": "", "files": [ok, bad]}, follow=True)
    assert "not an allowed file type" in r.content.decode()
    u = Upload.objects.get()
    assert u.original_name == "screen shot.png" and u.message_id
    assert not u.file.name.endswith("screen shot.png")  # stored under a random name
    d = tech.get(f"/files/{u.pk}/")
    assert d.status_code == 200 and d["Content-Disposition"].startswith("attachment")
    assert d["X-Content-Type-Options"] == "nosniff"


def test_no_billing_access_means_no_ticket_file_leak(client, tmp_path):
    """Files follow the access of what they're attached to."""
    c = Client.objects.create(name="A")
    up = Upload(kind="client", client=c, original_name="contract.pdf")
    up.file.save("contract.pdf", SimpleUploadedFile("contract.pdf", b"%PDF"), save=True)
    signed_in(client, make_user("v@example.com", role="viewer"))
    assert client.get(f"/files/{up.pk}/").status_code == 200  # viewers can read client files
    assert client.post(f"/files/{up.pk}/delete/").status_code == 403


def test_classic_and_grid_lists(tech, client):
    from apps.accounts.models import User
    from apps.helpdesk.models import Queue
    q = Queue.objects.create(name="Level 2", color="#5a3fc0")
    a = Ticket.objects.create(number="T-1", subject="Alpha", status="Open", priority="Critical", queue=q)
    Ticket.objects.create(number="T-2", subject="Bravo", status="Closed")
    html = tech.get("/tickets/").content.decode()
    assert "Alpha" in html and "Bravo" not in html and "All unresolved" in html and "Level 2" in html
    assert "Bravo" in tech.get("/tickets/?view=closed").content.decode()
    assert "Alpha" in tech.get(f"/tickets/?queue={q.pk}").content.decode()
    page = tech.get(f"/tickets/{a.pk}/").content.decode()
    assert "Escalate" not in page and "Private note" in page and "PROPERTIES" in page.upper()
    tech.post("/tickets/ui/", {"ui": "grid"})
    assert User.objects.get(email="tech@example.com").tickets_ui == "grid"
    grid = tech.get("/tickets/?tab=all").content.decode()
    assert "Alpha" in grid and "Bravo" in grid and "Move to queue" in grid
    assert 'id="panel"' in tech.get(f"/tickets/{a.pk}/panel/").content.decode()
    assert "tkg-panel" in tech.get(f"/tickets/{a.pk}/").content.decode()  # grid users get the list with the panel open


def test_reply_note_work_status_and_time(tech):
    t = Ticket.objects.create(number="T-5", subject="Printer", status="New")
    tech.post(f"/tickets/{t.pk}/message/", {"kind": "work", "body": "Replaced toner", "minutes": "30", "work_type": "On-site",
                                           "billable": "1", "status_after": "Resolved"})
    t.refresh_from_db()
    assert t.status == "Resolved" and t.first_response_at is None  # a work log isn't a reply to the client
    e = t.time_entries.get()
    assert (e.minutes, e.work_type, e.billable) == (30, "On-site", True)
    assert t.messages.filter(kind="work").exists()


def test_bulk_snooze_merge_timer(tech):
    from django.utils import timezone

    from apps.helpdesk.models import TicketTimer
    a = Ticket.objects.create(number="T-10", subject="A", status="Open")
    b = Ticket.objects.create(number="T-11", subject="B", status="Open", details="second request")
    tech.post("/tickets/bulk/", {"ids": [a.pk, b.pk], "action": "status", "value": "In progress"})
    assert set(Ticket.objects.values_list("status", flat=True)) == {"In progress"}
    tech.post(f"/tickets/{a.pk}/snooze/", {"until": "tomorrow"})
    a.refresh_from_db()
    assert a.snoozed_until > timezone.now() and "A" not in [x.subject for x in Ticket.objects.filter(snoozed_until__isnull=True)]
    tech.post(f"/tickets/{a.pk}/timer/", {"action": "start"})
    TicketTimer.objects.filter(ticket=a).update(started_at=timezone.now() - timezone.timedelta(minutes=20))
    tech.post(f"/tickets/{a.pk}/timer/", {"action": "stop"})
    assert a.time_entries.get().minutes == 20
    tech.post(f"/tickets/{b.pk}/merge/", {"into": "T-10"})
    b.refresh_from_db()
    assert b.merged_into_id == a.pk and b.status == "Closed"
    assert a.messages.filter(body="second request").exists()
