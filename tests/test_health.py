"""Settings › Speed & server health, and the slow-request recorder."""
import pytest

from apps.core.models import Setting, SlowRequest

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


def test_health_page_measures_and_lists_slow_pages(client, settings):
    Setting.put("security.require_mfa", "nobody")
    web = signed_in(client, make_user(role="admin"))
    settings.SLOW_REQUEST_MS = 0  # record everything
    r = web.get("/tickets/")
    assert "db;dur=" in r["Server-Timing"]
    assert SlowRequest.objects.filter(path="/tickets/", method="GET").exists()
    page = web.get("/settings/health/").content.decode()
    assert "Speed test" in page and "One database question" in page and "/tickets/" in page
    web.post("/settings/health/", {"action": "clear"})
    assert not SlowRequest.objects.filter(path="/tickets/").exists()


def test_fast_requests_are_not_recorded(client):
    client.get("/login/")
    assert not SlowRequest.objects.exists()


def test_techs_cannot_see_it(client):
    Setting.put("security.require_mfa", "nobody")
    assert signed_in(client, make_user(role="tech")).get("/settings/health/").status_code == 403
