"""Ticket templates and recurring tickets."""
from datetime import timedelta

import pytest
from django.utils import timezone

from apps.core import jobs
from apps.core.models import Setting
from apps.crm.models import Client
from apps.helpdesk.models import RecurringTicket, Ticket, TicketTemplate

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def tpl():
    return TicketTemplate.objects.create(name="Monthly check", subject="Monthly server check — {client} — {month}", details="Do the usual.",
                                         checklist="Check backups\n- Patch servers\nReview alerts", priority="High", estimate_minutes=60, billable=False)


def test_template_render(tpl):
    c = Client.objects.create(name="Acme")
    subject, details = tpl.render(c, timezone.localdate().replace(day=1))
    assert subject.startswith("Monthly server check — Acme — ") and "☐ Check backups" in details and "☐ Patch servers" in details and "60 min" in details


def test_recurring_opens_tickets_once_and_advances(tpl):
    today = timezone.localdate()
    a = Client.objects.create(name="Managed A", plan="Managed")
    Client.objects.create(name="Managed B", plan="Managed · Gold")
    Client.objects.create(name="Break fix", plan="Break/fix")
    tech = make_user(role="tech")
    every = RecurringTicket.objects.create(name="Monthly checks", template=tpl, frequency="Month", next_run=today - timedelta(days=40), assigned_to=tech)
    one = RecurringTicket.objects.create(name="Weekly A", template=tpl, client=a, frequency="Week", next_run=today)
    assert jobs.recurring_tickets() == {"opened": 3}
    assert Ticket.objects.filter(subject__startswith="Monthly server check — Managed A").count() == 2
    assert not Ticket.objects.filter(client__name="Break fix").exists()
    t = Ticket.objects.filter(assigned_to=tech).first()
    assert t.priority == "High" and not t.billable and t.due_date == every.next_run + timedelta(days=7)
    every.refresh_from_db()
    one.refresh_from_db()
    assert every.next_run > today and every.last_run == today and one.next_run == today + timedelta(days=7)
    assert jobs.recurring_tickets() == {"opened": 0}


def test_new_ticket_from_template(client, tpl):
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user(role="admin"))
    r = client.get(f"/tickets/new/?template={tpl.pk}", HTTP_HX_REQUEST="true")
    assert r.status_code == 200 and b"Monthly server check" in r.content and "☐ Check backups".encode() in r.content
    assert client.get("/m/recurring_tickets/").status_code == 200 and client.get("/m/ticket_templates/").status_code == 200
