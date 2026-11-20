"""Business hours on service calls: required on every call, due times in office hours, client hours shown on tickets."""
import datetime as dt
from zoneinfo import ZoneInfo

import pytest

from apps.core.models import Setting
from apps.crm.models import Client
from apps.helpdesk import hours, services
from apps.helpdesk.models import Ticket

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db
TZ = ZoneInfo("America/Phoenix")


@pytest.fixture
def office():
    Setting.put("app.timezone", "America/Phoenix")
    Setting.put("helpdesk.open", "08:00")
    Setting.put("helpdesk.close", "17:00")
    Setting.put("helpdesk.days", "Mon,Tue,Wed,Thu,Fri")
    return hours.office()


def at(day, hh, mm=0):  # November 2026: the 20th is a Friday
    return dt.datetime(2026, 11, day, hh, mm, tzinfo=TZ)


def test_due_times_only_count_office_hours(office):
    assert office.label() == "Mon–Fri · 8 AM – 5 PM"
    assert office.add(at(20, 16), 240).astimezone(TZ) == at(23, 11)          # Fri 4 PM + 4 h → Mon 11 AM
    assert office.add(at(20, 10), 60).astimezone(TZ) == at(20, 11)           # same day
    assert office.add(at(21, 13), 30).astimezone(TZ) == at(23, 8, 30)        # Saturday → Monday 8:30
    assert office.add(at(20, 6), 30).astimezone(TZ) == at(20, 8, 30)         # before opening
    assert office.add(at(20, 9), 24 * 60).astimezone(TZ) == at(24, 15)       # 24 working hours = 2 days + 6 h
    assert hours.due(at(20, 16), 240, "Critical").astimezone(TZ) == at(20, 20)   # critical runs around the clock
    Setting.put("tickets.sla_business_hours", "false")
    assert hours.due(at(20, 16), 240, "Low").astimezone(TZ) == at(20, 20)


def test_new_tickets_get_office_hour_deadlines(office, monkeypatch):
    monkeypatch.setattr(services.timezone, "now", lambda: at(20, 16, 30))
    t = services.create_ticket(subject="Printer", priority="High")
    mins = services.response_minutes("High", None)
    assert t.response_due_at == office.add(at(20, 16, 30), mins) and t.response_due_at.astimezone(TZ).date() >= dt.date(2026, 11, 20)
    assert t.resolve_due_at.astimezone(TZ).weekday() < 5 and t.resolve_due_at.astimezone(TZ) > at(23, 8)


def test_client_hours_show_on_the_ticket_and_fill_new_calls(client, office, settings):
    settings.REQUIRE_TICKET_HOURS = True
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user("tech@example.com", role="admin"))
    c = Client.objects.create(name="Acme", hours_open=dt.time(9), hours_close=dt.time(18), hours_days="Mon,Tue,Wed,Thu", hours_timezone="America/Denver",
                              hours_note="Closed for lunch 12–1")
    assert hours.client_text(c) == "Mon–Thu · 9 AM – 6 PM (Mountain time) — Closed for lunch 12–1"
    r = client.post("/tickets/new/", {"client": c.pk, "subject": "Printer", "priority": "Low"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204                      # blank is fine: the client has hours saved
    t = Ticket.objects.get()
    assert t.site_hours.startswith("Mon–Thu · 9 AM – 6 PM")
    page = client.get(f"/tickets/{t.pk}/?classic=1").content.decode()
    assert "Business hours:" in page and "Closed for lunch" in page and ("Open now" in page or "Closed now" in page)


def test_hours_are_required_when_the_client_has_none_and_then_remembered(client, office, settings):
    settings.REQUIRE_TICKET_HOURS = True
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user("tech@example.com", role="admin"))
    c = Client.objects.create(name="NoHours Inc")
    r = client.post("/tickets/new/", {"client": c.pk, "subject": "Printer", "priority": "Low"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 422 and b"Add the client&#x27;s business hours" in r.content
    r = client.post("/tickets/new/", {"client": c.pk, "subject": "Printer", "priority": "Low", "site_hours": "Mon-Fri 8-5"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204
    c.refresh_from_db()
    assert c.hours_note == "Mon-Fri 8-5" and Ticket.objects.get().site_hours == "Mon-Fri 8-5"
    # an email ticket for a client with nothing saved shows the prompt, and a tech can fill it in
    d = Client.objects.create(name="Email Only")
    e = services.create_ticket(subject="Help", client=d, source="Email", contact_email="jo@x.test")
    assert "No business hours on this call" in client.get(f"/tickets/{e.pk}/?classic=1").content.decode()
    client.post(f"/tickets/{e.pk}/hours/", {"site_hours": "Tue–Sat 10–6"})
    e.refresh_from_db(), d.refresh_from_db()
    assert e.site_hours == "Tue–Sat 10–6" and d.hours_note == "Tue–Sat 10–6"


def test_clients_see_our_hours_and_must_give_theirs(office, settings, client, tmp_path):
    from tests.test_portal import make_pu, sign_in
    settings.REQUIRE_TICKET_HOURS = True
    settings.MEDIA_ROOT = tmp_path
    c = Client.objects.create(name="Acme")
    make_pu(c)
    sign_in(client)
    page = client.get("/client-portal/tickets/").content.decode()
    assert "Our office hours: Mon–Fri · 8 AM – 5 PM" in page and 'name="site_hours"' in page and "required" in page
    r = client.post("/client-portal/tickets/", {"subject": "Printer", "priority": "Low"})
    assert r.status_code == 400 and b"Tell us your business hours" in r.content and not Ticket.objects.exists()
    r = client.post("/client-portal/tickets/", {"subject": "Printer", "priority": "Low", "site_hours": "Mon–Fri 9–5"})
    assert r.status_code == 302 and Ticket.objects.get().site_hours == "Mon–Fri 9–5"
    # next time it is filled in for them
    assert 'value="Mon–Fri 9–5"' in client.get("/client-portal/tickets/").content.decode()
