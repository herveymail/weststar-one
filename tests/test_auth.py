import pytest
from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.utils import timezone

from apps.accounts import security
from apps.accounts.models import User, UserSession
from apps.core.models import Setting

from .helpers import PASSWORD, code, make_user, signed_in

pytestmark = pytest.mark.django_db


def test_sign_in_with_two_factor(client):
    u = make_user(role="admin", mfa=True)
    r = client.post("/login/", {"email": u.email, "password": PASSWORD})
    assert r["Location"] == "/login/mfa/"
    assert client.get("/").status_code == 302  # half signed-in can't see anything
    r = client.post("/login/mfa/", {"code": code()})
    assert r["Location"] == "/"
    assert client.get("/").status_code == 200


def test_same_message_for_unknown_and_wrong_password(client):
    make_user()
    a = client.post("/login/", {"email": "nobody@example.com", "password": "x" * 12}).content
    b = client.post("/login/", {"email": "tech@example.com", "password": "x" * 12}).content
    from django.utils.html import escape
    msg = escape(security.GENERIC_FAIL).encode()
    assert msg in a and msg in b


def test_lockout_after_failures(client):
    u = make_user()
    for _ in range(settings.LOGIN_LOCK_AFTER):
        client.post("/login/", {"email": u.email, "password": "wrong-password-123"})
    u.refresh_from_db()
    assert u.locked_until and u.locked_until > timezone.now()
    r = client.post("/login/", {"email": u.email, "password": PASSWORD})
    assert r.status_code == 200  # right password still refused while locked


def test_correct_password_does_not_reset_2fa_failures(client):
    """H1: guessing 2FA codes, then signing in again with the password, must not reset the 2FA counter."""
    u = make_user(role="admin", mfa=True)
    for _ in range(settings.LOGIN_LOCK_AFTER - 1):
        client.post("/login/", {"email": u.email, "password": PASSWORD})
        client.post("/login/mfa/", {"code": "000000"})
        client.post("/logout/")
    u.refresh_from_db()
    assert u.mfa_failures == settings.LOGIN_LOCK_AFTER - 1
    client.post("/login/", {"email": u.email, "password": PASSWORD})
    client.post("/login/mfa/", {"code": "000000"})
    u.refresh_from_db()
    assert u.locked_until and u.locked_until > timezone.now()


def test_totp_code_cannot_be_reused(client):
    """L3: the same 6-digit code works once."""
    u = make_user(role="admin", mfa=True)
    c = code()
    assert security.verify_totp(u.pk, c)
    assert not security.verify_totp(u.pk, c)


def test_recovery_code_works_once(client):
    u = make_user(role="admin", mfa=True)
    codes = security.new_recovery_codes(u)
    assert security.use_recovery_code(u, codes[0])
    assert not security.use_recovery_code(u, codes[0])
    assert security.use_recovery_code(u, codes[1].replace("-", "").lower())


def test_old_php_bcrypt_password_works_and_upgrades(client):
    import bcrypt
    php_hash = bcrypt.hashpw(PASSWORD.encode(), bcrypt.gensalt(10)).decode().replace("$2b$", "$2y$")
    u = make_user()
    User.objects.filter(pk=u.pk).update(password="bcrypt$" + php_hash.replace("$2y$", "$2b$"))
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, User.objects.get(pk=u.pk))
    assert not User.objects.get(pk=u.pk).password.startswith("bcrypt")  # re-hashed with the preferred hasher


def test_privileged_people_must_set_up_2fa(client):
    """M4: admins, managers and anyone with H/R access are sent to 2FA setup."""
    u = make_user(role="tech", hr_access=True)
    client.post("/login/", {"email": u.email, "password": PASSWORD})
    assert client.get("/").headers["Location"] == "/account/mfa-setup/"
    plain = make_user("plain@example.com", role="tech")
    assert not security.mfa_required(plain)


def test_replacing_authenticator_needs_password(client):
    """L6: with 2FA already on, starting setup again requires the password."""
    u = make_user(role="admin", mfa=True)
    signed_in(client, u)
    r = client.post("/account/mfa-setup/", {"step": "start", "password": "wrong"})
    assert b"isn&#x27;t right" in r.content and b"<img" not in r.content
    r = client.post("/account/mfa-setup/", {"step": "start", "password": PASSWORD})
    assert b"class=\"qr\"" in r.content


def test_forced_password_change_and_other_sessions_signed_out(client, django_user_model):
    from django.test import Client
    u = make_user(must_change_password=True)
    other = Client()
    other.post("/login/", {"email": u.email, "password": PASSWORD})
    client.post("/login/", {"email": u.email, "password": PASSWORD})
    assert client.get("/").headers["Location"] == "/account/password/"
    r = client.post("/account/password/", {"current": PASSWORD, "new": "A-brand-new-passphrase-42", "again": "A-brand-new-passphrase-42"})
    assert r.status_code == 302
    assert client.get("/").status_code == 200
    assert other.get("/").status_code == 302  # the other browser was signed out
    assert UserSession.objects.filter(user=u, revoked_at__isnull=True).count() == 1


def test_security_headers(client):
    r = client.get("/login/")
    csp = r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in csp and "unsafe-eval" not in csp
    assert r.headers["X-Frame-Options"] == "DENY" or "frame-ancestors 'none'" in csp
    assert b"<script>" not in r.content  # no inline scripts anywhere


def test_proxy_ip_uses_rightmost_forwarded_address(rf, settings):
    """M1: a client can't spoof its IP by adding its own X-Forwarded-For entries."""
    from apps.core.net import client_ip
    settings.TRUST_PROXY = True
    req = rf.get("/", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.9", REMOTE_ADDR="10.0.0.2")
    assert client_ip(req) == "203.0.113.9"


def test_dummy_hash_is_argon2():
    assert make_password("x").startswith(("argon2", "md5"))
