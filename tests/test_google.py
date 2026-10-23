"""Google Workspace sign-in, with Google's token endpoint faked."""
import base64
import json
import time
from urllib.parse import parse_qs, urlparse

import pytest

from apps.accounts import google
from apps.core.models import Setting

from .helpers import PASSWORD, make_user

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def configured():
    Setting.put("google.client_id", "cid.apps.googleusercontent.com")
    Setting.put("google.client_secret", "shh", secret=True)
    Setting.put("google.domains", "weststarmsp.com, dsotv.com")


def _token(**claims):
    body = {"iss": "https://accounts.google.com", "aud": "cid.apps.googleusercontent.com", "exp": time.time() + 300,
            "email_verified": True, **claims}
    enc = base64.urlsafe_b64encode(json.dumps(body).encode()).rstrip(b"=").decode()
    return f"eyJhbGciOiJSUzI1NiJ9.{enc}.sig"


def _go(client, monkeypatch, nonce_ok=True, **claims):
    r = client.get("/login/google/")
    q = parse_qs(urlparse(r["Location"]).query)
    assert q["code_challenge_method"] == ["S256"] and q["redirect_uri"][0].endswith("/login/google/callback/")
    nonce = q["nonce"][0] if nonce_ok else "wrong"
    monkeypatch.setattr(google, "_post", lambda url, data: {"id_token": _token(nonce=nonce, **claims)})
    return client.get("/login/google/callback/", {"state": q["state"][0], "code": "abc"})


def test_staff_member_signs_in(client, monkeypatch):
    make_user("amy@weststarmsp.com", role="admin", mfa=True)
    r = _go(client, monkeypatch, email="Amy@weststarmsp.com", hd="weststarmsp.com")
    assert r.status_code == 302 and r["Location"] == "/"
    assert client.get("/").status_code == 200  # Google's 2-Step counts as two-factor by default


def test_unknown_person_cannot_sign_in(client, monkeypatch):
    r = _go(client, monkeypatch, email="stranger@weststarmsp.com", hd="weststarmsp.com")
    assert r.status_code == 403 and client.get("/").status_code == 302


def test_personal_gmail_and_other_domains_rejected(client, monkeypatch):
    make_user("amy@weststarmsp.com")
    assert _go(client, monkeypatch, email="amy@weststarmsp.com").status_code == 400            # no hd = not Workspace
    assert _go(client, monkeypatch, email="amy@weststarmsp.com", hd="evil.com").status_code == 400
    assert _go(client, monkeypatch, email="amy@weststarmsp.com", hd="weststarmsp.com", nonce_ok=False).status_code == 400


def test_forged_state_rejected(client, monkeypatch):
    client.get("/login/google/")
    monkeypatch.setattr(google, "_post", lambda url, data: pytest.fail("must not call Google"))
    assert client.get("/login/google/callback/", {"state": "forged", "code": "x"}).status_code == 400


def test_archived_user_rejected(client, monkeypatch):
    make_user("gone@weststarmsp.com", is_active=False)
    assert _go(client, monkeypatch, email="gone@weststarmsp.com", hd="weststarmsp.com").status_code == 403


def test_passwords_can_be_limited_to_admins(client):
    Setting.put("security.password_login", "admins")
    tech = make_user("tech@weststarmsp.com", role="tech")
    admin = make_user("boss@weststarmsp.com", role="admin")
    assert client.post("/login/", {"email": tech.email, "password": PASSWORD}).status_code == 200  # refused
    assert client.post("/login/", {"email": admin.email, "password": PASSWORD}).status_code == 302
