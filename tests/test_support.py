"""Settings › System support: who can see it, what it shows, crash capture, clean-up, the support report."""
import pytest
from django.test import Client as Browser

from apps.accounts.models import User
from apps.core import support
from apps.core.models import ErrorEvent, Setting, SlowRequest

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def boss(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin", email="boss@example.com")
    signed_in(client, u)
    return u


def test_claim_then_only_chosen_people_see_it(client, boss):
    other = make_user(role="admin", email="other@example.com")
    assert b"System support" in client.get("/settings/").content           # nobody has it yet: admins may claim
    assert b"Nobody has access yet" in client.get("/settings/support/").content
    client.post("/settings/support/", {"action": "claim"})
    boss.refresh_from_db()
    assert boss.support_access
    page = client.get("/settings/support/")
    assert page.status_code == 200 and b"what&#x27;s taking the room" in page.content or b"what's taking the room" in page.content
    for bit in (b"Tickets", b"Database", b"Background jobs", b"Crashes", b"Who can see this screen", b"PostgreSQL"):
        assert bit in page.content, bit
    # the other admin can't see or open it, and can't claim it any more
    b2 = Browser()
    signed_in(b2, other)
    assert b"System support" not in b2.get("/settings/").content
    assert b2.get("/settings/support/").status_code == 403
    assert b2.post("/settings/support/", {"action": "claim"}).status_code == 403
    assert b2.get("/settings/support/?report=1").status_code == 403
    # boss grants it; boss can't untick themself
    client.post("/settings/support/", {"action": "access", "user": [other.pk]})
    other.refresh_from_db()
    boss.refresh_from_db()
    assert other.support_access and boss.support_access
    assert b2.get("/settings/support/").status_code == 200
    client.post("/settings/support/", {"action": "access"})
    assert not User.objects.get(pk=other.pk).support_access and User.objects.get(pk=boss.pk).support_access


def test_non_admin_never(client):
    Setting.put("security.require_mfa", "nobody")
    t = make_user(role="tech", support_access=True)
    signed_in(client, t)
    assert client.get("/settings/support/").status_code == 403


def test_crash_is_recorded_and_grouped(rf):
    req = rf.get("/tickets/5/")
    for _ in range(3):
        try:
            raise ValueError("bad thing 123")
        except ValueError:
            support.record_exception(request=req)
    e = ErrorEvent.objects.get()
    assert e.count == 3 and e.kind == "ValueError" and e.path == "/tickets/5/" and "test_support.py" in e.where and "test_crash_is_recorded" in e.trace


def test_report_and_cleanup(client, boss):
    from datetime import timedelta

    from django.utils import timezone
    User.objects.filter(pk=boss.pk).update(support_access=True)
    Setting.put("stripe.secret_key", "sk_live_SHOULD_NOT_APPEAR", secret=True)
    r = client.get("/settings/support/?report=1")
    body = r.content.decode()
    assert r["Content-Disposition"].startswith("attachment") and "SUPPORT REPORT" in body and "== Database ==" in body and "helpdesk_ticket" in body
    assert "SHOULD_NOT_APPEAR" not in body and "sk_live" not in body
    s = SlowRequest.objects.create(path="/x/", method="GET", total_ms=2000, db_ms=10)
    SlowRequest.objects.filter(pk=s.pk).update(created_at=timezone.now() - timedelta(days=60))
    assert support.trim_counts()["slow"] == 1
    client.post("/settings/support/", {"action": "trim"})
    assert not SlowRequest.objects.exists()
    assert client.post("/settings/support/", {"action": "tidy"}).status_code == 302
