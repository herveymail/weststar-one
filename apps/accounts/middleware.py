from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from .models import UserSession
from .google import counts_as_2fa as google_counts_as_2fa
from .security import idle_minutes, mfa_required

OPEN_PATHS = ("/login/", "/static/", "/health/", "/client-portal/", "/portal", "/stripe/webhook/", "/brand/")  # the portal has its own sign-in (apps/portal/auth.py)
# Paths allowed while a sign-in is only half finished.
STEP_PATHS = ("/login/mfa/", "/logout/", "/account/password/", "/account/mfa-setup/")


class SessionGuardMiddleware:
    """Every request: session still valid (not revoked, not idle), then the sign-in gates in order —
    two-factor code → forced password change → required two-factor setup."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path
        if path.startswith(OPEN_PATHS) and not path.startswith("/login/mfa/"):
            return self.get_response(request)
        user = request.user
        if not user.is_authenticated:
            if path.startswith(STEP_PATHS):
                return redirect("/login/")
            return self.get_response(request)

        key = request.session.session_key
        now = timezone.now()
        us = UserSession.objects.filter(session_key=key, revoked_at__isnull=True).only("id", "last_seen_at").first()
        last = request.session.get("last_seen", 0)
        if us is None or now.timestamp() - last > idle_minutes() * 60:
            logout(request)
            if us:
                UserSession.objects.filter(pk=us.pk).update(revoked_at=now)
            return redirect("/login/?expired=1")
        if now.timestamp() - last > 60:
            request.session["last_seen"] = now.timestamp()
            UserSession.objects.filter(pk=us.pk).update(last_seen_at=now)

        request.mfa_passed = bool(request.session.get("mfa_passed"))
        if not request.mfa_passed:
            return self.get_response(request) if path.startswith(("/login/mfa/", "/logout/")) else redirect("/login/mfa/")
        if user.must_change_password and not request.session.get("via_google"):  # Google sign-ins don't use the password
            return self.get_response(request) if path.startswith(("/account/password/", "/logout/")) else redirect("/account/password/")
        if not user.mfa_enabled and mfa_required(user) and not (request.session.get("via_google") and google_counts_as_2fa()):
            return self.get_response(request) if path.startswith(("/account/mfa-setup/", "/logout/")) else redirect("/account/mfa-setup/")
        return self.get_response(request)
