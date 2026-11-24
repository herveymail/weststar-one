"""A contractor login limited to certain clients: sees and works only their tickets, and nothing else in the system."""
from decimal import Decimal as D

import pytest
from django.test import Client as Browser

from apps.core import scope
from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.helpdesk import services
from apps.helpdesk.models import Ticket, TimeEntry

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def world():
    Setting.put("security.require_mfa", "nobody")
    a, b, c = Client.objects.create(name="Alpha Dental"), Client.objects.create(name="Beta Law"), Client.objects.create(name="Gamma Secret")
    Contact.objects.create(client=a, name="Ann", email="ann@alpha.test")
    Contact.objects.create(client=c, name="Gus", email="gus@gamma.test")
    ta = services.create_ticket(subject="Alpha printer", client=a, contact_email="ann@alpha.test")
    tb = services.create_ticket(subject="Beta wifi", client=b)
    tc = services.create_ticket(subject="Gamma payroll server", client=c, contact_email="gus@gamma.test")
    con = make_user("contractor@example.com", role="tech", name="Connie Contractor")
    con.scoped_clients.set([a, b])
    return {"a": a, "b": b, "c": c, "ta": ta, "tb": tb, "tc": tc, "con": con, "web": signed_in(Browser(), con)}


def test_sees_only_their_clients_tickets(world):
    w = world["web"]
    page = w.get("/tickets/").content.decode()
    assert "Alpha printer" in page and "Beta wifi" in page and "Gamma" not in page
    assert w.get(f"/tickets/{world['ta'].pk}/?classic=1").status_code == 200
    assert w.get(f"/tickets/{world['tc'].pk}/").status_code == 404
    assert w.get(f"/tickets/{world['tc'].pk}/panel/").status_code == 404
    assert w.post(f"/tickets/{world['tc'].pk}/message/", {"kind": "note", "body": "peek"}).status_code == 404
    assert not world["tc"].messages.filter(body="peek").exists()
    # the tech phone app too
    assert "Gamma" not in w.get("/tech/tickets/").content.decode() and w.get(f"/tech/t/{world['tc'].pk}/").status_code == 404
    assert scope.current() is None                      # the limit never leaks past the request


