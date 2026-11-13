"""Seeing and fixing why someone can't sign in: security log reasons, unlock, clearing a blocked office network."""
import pytest
from django.conf import settings
from django.test import Client as Browser
from django.utils import timezone

from apps.accounts import security
from apps.accounts.models import LoginAttempt, User
from apps.core.models import Setting

from .helpers import PASSWORD, make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(client):
    Setting.put("security.require_mfa", "nobody")
    u = make_user(role="admin", email="boss@example.com")
    signed_in(client, u)
    return u


def test_log_explains_and_unlock_works(client, admin):
    u = make_user(email="pat@example.com")
    b = Browser()
    for _ in range(settings.LOGIN_LOCK_AFTER + 1):
        b.post("/login/", {"email": u.email, "password": "wrong-password-123"})
    page = client.get("/settings/security_log/")
    assert b"Wrong password" in page.content and b"Account locked" in page.content and b"Blocked right now" in page.content
    assert b"locked out" in client.get("/settings/").content
    client.post("/settings/security_log/", {"action": "unlock", "user": u.pk})
    u.refresh_from_db()
    assert u.locked_until is None and u.lock_count == 0
    assert b.post("/login/", {"email": u.email, "password": PASSWORD}).status_code == 302


def test_office_network_block_is_explained_and_clearable(client, admin):
    make_user(email="sam@example.com")
    ip = "127.0.0.1"
    LoginAttempt.objects.bulk_create([LoginAttempt(email="x@example.com", ip=ip, success=False, reason="bad_password") for _ in range(settings.LOGIN_IP_MAX_FAILS)])
    r = Browser().post("/login/", {"email": "sam@example.com", "password": PASSWORD})
    assert b"from your network" in r.content
    assert security.blocked_ips()[0]["ip"] == ip
    assert b"Clear block" in client.get("/settings/security_log/").content
    client.post("/settings/security_log/", {"action": "clear_ip", "ip": ip})
    assert security.blocked_ips() == []
    assert Browser().post("/login/", {"email": "sam@example.com", "password": PASSWORD}).status_code == 302


def test_google_only_user_told_to_use_google(client):
    Setting.put("google.client_id", "x.apps.googleusercontent.com")
    Setting.put("google.client_secret", "s", secret=True)
    Setting.put("google.domains", "example.com")
    u = make_user(email="g@example.com")
    User.objects.filter(pk=u.pk).update(google_only=True)
    from apps.accounts import google
    if not google.enabled():
        pytest.skip("Google sign-in settings differ")
    r = client.post("/login/", {"email": u.email, "password": PASSWORD})
    assert "Sign in with Google".encode() in r.content


def test_good_signin_resets_lock_doubling(client):
    u = make_user(email="lc@example.com")
    User.objects.filter(pk=u.pk).update(lock_count=6)
    client.post("/login/", {"email": u.email, "password": PASSWORD})
    u.refresh_from_db()
    assert u.lock_count == 0 and timezone.now()


def test_pause_is_not_extended_by_retries():
    """Trying again while the network is paused must not keep it paused forever."""
    from datetime import timedelta
    ip = "127.0.0.1"
    old = timezone.now() - timedelta(minutes=14)
    for _ in range(settings.LOGIN_IP_MAX_FAILS):
        LoginAttempt.objects.create(email="x@example.com", ip=ip, success=False, reason="bad_password")
    LoginAttempt.objects.filter(ip=ip).update(created_at=old)
    b = Browser()
    for _ in range(5):
        b.post("/login/", {"email": "y@example.com", "password": "nope-nope-123"})
    LoginAttempt.objects.filter(ip=ip, reason="bad_password").update(created_at=timezone.now() - timedelta(minutes=16))
    make_user(email="z@example.com")
    assert b.post("/login/", {"email": "z@example.com", "password": PASSWORD}).status_code == 302
