import pyotp
from django.utils import timezone

from apps.accounts.models import User
from apps.core.crypto import encrypt

PASSWORD = "Correct-Horse-Battery-9"
SEED = "JBSWY3DPEHPK3PXPJBSWY3DPEHPK3PXP"


def make_user(email="tech@example.com", role="tech", mfa=False, **kw):
    u = User(email=email, name=kw.pop("name", email.split("@")[0].title()), role=role, **kw)
    u.set_password(PASSWORD)
    if mfa:
        u.mfa_enabled, u.totp_secret_enc = True, encrypt(SEED)
    u.save()
    return u


def code(offset_steps=0):
    return pyotp.TOTP(SEED).at(timezone.now().timestamp() + 30 * offset_steps)


def signed_in(client, user):
    """Sign in through the real pages (password, then 2FA if on)."""
    r = client.post("/login/", {"email": user.email, "password": PASSWORD})
    assert r.status_code == 302, r.content[:300]
    if user.mfa_enabled:
        r = client.post("/login/mfa/", {"code": code()})
        assert r.status_code == 302 and r["Location"] == "/", r.content[:300]
    return client
