from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import Setting
from apps.crm.models import Client
from apps.helpdesk import services
from apps.helpdesk.models import Ticket

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


def test_dashboard_live_numbers(client):
    Setting.put("security.require_mfa", "nobody")
    u = signed_in(client, make_user(role="admin"))
    c = Client.objects.create(name="Acme")
    late = services.create_ticket(subject="Server down", details="", client=c, priority="Critical")
    Ticket.objects.filter(pk=late.pk).update(response_due_at=timezone.now() - timedelta(minutes=30))
    services.create_ticket(subject="Printer", details="", client=c, priority="Low")
    r = u.get("/")
    assert r.status_code == 200 and b"Needs attention" in r.content and b"Server down" in r.content
    live = u.get("/?part=live", HTTP_HX_REQUEST="true")
    assert b"past SLA" in live.content and b"SLA over" in live.content and b"<html" not in live.content


def test_logo_upload_and_public_serve(client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Setting.put("security.require_mfa", "nobody")
    from django.core.files.uploadedfile import SimpleUploadedFile
    signed_in(client, make_user(role="admin"))
    bad = SimpleUploadedFile("x.svg", b'<svg onload="alert(1)"></svg>', content_type="image/svg+xml")
    r = client.post("/settings/branding/", {"brand.logo": bad}, follow=True)
    assert b"scripts or links" in r.content
    png = SimpleUploadedFile("logo.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, content_type="image/png")
    client.post("/settings/branding/", {"brand.logo": png})
    client.logout()
    login = client.get("/login/")
    assert b"/brand/logo/" in login.content
    img = client.get("/brand/logo/")
    assert img.status_code == 200 and img["Content-Type"] == "image/png" and "sandbox" in img["Content-Security-Policy"]
