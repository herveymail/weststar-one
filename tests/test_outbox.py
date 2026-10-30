"""Ticket emails go through the outbox so closing or replying doesn't wait on the mail server."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core import mail
from apps.core.models import OutboxEmail, Setting
from apps.helpdesk import services
from apps.helpdesk.models import TicketMessage

from .helpers import make_user

pytestmark = pytest.mark.django_db


@pytest.fixture
def queued(settings, monkeypatch):
    settings.MAIL_BACKGROUND = True
    monkeypatch.setattr(mail, "_kick", lambda pk: None)  # the thread; the tests call deliver_outbox themselves
    monkeypatch.setattr(mail, "configured", lambda: True)
    Setting.put("security.require_mfa", "nobody")
    sent = []
    monkeypatch.setattr(mail, "_deliver", lambda msg: sent.append(msg))
    return sent


def test_closing_queues_the_email_instead_of_waiting(queued, monkeypatch, django_capture_on_commit_callbacks):
    user = make_user()
    t = services.create_ticket(subject="Printer", contact_email="maria@franklin.test")
    slow = []
    monkeypatch.setattr(mail, "_deliver", lambda msg: slow.append(msg))
    with django_capture_on_commit_callbacks(execute=True):
        services.update_ticket(t, user=user, status="Closed")
    row = OutboxEmail.objects.get()
    assert row.status == "pending" and row.to == "maria@franklin.test" and not slow
    assert mail.deliver_outbox() == {"sent": 1, "failed": 0}
    row.refresh_from_db()
    assert row.status == "sent" and slow[0].to == ["maria@franklin.test"] and "Message-ID" in slow[0].extra_headers
    assert t.messages.filter(kind="event", body__startswith="Emailed maria@franklin.test").exists()
    assert mail.deliver_outbox() == {"sent": 0, "failed": 0}  # nothing sent twice


def test_reply_is_marked_emailed_once_it_goes(queued):
    t = services.create_ticket(subject="VPN", contact_email="bo@client.test")
    m = services.add_message(t, user=make_user(), kind="reply", body="Try again")
    m.refresh_from_db()
    assert m.via == "web"
    mail.deliver_outbox()
    m.refresh_from_db()
    assert m.via == "email" and m.email_message_id.startswith("<ws1.t")


def test_failures_retry_then_note_the_ticket(queued, monkeypatch, django_capture_on_commit_callbacks):
    def boom(msg):
        raise OSError("Connection refused")
    monkeypatch.setattr(mail, "_deliver", boom)
    t = services.create_ticket(subject="Mail", contact_email="al@client.test")
    with django_capture_on_commit_callbacks(execute=True):
        services.update_ticket(t, user=make_user(), status="Resolved")
    for _ in range(len(mail.RETRY_MINUTES)):
        OutboxEmail.objects.filter(status="pending").update(next_try_at=timezone.now() - timedelta(seconds=1))
        mail.deliver_outbox()
    row = OutboxEmail.objects.get()
    assert row.status == "failed" and row.tries == len(mail.RETRY_MINUTES) and "refused" in row.last_error
    assert TicketMessage.objects.filter(ticket=t, body__contains="couldn't be sent").exists()


def test_stuck_sends_are_picked_up_again(queued, django_capture_on_commit_callbacks):
    t = services.create_ticket(subject="X", contact_email="cy@client.test")
    with django_capture_on_commit_callbacks(execute=True):
        services.update_ticket(t, user=make_user(), status="Closed")
    OutboxEmail.objects.update(status="sending", next_try_at=timezone.now() - timedelta(minutes=30))
    assert mail.deliver_outbox()["sent"] == 1
