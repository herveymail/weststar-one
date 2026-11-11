"""Dashboard To do list, morning summary email, renewal heads-ups and renewal quotes."""
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.billing.models import Contract, Quote, Renewal
from apps.core import mail, today
from apps.core.models import Setting
from apps.crm.models import Client
from apps.helpdesk.models import Ticket, TimeEntry
from apps.tools.models import Domain

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def boss(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin")
    signed_in(client, u)
    return u


def test_todo_on_dashboard(client, boss):
    d = timezone.localdate()
    c = Client.objects.create(name="BF", plan="Break/fix")
    t = Ticket.objects.create(number="T-1", subject="Late one", client=c, assigned_to=boss, status="Open", due_date=d - timedelta(days=2))
    TimeEntry.objects.create(ticket=t, user=boss, minutes=60, work_date=d)
    Quote.objects.create(number="Q1", client=c, status="Sent", quote_date=d, expires_on=d - timedelta(days=1))
    Contract.objects.create(name="MSA", client=c, status="Sent")
    Renewal.objects.create(item="M365", client=c, renews_on=d + timedelta(days=10))
    Domain.objects.create(name="bf.test", client=c, ssl_expires_on=d + timedelta(days=5))
    texts = " | ".join(i["text"] for i in today.todo(boss))
    for bit in ("past the due date", "ready to bill", "expired", "waiting for a signature", "renewal", "SSL"):
        assert bit in texts, bit
    page = client.get("/")
    assert b"To do" in page.content and b"/billing/ready/" in page.content


def test_morning_summary_once_per_weekday(boss, monkeypatch):
    sent = []
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.append((to, tpl, len(ctx["tickets"]))) or True)
    Ticket.objects.create(number="T-2", subject="Mine", assigned_to=boss, status="Open")
    monday = timezone.make_aware(datetime(2026, 11, 9, 7, 30))
    assert today.morning_summary(monday) == {"sent": 0}  # not turned on
    type(boss).objects.filter(pk=boss.pk).update(morning_summary=True)
    assert today.morning_summary(monday.replace(hour=6)) == {"sent": 0}
    assert today.morning_summary(monday) == {"sent": 1} and sent[0] == ([boss.email], "email/morning_summary", 1)
    assert today.morning_summary(monday.replace(hour=9)) == {"sent": 0}
    assert today.morning_summary(monday + timedelta(days=5)) == {"sent": 0}  # Saturday


def test_renewal_notices_once(monkeypatch):
    got = []
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: got.append((to, len(ctx["renewals"]), len(ctx["domains"]))) or True)
    Setting.put("email.support_address", "help@ws.test")
    d = timezone.localdate()
    c = Client.objects.create(name="C")
    Renewal.objects.create(item="Firewall license", client=c, renews_on=d + timedelta(days=20))
    Renewal.objects.create(item="Far away", client=c, renews_on=d + timedelta(days=200))
    Domain.objects.create(name="c.test", client=c, expires_on=d + timedelta(days=3))
    assert today.renewal_notices()["sent"] and got == [(["help@ws.test"], 1, 1)]
    today.renewal_notices()
    assert len(got) == 1


def test_renewal_quote(client, boss):
    Setting.put("renewals.markup_pct", "20")
    c = Client.objects.create(name="C")
    r = Renewal.objects.create(item="Firewall license", client=c, type="License", renews_on=timezone.localdate() + timedelta(days=20), cost=Decimal("100"))
    assert b"Make renewal quote" in client.get(f"/m/renewals/{r.pk}/", HTTP_HX_REQUEST="true").content
    resp = client.post(f"/billing/renewal/{r.pk}/quote/")
    q = Quote.objects.get(client=c)
    assert resp.status_code == 302 and q.status == "Draft" and q.lines.get().rate == Decimal("120.00")
    client.post(f"/billing/renewal/{r.pk}/quote/")
    assert Quote.objects.count() == 1