def test_can_do_the_work_on_their_tickets(world):
    w, t = world["web"], world["ta"]
    r = w.post(f"/tickets/{t.pk}/message/", {"kind": "worklog", "body": "Replaced the drum", "minutes": "45", "billable": "on"})
    assert r.status_code in (200, 204, 302)
    e = TimeEntry.objects.get(ticket=t)
    assert (e.minutes, e.billable, e.user) == (45, True, world["con"])
    w.post(f"/tickets/{t.pk}/update/", {"field": "status", "value": "Resolved", "resolution": "Fixed"})
    # a new ticket: only their clients are offered, and another client's id is refused
    form = w.get("/tickets/new/", HTTP_HX_REQUEST="true").content.decode()
    assert "Alpha Dental" in form and "Beta Law" in form and "Gamma Secret" not in form
    r = w.post("/tickets/new/", {"client": world["c"].pk, "subject": "Sneaky", "priority": "Low"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 422 and not Ticket.objects.filter(subject="Sneaky").exists()
    r = w.post("/tickets/new/", {"client": world["b"].pk, "subject": "Beta new PC", "priority": "Low"}, HTTP_HX_REQUEST="true")
    assert r.status_code == 204 and Ticket.objects.get(subject="Beta new PC").client == world["b"]
    # the time they logged is waiting for accounting in Ready to bill
    from apps.billing import ready
    world["a"].hourly_rate = D("100")
    world["a"].save()
    assert [g["client"].name for g in ready.collect()] == ["Alpha Dental"]


def test_everything_else_is_closed(world):
    w = world["web"]
    for url in ("/", "/clients/", f"/clients/{world['c'].pk}/", "/m/invoices/", "/billing/ready/", "/settings/", "/settings/users/", "/m/contacts/", "/reports/", "/m/clients/"):
        r = w.get(url)
        assert r.status_code == 302 and r["Location"] == "/tickets/", url
    assert w.get("/search/?q=Gamma", HTTP_HX_REQUEST="true").status_code == 403
    assert w.post("/m/clients/new/", {"name": "X"}).status_code == 403
    page = w.get("/tickets/").content.decode()
    assert 'href="/settings/"' not in page and "/m/invoices/new/" not in page and 'href="/m/clients/"' not in page
    assert w.get("/profile/").status_code == 200


def test_normal_staff_are_untouched_and_alerts_respect_the_limit(world, monkeypatch):
    tech = make_user("tech@example.com", role="tech")
    w = signed_in(Browser(), tech)
    assert "Gamma payroll server" in w.get("/tickets/").content.decode() and w.get("/clients/").status_code == 200
    world["con"].ticket_alerts = "all"
    world["con"].save()
    assert "contractor@example.com" not in services.staff_alert_recipients(world["tc"])
    assert "contractor@example.com" in services.staff_alert_recipients(world["ta"])


def test_admin_sets_it_on_the_user_and_admins_cannot_be_limited(world):
    Setting.put("security.require_mfa", "nobody")
    boss = make_user("boss@example.com", role="admin")
    w = signed_in(Browser(), boss)
    u = make_user("new@example.com", role="tech", name="New Person")
    data = {"action": "save", "name": "New Person", "email": "new@example.com", "role": "tech", "scoped_clients": [world["a"].pk]}
    assert w.post(f"/settings/users/{u.pk}/", data).status_code in (200, 204)
    assert list(u.scoped_clients.all()) == [world["a"]]
    assert "Contractor · 1 client" in w.get("/settings/users/").content.decode()
    # any role can be limited: a manager is still kept to their clients and out of everything else
    assert w.post(f"/settings/users/{u.pk}/", {**data, "role": "manager"}).status_code in (200, 204)
    u.refresh_from_db()
    assert u.role == "manager" and list(u.scoped_clients.all()) == [world["a"]]
    m = signed_in(Browser(), u)
    page = m.get("/tickets/").content.decode()
    assert "Alpha printer" in page and "Beta wifi" not in page and "Gamma" not in page
    assert m.get("/settings/users/")["Location"] == "/tickets/" and m.get("/m/invoices/")["Location"] == "/tickets/"
    assert m.get(f"/tickets/{world['tc'].pk}/").status_code == 404
    # but an admin can't lock themselves out of Settings
    r = w.post(f"/settings/users/{boss.pk}/", {"action": "save", "name": boss.name, "email": boss.email, "role": "admin", "scoped_clients": [world["a"].pk]})
    assert b"limit your own sign-in" in r.content and not boss.scoped_clients.exists()


def test_nothing_about_other_clients_leaks_on_any_screen_they_can_open(world, settings, tmp_path):
    from django.core.files.base import ContentFile
    from django.utils import timezone

    from apps.files.models import Upload
    from apps.tools.models import CalendarEvent
    settings.MEDIA_ROOT = tmp_path
    boss = make_user("boss2@example.com", role="admin", name="Boss Two")
    tc, ta, w = world["tc"], world["ta"], world["web"]
    services.add_message(tc, user=boss, kind="reply", body="Gamma confidential reply")
    TimeEntry.objects.create(ticket=tc, user=world["con"], minutes=30, work_date=timezone.localdate(), billable=True, description="Gamma time")
    CalendarEvent.objects.create(title="Gamma onsite visit", starts_at=timezone.now(), who=world["con"], client=world["c"])
    up = Upload(kind="ticket", ticket=tc, original_name="gamma-secret.txt", size=3, content_type="text/plain", uploaded_by=boss)
    up.file.save("gamma-secret.txt", ContentFile(b"abc"))
    up.save()
    for url in ("/tickets/", "/tickets/?view=all", "/tickets/?q=Gamma", "/tickets/?status=all&classic=1", f"/tickets/?client={world['c'].pk}", "/tech/", "/tech/tickets/",
                "/tech/tickets/?q=Gamma", "/tech/schedule/", "/tech/time/", "/tech/me/", f"/tickets/{ta.pk}/?classic=1", f"/tickets/{ta.pk}/panel/", "/profile/"):
        r = w.get(url)
        assert r.status_code == 200, (url, r.status_code)
        body = r.content.decode()
        for secret in ("Gamma Secret", "payroll server", "Gamma confidential", "Gamma onsite", "Gamma time", "gamma-secret", "gus@gamma.test", tc.number):
            i = body.find(secret)
            assert i < 0, (url, secret, body[max(0, i - 160):i + 80])
    assert w.get(f"/files/{up.pk}/").status_code == 404
    assert "gamma-secret" not in w.get(f"/files/ticket/{tc.pk}/").content.decode()
    # can't merge one of their tickets into another client's ticket, or read it that way
    w.post(f"/tickets/{ta.pk}/merge/", {"into": tc.number, "target": tc.number, "number": tc.number})
    ta.refresh_from_db()
    assert ta.merged_into_id is None


def test_a_contractor_cannot_be_given_another_clients_ticket(world):
    boss = make_user("boss3@example.com", role="admin", name="Boss Three")
    services.update_ticket(world["tc"], user=boss, assigned_to=world["con"])
    world["tc"].refresh_from_db()
    assert world["tc"].assigned_to is None and world["tc"].messages.filter(kind="event", body__contains="limited to other clients").exists()
    services.update_ticket(world["ta"], user=boss, assigned_to=world["con"])
    world["ta"].refresh_from_db()
    assert world["ta"].assigned_to == world["con"]
