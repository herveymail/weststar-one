"""Who may sign in with a password once Google sign-in is on and passwords are limited to admins."""
import pytest
from django.test import Client as Browser

from apps.accounts.views import password_login_allowed
from apps.core.models import Setting

from .helpers import make_user

pytestmark = pytest.mark.django_db
PW = "Correct-horse-9!"


@pytest.fixture
def google_on():
    Setting.put("security.require_mfa", "nobody")
    Setting.put("google.client_id", "id")
    Setting.put("google.client_secret", "secret")
    Setting.put("google.domains", "weststarmsp.com, dsotv.com")
    Setting.put("security.password_login", "admins")


def user(email, **kw):
    u = make_user(email, role=kw.pop("role", "tech"), **kw)
    u.set_password(PW)
    u.must_change_password = False
    u.save()
    return u


def test_outside_contractor_can_use_their_password(google_on):
    """richard@myderone.com: not on a Google domain, 'Must sign in with Google' unticked — the password has to work."""
    r = user("richard@myderone.com")
    assert password_login_allowed(r)
    resp = Browser().post("/login/?password=1", {"email": "richard@myderone.com", "password": PW})
    assert resp.status_code == 302 and "/login" not in resp["Location"]


def test_company_staff_still_use_google_unless_allowed(google_on):
    staff = user("tech@weststarmsp.com")
    assert not password_login_allowed(staff)
    resp = Browser().post("/login/?password=1", {"email": "tech@weststarmsp.com", "password": PW})
    assert b"signs in with Google" in resp.content
    staff.password_ok = True
    staff.save()
    assert password_login_allowed(staff)
    assert password_login_allowed(user("boss@weststarmsp.com", role="admin"))
    # someone whose Google account is on our domain even though their staff email isn't
    linked = user("pat@gmail.com", google_email="pat@dsotv.com")
    assert not password_login_allowed(linked)
    # "Must sign in with Google" still wins when it is ticked
    forced = user("forced@weststarmsp.com", google_only=True, password_ok=False)
    assert not password_login_allowed(forced)


def test_the_user_form_stops_settings_that_lock_someone_out(google_on, client):
    from .helpers import signed_in
    Setting.put("security.password_login", "everyone")
    boss = make_user("admin@weststarmsp.com", role="admin")
    signed_in(client, boss)
    r = user("richard@myderone.com")
    base = {"action": "save", "name": "Richard", "email": "richard@myderone.com", "role": "tech"}
    resp = client.post(f"/settings/users/{r.pk}/", {**base, "google_only": "on"})
    assert b"could never sign in" in resp.content
    resp = client.post(f"/settings/users/{r.pk}/", {**base, "google_only": "on", "password_ok": "on", "google_email": "richard@weststarmsp.com"})
    assert b"Pick one" in resp.content
    assert client.post(f"/settings/users/{r.pk}/", {**base, "password_ok": "on"}).status_code in (200, 204)
    r.refresh_from_db()
    assert r.password_ok and not r.google_only
