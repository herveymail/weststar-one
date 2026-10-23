"""Portal sign-in: its own session cookie (never the staff one), password or emailed link, optional 2FA,
lockouts, idle timeout and per-request re-checks (account still active, client still a customer)."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from functools import wraps

import pyotp
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect
from django.utils import timezone

from apps.accounts.models import LoginAttempt
from apps.core.crypto import decrypt
from apps.core.models import Setting
from apps.core.net import client_ip

from .models import PortalToken, PortalUser

COOKIE = "__Host-ws_portal" if settings.APP_URL.startswith("https://") else "ws_portal"
IDLE_MINUTES = 60
MAX_AGE = 12 * 3600
LOCK_AFTER, LOCK_MINUTES = 5, 15
GENERIC_FAIL = "That email and password don't match, or the account is locked for a few minutes. Try again, or use 'Email me a sign-in link'."
_DUMMY = make_password("portal-dummy-password")
TOKEN_LIFETIME = {"reset": timedelta(hours=1), "magic": timedelta(minutes=15), "invite": timedelta(days=7)}


def enabled(key: str = "enabled") -> bool:
    """Settings › Customer portal switches (on unless turned off)."""
    from apps.core.settings_catalog import DEFAULTS
    return Setting.get(f"portal.{key}", DEFAULTS.get(f"portal.{key}", "true")) != "false"


def _auth_hash(user: PortalUser) -> str:
    """Changes when the password changes, which signs out every other session of that person."""
    return hmac.new(settings.SECRET_KEY.encode(), f"{user.pk}:{user.password}".encode(), hashlib.sha256).hexdigest()


class PortalSessionMiddleware:
    """For /client-portal/ pages: loads the portal session from its own cookie and the signed-in portal user."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.path.startswith("/client-portal/"):
            return self.get_response(request)
        request.portal_session = SessionStore(request.COOKIES.get(COOKIE))
        request.portal_user = self._load(request)
        response = self.get_response(request)
        s = request.portal_session
        if s.get("_logout"):
            s.flush()
            response.delete_cookie(COOKIE, path="/", samesite="Lax")
        elif s.modified or (request.portal_user and s.session_key):
            s.set_expiry(MAX_AGE)
            s.save()
            response.set_cookie(COOKIE, s.session_key, max_age=MAX_AGE, path="/", secure=settings.APP_URL.startswith("https://"),
                                httponly=True, samesite="Lax")
        return response

    @staticmethod
    def _load(request):
        s = request.portal_session
        uid = s.get("uid")
        if not uid:
            return None
        u = PortalUser.objects.select_related("client", "group", "contact").filter(pk=uid).first()
        now = timezone.now().timestamp()
        ok = (u is not None and u.is_active and s.get("hash") == _auth_hash(u) and now - s.get("seen", 0) < IDLE_MINUTES * 60
              and u.client.archived_at is None and u.client.status not in ("Inactive", "Former") and enabled())
        if not ok:
            s.flush()
            request.portal_expired = bool(uid)
            return None
        if not s.get("mfa_ok"):
            request.portal_pending = u
            return None
        if now - s.get("seen", 0) > 60:
            s["seen"] = now
        return u


def start(request, user: PortalUser, mfa_ok: bool) -> None:
    s = request.portal_session
    s.cycle_key()  # new session id at sign-in (no session fixation)
    s["uid"], s["hash"], s["seen"], s["mfa_ok"] = user.pk, _auth_hash(user), timezone.now().timestamp(), mfa_ok
    PortalUser.objects.filter(pk=user.pk).update(last_login=timezone.now(), failed_logins=0)


def logout(request) -> None:
    request.portal_session["_logout"] = True


def portal_login_required(perm: str | None = None, setting: str | None = None):
    def deco(view):
        @wraps(view)
        def wrapper(request, *a, **kw):
            if not enabled():
                return redirect("/client-portal/login/")
            if getattr(request, "portal_pending", None):
                return redirect("/client-portal/login/code/")
            if not request.portal_user:
                return redirect("/client-portal/login/" + ("?expired=1" if getattr(request, "portal_expired", False) else ""))
            if (perm and not request.portal_user.can(perm)) or (setting and not enabled(f"show_{setting}")):
                raise PermissionDenied
            return view(request, *a, **kw)
        return wrapper
    return deco


