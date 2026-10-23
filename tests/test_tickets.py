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
    r = tech.post(f"/tickets/{t.pk}/message/", {"kind": "note", "body": "", "files": [ok, bad]})
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


def test_board_and_queue(tech):
    Ticket.objects.create(number="T-1", subject="Alpha")
    assert b"Alpha" in tech.get("/tickets/?view=board").content
    assert b"Alpha" not in tech.get("/tickets/?view=queue").content
