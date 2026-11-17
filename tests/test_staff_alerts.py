"""Email the team when a new ticket is waiting."""
import pytest

from apps.core import mail
from apps.core.models import Setting
from apps.helpdesk import services
from apps.helpdesk.models import Ticket

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.fixture
def sent(monkeypatch):
    out = []
    monkeypatch.setattr(mail, "configured", lambda: True)
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: out.append({"to": to, "subject": subject, "tpl": tpl, "headers": kw.get("headers")}) or True)
    return out


@pytest.fixture
def team():
    Setting.put("email.support_address", "help@weststar.test")
    return {
        "tech": make_user(email="tech@weststar.test", role="tech"),
        "desk": make_user(email="desk@weststar.test", role="help_desk"),
        "quiet": make_user(email="quiet@weststar.test", role="tech", ticket_alerts="none"),
        "minefan": make_user(email="mine@weststar.test", role="tech", ticket_alerts="mine"),
        "sales": make_user(email="sales@weststar.test", role="sales"),
        "boss": make_user(email="boss@weststar.test", role="admin"),
    }


def _alerts(sent):
    return [s for s in sent if s["tpl"] == "email/staff_new_ticket"]


def test_new_ticket_from_a_client_emails_the_techs(team, sent):
    Setting.put("tickets.staff_alert_to", "techs@weststar.test, help@weststar.test")
    services.create_ticket(subject="Printer offline", source="Email", contact_email="pat@client.test", contact_name="Pat")
    a = _alerts(sent)
    assert len(a) == 1
    assert sorted(a[0]["to"]) == sorted(["tech@weststar.test", "desk@weststar.test", "boss@weststar.test", "techs@weststar.test"])
    assert a[0]["subject"].startswith("[New ticket] T") and "Printer offline" in a[0]["subject"]
    assert a[0]["headers"]["Auto-Submitted"] == "auto-generated"  # so the inbox never turns it into a ticket


def test_assigned_ticket_goes_only_to_that_tech(team, sent):
    services.create_ticket(subject="Laptop", source="Portal", assigned_to=team["minefan"])
    assert [s["to"] for s in _alerts(sent)] == [["mine@weststar.test"]]


def test_staff_typed_tickets_and_switches(team, sent):
    services.create_ticket(subject="Typed in", user=team["boss"])
    assert _alerts(sent) == []
    Setting.put("tickets.staff_alert_which", "all")
    services.create_ticket(subject="Typed in", user=team["boss"])
    assert "boss@weststar.test" not in _alerts(sent)[0]["to"]  # not to the person who made it
    sent.clear()
    Setting.put("tickets.staff_alert_monitoring", "false")
    services.create_ticket(subject="Backup failed", source="Alert")
    assert _alerts(sent) == []
    Setting.put("tickets.staff_alert", "false")
    services.create_ticket(subject="Anything", source="Email")
    assert _alerts(sent) == []


def test_profile_choice(client, team):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, team["tech"])
    page = client.get("/profile/")
    assert b"Email me about new tickets" in page.content
    assert Ticket.objects.count() == 0