def _record(email, request, ok, reason):
    LoginAttempt.objects.create(email=f"portal:{(email or '')[:240]}", ip=client_ip(request), success=ok, reason=reason)


def ip_blocked(request) -> bool:
    since = timezone.now() - timedelta(minutes=15)
    return LoginAttempt.objects.filter(ip=client_ip(request), success=False, created_at__gte=since).count() >= settings.LOGIN_IP_MAX_FAILS


def check_password_step(request, email: str, password: str) -> PortalUser | None:
    email = (email or "").strip().lower()
    if ip_blocked(request):
        _record(email, request, False, "ip_blocked")
        return None
    u = PortalUser.objects.select_related("client").filter(email__iexact=email, is_active=True).first()
    if u is None or not u.has_password or (u.locked_until and u.locked_until > timezone.now()):
        check_password(password, _DUMMY)
        _record(email, request, False, "unknown_or_locked")
        return None
    if not u.check_password(password):
        with transaction.atomic():
            x = PortalUser.objects.select_for_update().get(pk=u.pk)
            x.failed_logins += 1
            if x.failed_logins >= LOCK_AFTER:
                x.locked_until, x.failed_logins = timezone.now() + timedelta(minutes=LOCK_MINUTES), 0
            x.save(update_fields=["failed_logins", "locked_until"])
        _record(email, request, False, "bad_password")
        return None
    if u.client.archived_at or u.client.status in ("Inactive", "Former"):
        _record(email, request, False, "client_inactive")
        return None
    _record(email, request, True, "ok")
    return u


def verify_totp(user: PortalUser, code: str, field: str = "totp_secret_enc") -> bool:
    code = "".join(c for c in (code or "") if c.isdigit())
    if len(code) != 6:
        return False
    with transaction.atomic():
        u = PortalUser.objects.select_for_update().get(pk=user.pk)
        secret = decrypt(getattr(u, field)) if getattr(u, field) else ""
        if not secret:
            return False
        totp, now = pyotp.TOTP(secret), timezone.now().timestamp()
        for drift in (0, -1, 1):
            step = int(now // 30) + drift
            if totp.at(step * 30) == code:
                if u.totp_last_step is not None and step <= u.totp_last_step:
                    return False
                u.totp_last_step = step
                u.save(update_fields=["totp_last_step"])
                return True
    return False


# ── one-use links ──
def make_token(user: PortalUser, kind: str) -> str:
    raw = secrets.token_urlsafe(32)
    PortalToken.objects.filter(user=user, kind=kind, used_at__isnull=True).delete()
    PortalToken.objects.create(user=user, kind=kind, token_hash=PortalToken.hash(raw), expires_at=timezone.now() + TOKEN_LIFETIME[kind])
    return raw


def use_token(raw: str, kinds=("reset", "magic", "invite"), consume=True) -> PortalToken | None:
    with transaction.atomic():
        t = (PortalToken.objects.select_for_update().select_related("user", "user__client")
             .filter(token_hash=PortalToken.hash(raw or ""), kind__in=kinds, used_at__isnull=True, expires_at__gt=timezone.now()).first())
        if t is None or not t.user.is_active:
            return None
        if consume:
            t.used_at = timezone.now()
            t.save(update_fields=["used_at"])
        return t


def link(raw: str) -> str:
    return f"{settings.PORTAL_BASE}/link/{raw}/"


def send_link(user: PortalUser, kind: str, invited_by: str = "") -> bool:
    from apps.core import mail
    raw = make_token(user, kind)
    subject = {"reset": "Reset your portal password", "magic": "Your sign-in link", "invite": "You're invited to our client portal"}[kind]
    return mail.send(user.email, subject, f"email/portal_{kind}", {"u": user, "link": link(raw), "invited_by": invited_by,
                                                                   "minutes": int(TOKEN_LIFETIME[kind].total_seconds() // 60)})


def require_admin_of_client(request):
    if not (request.portal_user and request.portal_user.role == "admin"):
        raise PermissionDenied
