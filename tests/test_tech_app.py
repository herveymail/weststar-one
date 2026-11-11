"""Tech app (/tech/) — the phone version for techs."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.helpdesk.models import Ticket, TicketTimer, TimeEntry
from apps.hr.models import TimeclockEntry
from apps.tools.models import CalendarEvent, MileageTrip

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Mobile/15E148 Safari/604.1"


@pytest.fixture
def tech(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin")
    signed_in(client, u)
    return u


@pytest.fixture
def job(tech):
    c = Client.objects.create(name="Desert Dental", phone="(480) 555-0100", address="1250 E Baseline Rd", city="Tempe", state="AZ", zip="85283")
    Contact.objects.create(client=c, name="Pat Lee", phone="602-555-0199", email="pat@dd.test", is_primary=True)
    return Ticket.objects.create(number="T-1", subject="Front desk PC won't boot", client=c, assigned_to=tech, priority="Critical", status="Open")


def test_today_tiles_and_lists(client, tech, job):
    CalendarEvent.objects.create(title="Walk-through", starts_at=timezone.now(), who=tech, client=job.client)
    TimeEntry.objects.create(ticket=job, user=tech, minutes=90, work_date=timezone.localdate())
    r = client.get("/tech/")
    assert r.status_code == 200
    for txt in (b"Jobs today", b"Urgent", b"1.5h", b"Need signature", b"Walk-through", b"Front desk PC", b'rel="manifest"', b"apple-touch-icon"):
        assert txt in r.content, txt


def test_login_required_and_app_files_open(client):
    assert client.get("/tech/").status_code == 302
    m = client.get("/tech/manifest.webmanifest")
    assert m.status_code == 200 and m.json()["start_url"] == "/tech/" and m.json()["display"] == "standalone"
    sw = client.get("/tech/sw.js")
    assert sw.status_code == 200 and sw["Service-Worker-Allowed"] == "/tech/" and b"__ASSETS__" not in sw.content
    assert client.get("/tech/offline/").status_code == 200


def test_ticket_screen_actions(client, tech, job):
    r = client.get(f"/tech/t/{job.pk}/")
    assert b"tel:4805550100" in r.content and b"maps.apple.com" in r.content and b"signoff/?type=completion&back=tech" in r.content
    client.post(f"/tech/t/{job.pk}/", {"action": "timer"})
    assert TicketTimer.objects.filter(ticket=job, user=tech).exists()
    job.refresh_from_db()
    assert job.status == "In progress"
    TicketTimer.objects.filter(ticket=job).update(started_at=timezone.now() - timedelta(minutes=30))
    client.post(f"/tech/t/{job.pk}/", {"action": "timer"})
    assert not TicketTimer.objects.filter(ticket=job).exists() and TimeEntry.objects.filter(ticket=job).exists()
    client.post(f"/tech/t/{job.pk}/", {"action": "note", "kind": "work", "body": "Replaced PSU", "hours": "1", "work_type": "On-site"})
    assert job.messages.filter(kind="work", body="Replaced PSU").exists()
    assert TimeEntry.objects.filter(ticket=job, minutes=60, work_type="On-site").exists()
    client.post(f"/tech/t/{job.pk}/", {"action": "status", "status": "Waiting on client"})
    job.refresh_from_db()
    assert job.status == "Waiting on client"


def test_clock_and_mileage(client, tech, job):
    client.post("/tech/time/", {"action": "clock", "next": "/tech/"})
    assert TimeclockEntry.objects.filter(user=tech, status="Open").exists()
    assert b"Clock out" in client.get("/tech/").content
    client.post("/tech/time/", {"action": "clock"})
    assert TimeclockEntry.objects.get(user=tech).status == "Submitted"
    client.post("/tech/time/", {"action": "mileage", "trip": "Office -> Desert Dental", "miles": "12.4", "client": job.client_id, "billable": "1"})
    m = MileageTrip.objects.get(user=tech)
    assert float(m.miles) == 12.4 and m.billable and m.client == job.client
    client.post("/tech/time/", {"action": "mileage", "trip": "", "miles": "5"})
    assert MileageTrip.objects.count() == 1


def test_ticket_filters(client, tech, job):
    Ticket.objects.create(number="T-2", subject="Unassigned thing", status="New")
    assert b"Unassigned thing" not in client.get("/tech/tickets/").content
    assert b"Unassigned thing" in client.get("/tech/tickets/?f=unassigned").content
    assert b"Front desk" in client.get("/tech/tickets/?q=desert").content


def test_phone_stays_signed_in(client, tech):
    client.get("/tech/", HTTP_USER_AGENT=IPHONE)
    assert client.session.get("tech_app") and client.session.get_expiry_age() > 6 * 86400
    s = client.session
    s["last_seen"] = timezone.now().timestamp() - 3 * 3600  # 3 hours idle: the website would sign out after 30 min
    s.save()
    assert client.get("/tech/", HTTP_USER_AGENT=IPHONE).status_code == 200


def test_desktop_and_setting_off_keep_normal_timeout(client, tech):
    client.get("/tech/")
    assert not client.session.get("tech_app")
    Setting.put("tech.stay_days", "0")
    client.get("/tech/", HTTP_USER_AGENT=IPHONE)
    assert not client.session.get("tech_app")


def test_signoff_returns_to_tech_app(client, tech, job):
    r = client.get(f"/tickets/{job.pk}/signoff/?type=completion&back=tech")
    assert b'name="back" value="tech"' in r.content and f"/tech/t/{job.pk}/".encode() in r.content
