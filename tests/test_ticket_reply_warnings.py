"""A tech is told when a reply did not reach the client, and typed time is never dropped silently."""
import pytest

from apps.helpdesk import services
from apps.helpdesk.models import TimeEntry

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


def test_time_is_read_the_way_people_type_it():
    p = services.parse_minutes
    assert (p("1.5", "hours"), p("90"), p("90m"), p("1h 30m"), p("1:30"), p("1.5 hrs"), p(""), p("0,25", "hours")) == (90, 90, 90, 90, 90, 90, 0, 15)
    assert p("soon") is None


def test_reply_with_no_client_email_warns_the_tech(client):
    signed_in(client, make_user("tech@example.com", role="tech"))
    t = services.create_ticket(subject="Printer", contact_name="Walk-in")
    r = client.post(f"/tickets/{t.pk}/message/", {"kind": "reply", "body": "On my way", "minutes": "1:30"}, follow=True)
    html = r.content.decode()
    assert "NOT emailed to the client" in html and "no email address on this ticket" in html
    assert TimeEntry.objects.get(ticket=t).minutes == 90
    assert t.messages.filter(kind="event", body__contains="NOT emailed").exists()
    r = client.post(f"/tickets/{t.pk}/message/", {"kind": "note", "body": "x", "minutes": "a while"}, follow=True)
    assert "Time NOT logged" in r.content.decode() and TimeEntry.objects.filter(ticket=t).count() == 1
