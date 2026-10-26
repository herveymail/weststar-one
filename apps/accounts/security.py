"""
Sign-in rules. Every counter change happens inside a transaction with the user's row locked
(SELECT … FOR UPDATE), so parallel requests can't slip past the lockout or reuse a 2FA code.
"""
import hashlib
from datetime import timedelta

import pyotp
from django.conf import settings
from django.contrib.auth import login as django_login
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.sessions.models import Session
from django.db import transaction
from django.utils import timezone

from apps.core.audit import audit
from apps.core.crypto import decrypt, encrypt, keyed_hash, keyed_hashes, token
from apps.core.models import Setting
from apps.core.net import client_ip

from .models import LoginAttempt, RecoveryCode, User, UserSession

GENERIC_FAIL = "That email and password don't match, or the account is temporarily locked. Try again later or ask an admin."
_DUMMY = make_password("not-a-real-password")


def mfa_policy() -> str:
    return Setting.get("security.require_mfa", "privileged")


def mfa_required(user: User) -> bool:
    """Default policy 'privileged': admins, managers, and anyone with H/R access must use 2FA."""
    policy = mfa_policy()
    if policy == "everyone":
        return True
    if policy == "nobody":
        return False
    return user.role in ("admin", "manager") or user.hr_access


def idle_minutes() -> int:
    try:
        v = int(Setting.get("security.idle_minutes", "30"))
    except ValueError:
        v = 30
    return min(max(v, 5), 24 * 60)


def _record(email: str, request, success: bool, reason: str):
    LoginAttempt.objects.create(email=(email or "")[:254], ip=client_ip(request), success=success, reason=reason)


def record_attempt(email: str, request, success: bool, reason: str):
    _record(email, request, success, reason)


def ip_blocked(request) -> bool:
    since = timezone.now() - timedelta(minutes=15)
    fails = LoginAttempt.objects.filter(ip=client_ip(request), success=False, created_at__gte=since)
    return fails.exclude(reason__startswith="google").count() >= settings.LOGIN_IP_MAX_FAILS  # Google failures aren't password guesses


def _fail(user_id: int, counter: str) -> None:
    """Add one failure and lock the account when the counter reaches the limit (atomically)."""
    with transaction.atomic():
        u = User.objects.select_for_update().get(pk=user_id)
        setattr(u, counter, getattr(u, counter) + 1)
        if getattr(u, counter) >= settings.LOGIN_LOCK_AFTER:
            u.lock_count += 1
            minutes = settings.LOGIN_LOCK_MINUTES * 2 ** min(u.lock_count - 1, 6)
            u.locked_until = timezone.now() + timedelta(minutes=minutes)
            setattr(u, counter, 0)
        u.save(update_fields=[counter, "lock_count", "locked_until"])


def check_password_step(request, email: str, password: str) -> tuple[User | None, str]:
    """Returns (user, "") on success, or (None, reason). The person always sees the same message."""
    email = (email or "").strip().lower()
    if ip_blocked(request):
        _record(email, request, False, "ip_blocked")
        return None, "ip_blocked"
    user = User.objects.filter(email__iexact=email, is_active=True).first()
    if user is None:
        check_password(password, _DUMMY)  # same work as a real check, so timing doesn't reveal accounts
        _record(email, request, False, "unknown_email")
        return None, "unknown_email"
    if user.locked_until and user.locked_until > timezone.now():
        check_password(password, _DUMMY)
        _record(email, request, False, "locked")
        return None, "locked"
    # check_password() also upgrades old bcrypt hashes from the PHP app to Argon2.
    if not user.check_password(password):
        _fail(user.pk, "failed_logins")
        _record(email, request, False, "bad_password")
        return None, "bad_password"
    User.objects.filter(pk=user.pk).update(failed_logins=0)
    _record(email, request, True, "ok")
    return user, ""


def verify_totp(user_id: int, code: str, secret_field: str = "totp_secret_enc") -> bool:
    code = "".join(ch for ch in (code or "") if ch.isdigit())
    if len(code) != 6:
        return False
    with transaction.atomic():
        u = User.objects.select_for_update().get(pk=user_id)
        secret = decrypt(getattr(u, secret_field)) if getattr(u, secret_field) else ""
        if not secret:
            return False
        totp = pyotp.TOTP(secret)
        now = timezone.now().timestamp()
        for drift in (0, -1, 1):
            step = int(now // 30) + drift
            if totp.at(step * 30) == code:
                if u.totp_last_step is not None and step <= u.totp_last_step:
                    return False  # already used
                u.totp_last_step = step
                u.save(update_fields=["totp_last_step"])
                return True
    return False


def use_recovery_code(user: User, code: str) -> bool:
    clean = "".join(ch for ch in (code or "").upper() if ch.isalnum())
    if len(clean) < 8:
        return False
    with transaction.atomic():
        row = RecoveryCode.objects.select_for_update().filter(user=user, code_hash__in=keyed_hashes(clean), used_at__isnull=True).first()
        if not row:
            return False
        row.used_at = timezone.now()
        row.save(update_fields=["used_at"])
        return True


def check_mfa_step(request, user: User, code: str) -> tuple[bool, bool]:
    """Returns (ok, used_recovery_code)."""
    user.refresh_from_db()
    if user.locked_until and user.locked_until > timezone.now():
        _record(user.email, request, False, "locked")
        return False, False
    if verify_totp(user.pk, code):
        User.objects.filter(pk=user.pk).update(mfa_failures=0)
        return True, False
    if use_recovery_code(user, code):
        User.objects.filter(pk=user.pk).update(mfa_failures=0)
        return True, True
    _fail(user.pk, "mfa_failures")
    _record(user.email, request, False, "bad_mfa")
    return False, False


def new_recovery_codes(user: User) -> list[str]:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    import secrets as _s
    codes = ["".join(_s.choice(alphabet) for _ in range(10)) for _ in range(10)]
    with transaction.atomic():
        RecoveryCode.objects.filter(user=user).delete()
        RecoveryCode.objects.bulk_create([RecoveryCode(user=user, code_hash=keyed_hash(c)) for c in codes])
    return [c[:5] + "-" + c[5:] for c in codes]


def new_totp_secret() -> str:
    return pyotp.random_base32(32)


def enable_mfa(user: User) -> list[str]:
    with transaction.atomic():
        u = User.objects.select_for_update().get(pk=user.pk)
        u.totp_secret_enc, u.totp_pending_enc, u.mfa_enabled, u.mfa_failures = u.totp_pending_enc, "", True, 0
        u.save(update_fields=["totp_secret_enc", "totp_pending_enc", "mfa_enabled", "mfa_failures"])
    return new_recovery_codes(user)


def start_session(request, user: User, mfa_passed: bool) -> None:
    """Sign in. django.contrib.auth.login() issues a brand-new session id (no session fixation)."""
    django_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    request.session["mfa_passed"] = mfa_passed
    request.session["last_seen"] = timezone.now().timestamp()
    request.session.save()
    key = request.session.session_key
    UserSession.objects.update_or_create(
        session_key=key,
        defaults={"user": user, "fingerprint": hashlib.sha256(key.encode()).hexdigest()[:16], "ip": client_ip(request),
                  "user_agent": request.META.get("HTTP_USER_AGENT", "")[:300]},
    )


def finish_mfa(request, user: User) -> None:
    """Second step passed: rotate the session id again and mark it complete."""
    old = request.session.session_key
    UserSession.objects.filter(session_key=old).delete()
    request.session.cycle_key()
    start_session(request, user, mfa_passed=True)


def revoke_sessions(user: User, except_key: str | None = None) -> None:
    rows = UserSession.objects.filter(user=user, revoked_at__isnull=True)
    if except_key:
        rows = rows.exclude(session_key=except_key)
    keys = list(rows.values_list("session_key", flat=True))
    Session.objects.filter(session_key__in=keys).delete()
    rows.update(revoked_at=timezone.now())


def otpauth_uri(user: User, secret: str) -> str:
    return pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name=Setting.get("brand.app_name", "Weststar ONE"))


def encrypt_pending(user: User, secret: str) -> None:
    User.objects.filter(pk=user.pk).update(totp_pending_enc=encrypt(secret))


_ = (audit, token)
