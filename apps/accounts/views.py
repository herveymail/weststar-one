import base64
import io
import secrets
import string

import qrcode
import qrcode.image.svg
from django import forms
from django.contrib import messages
from django.contrib.auth import logout as django_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import PermissionDenied, ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.audit import audit
from apps.core.crypto import decrypt
from apps.core.models import Setting
from apps.core.permissions import ROLES, can

from . import security
from .models import LoginAttempt, User, UserSession


def _qr_svg(uri: str) -> str:
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathFillImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


def login_view(request):
    if request.user.is_authenticated and request.session.get("mfa_passed"):
        return redirect("/")
    error = ""
    if request.method == "POST":
        user, reason = security.check_password_step(request, request.POST.get("email", ""), request.POST.get("password", ""))
        if user and not password_login_allowed(user):
            security.record_attempt(user.email, request, False, "password_off")
            user = None
        if user:
            needs_code = user.mfa_enabled
            security.start_session(request, user, mfa_passed=not needs_code)
            audit(request, "login", "user", user.pk, f"{user.email} signed in{' (password step)' if needs_code else ''}", user=user)
            return redirect("/login/mfa/" if needs_code else request.GET.get("next", "/") if request.GET.get("next", "/").startswith("/") and not request.GET.get("next", "/").startswith("//") else "/")
        error = security.GENERIC_FAIL
    from . import google
    return render(request, "accounts/login.html", {"error": error, "expired": request.GET.get("expired"), "google": google.enabled(),
                                                   "password_login": not google.enabled() or Setting.get("security.password_login", "everyone") == "everyone"
                                                   or request.GET.get("password") == "1"})


def password_login_allowed(user) -> bool:
    """Settings › Sign-in: once Google sign-in is on, passwords can be limited to admins (break-glass)."""
    from . import google
    if not google.enabled():
        return True
    if user.google_only:
        return False
    if Setting.get("security.password_login", "everyone") == "everyone":
        return True
    return user.role == "admin"


def google_start(request):
    from . import google
    if not google.enabled():
        return redirect("/login/")
    return redirect(google.start(request.session))


def google_callback(request):
    from . import google
    if not google.enabled():
        return redirect("/login/")
    try:
        email = google.finish(request.session, request.GET)
    except google.GoogleSignInError as e:
        security.record_attempt(e.email or "(google)", request, False, e.code)
        return render(request, "accounts/login.html", {"error": str(e), "google": True, "password_login": True}, status=400)
    user = User.objects.filter(email__iexact=email).first()
    problem = None
    if user is None:
        problem = ("google_no_account", f"There's no Weststar ONE staff account for {email}. Ask an admin to add you in Settings › Staff users (same email as your Google account).")
    elif not user.is_active:
        problem = ("google_inactive", f"The staff account for {email} is turned off. Ask an admin to turn it back on in Settings › Staff users.")
    elif user.locked_until and user.locked_until > timezone.now():
        problem = ("locked", f"The staff account for {email} is locked after too many failed sign-ins. It unlocks {timezone.localtime(user.locked_until):%-I:%M %p}, or an admin can unlock it in Staff users.")
    if problem:
        security.record_attempt(email, request, False, problem[0])
        return render(request, "accounts/login.html", {"error": problem[1], "google": True, "password_login": True}, status=403)
    security.record_attempt(email, request, True, "google")
    passed = google.counts_as_2fa() or not user.mfa_enabled
    security.start_session(request, user, mfa_passed=passed)
    request.session["via_google"] = True
    User.objects.filter(pk=user.pk).update(failed_logins=0, last_login=timezone.now(), google_linked_at=user.google_linked_at or timezone.now())
    audit(request, "login", "user", user.pk, f"{user.email} signed in with Google", user=user)
    return redirect("/" if passed else "/login/mfa/")


def mfa_view(request):
    if not request.user.is_authenticated:
        return redirect("/login/")
    if request.session.get("mfa_passed"):
        return redirect("/")
    error = ""
    if request.method == "POST":
        ok, recovery = security.check_mfa_step(request, request.user, request.POST.get("code", ""))
        if ok:
            user = request.user
            security.finish_mfa(request, user)
            audit(request, "login_mfa", "user", user.pk, "Signed in with a recovery code" if recovery else "Two-factor code accepted", user=user)
            if recovery:
                messages.warning(request, "You used a recovery code. Make new ones under My sign-in & 2FA if you're running low.")
            return redirect("/")
        error = "That code isn't right. Codes change every 30 seconds — try the newest one."
        request.user.refresh_from_db()
        if request.user.locked_until and request.user.locked_until > timezone.now():
            django_logout(request)
            return redirect("/login/")
    return render(request, "accounts/mfa.html", {"error": error})


@require_POST
def logout_view(request):
    if request.user.is_authenticated:
        audit(request, "logout", "user", request.user.pk, "Signed out")
        UserSession.objects.filter(session_key=request.session.session_key).update(revoked_at=timezone.now())
    django_logout(request)
    return redirect("/login/")


@login_required
def password_view(request):
    error = ""
    if request.method == "POST":
        user = request.user
        current, new, again = request.POST.get("current", ""), request.POST.get("new", ""), request.POST.get("again", "")
        if not user.check_password(current):
            error = "Your current password isn't right."
        elif new != again:
            error = "The two new passwords don't match."
        else:
            try:
                validate_password(new, user)
            except ValidationError as e:
                error = " ".join(e.messages)
        if not error:
            user.set_password(new)
            user.must_change_password = False
            user.password_changed_at = timezone.now()
            user.save()
            old_key = request.session.session_key
            update_session_auth_hash(request, user)  # issues a new session id for this browser
            UserSession.objects.filter(session_key=old_key).update(session_key=request.session.session_key)
            security.revoke_sessions(user, except_key=request.session.session_key)
            audit(request, "password_change", "user", user.pk, "Changed password; other sessions signed out")
            messages.success(request, "Password changed. You were signed out everywhere else.")
            return redirect("/settings/my_security/" if request.GET.get("from") == "security" else "/")
    return render(request, "accounts/password.html", {"error": error, "forced": request.user.must_change_password})


@login_required
def mfa_setup_view(request):
    """Turn on two-factor. If it is already on, the password is required first (so a borrowed,
    unlocked laptop can't be used to swap in someone else's authenticator)."""
    user = request.user
    error, codes, qr, secret = "", None, None, None
    step = request.POST.get("step", "")
    if request.method == "POST" and step == "start":
        if user.mfa_enabled and not user.check_password(request.POST.get("password", "")):
            error = "Your password isn't right."
        else:
            secret = security.new_totp_secret()
            security.encrypt_pending(user, secret)
            qr = _qr_svg(security.otpauth_uri(user, secret))
    elif request.method == "POST" and step == "confirm":
        user.refresh_from_db()
        if not user.totp_pending_enc:
            error = "Start the setup again."
        elif security.verify_totp(user.pk, request.POST.get("code", ""), secret_field="totp_pending_enc"):
            codes = security.enable_mfa(user)
            request.session["mfa_passed"] = True
            audit(request, "mfa_enable", "user", user.pk, "Turned on two-factor sign-in")
        else:
            secret = decrypt(user.totp_pending_enc)
            qr = _qr_svg(security.otpauth_uri(user, secret))
            error = "That code isn't right. Check the time on your phone and use the newest code."
    return render(request, "accounts/mfa_setup.html", {
        "error": error, "codes": codes, "qr": qr, "secret": secret, "required": security.mfa_required(user),
        "needs_password": user.mfa_enabled and not qr and not codes,
    })


@login_required
def my_security_view(request):
    user = request.user
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "end_session":
            if request.POST.get("fp") == "all":
                security.revoke_sessions(user, except_key=request.session.session_key)
                audit(request, "session_revoke", "user", user.pk, "Signed out all other sessions")
            else:
                _end_one(user, request)
            messages.success(request, "Signed out.")
        elif action == "disable_mfa":
            if security.mfa_required(user):
                messages.error(request, "Two-factor sign-in is required for your account.")
            elif not user.check_password(request.POST.get("password", "")):
                messages.error(request, "Your password isn't right.")
            else:
                User.objects.filter(pk=user.pk).update(mfa_enabled=False, totp_secret_enc="", totp_pending_enc="")
                user.recovery_codes.all().delete()
                audit(request, "mfa_disable", "user", user.pk, "Turned off two-factor sign-in")
                messages.success(request, "Two-factor sign-in is off.")
        return redirect("/settings/my_security/")
    sessions = UserSession.objects.filter(user=user, revoked_at__isnull=True).order_by("-last_seen_at")
    return render(request, "accounts/my_security.html", {
        "sessions": sessions, "current": request.session.session_key, "required": security.mfa_required(user),
        "codes_left": user.recovery_codes.filter(used_at__isnull=True).count(),
    })


def _end_one(user, request):
    s = UserSession.objects.filter(user=user, fingerprint=request.POST.get("fp", "")).exclude(session_key=request.session.session_key).first()
    if s:
        from django.contrib.sessions.models import Session
        Session.objects.filter(session_key=s.session_key).delete()
        s.revoked_at = timezone.now()
        s.save(update_fields=["revoked_at"])
        audit(request, "session_revoke", "user", user.pk, "Signed out another session")


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "title", "phone"]
        widgets = {f: forms.TextInput(attrs={"class": "input"}) for f in ["name", "title", "phone"]}


@login_required
def profile_view(request):
    user = request.user
    if request.method == "POST" and request.POST.get("tickets_ui") in ("classic", "grid"):
        User.objects.filter(pk=user.pk).update(tickets_ui=request.POST["tickets_ui"])
        messages.success(request, "Ticket screen changed.")
        return redirect("/profile/")
    if request.method == "POST" and request.POST.get("menu_style") in ("icons", "list"):
        User.objects.filter(pk=user.pk).update(menu_style=request.POST["menu_style"])
        return redirect("/profile/")
    from apps.core.themes import BY_KEY
    from apps.core.ui_styles import BY_KEY as STYLE_KEYS
    if request.method == "POST" and request.POST.get("ui_style") in STYLE_KEYS:
        User.objects.filter(pk=user.pk).update(ui_style=request.POST["ui_style"])
        messages.success(request, "Style changed.")
        return redirect("/profile/")
    if request.method == "POST" and request.POST.get("look") in BY_KEY:
        User.objects.filter(pk=user.pk).update(look=request.POST["look"])
        messages.success(request, "Look changed.")
        return redirect("/profile/")
    form = ProfileForm(request.POST or None, instance=user)
    if request.method == "POST" and form.is_valid():
        form.save()
        audit(request, "update", "user", user.pk, "Updated own profile")
        messages.success(request, "Profile saved.")
        return redirect("/profile/")
    return render(request, "accounts/profile.html", {"themes": __import__("apps.core.themes", fromlist=["THEMES"]).THEMES, "styles": __import__("apps.core.ui_styles", fromlist=["STYLES"]).STYLES, "form": form,
                                                     "app_version": __import__("django.conf", fromlist=["settings"]).settings.APP_VERSION})


# ── Staff users (Settings › Staff users) ──
def _temp_password() -> str:
    alphabet = string.ascii_letters.replace("l", "").replace("I", "").replace("O", "") + "23456789"
    return "".join(secrets.choice(alphabet) for _ in range(14))


class UserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "role", "hr_access", "google_only", "title", "phone"]
        widgets = {
            "name": forms.TextInput(attrs={"class": "input"}), "email": forms.EmailInput(attrs={"class": "input"}),
            "role": forms.Select(attrs={"class": "select"}), "title": forms.TextInput(attrs={"class": "input"}),
            "phone": forms.TextInput(attrs={"class": "input"}),
        }

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise ValidationError("Someone already uses that email address.")
        return email


@login_required
def users_view(request):
    if not can(request.user, "admin", "view"):
        raise PermissionDenied
    users = User.objects.order_by("-is_active", "name")
    return render(request, "accounts/users.html", {"users": users, "can_manage": can(request.user, "admin", "manage"), "now": timezone.now()})


@login_required
def user_edit_view(request, pk=None):
    if not can(request.user, "admin", "manage"):
        raise PermissionDenied
    obj = get_object_or_404(User, pk=pk) if pk else None
    form = UserForm(request.POST or None, instance=obj)
    temp = None
    if request.method == "POST":
        action = request.POST.get("action", "save")
        if action == "save" and form.is_valid():
            if obj and obj.pk == request.user.pk and form.cleaned_data["role"] != "admin":
                form.add_error("role", "You can't remove your own admin role.")
            else:
                changed = form.changed_data
                u = form.save(commit=False)
                if not obj:
                    temp = _temp_password()
                    u.set_password(temp)
                    u.must_change_password = True
                u.save()
                if obj and ({"role", "hr_access"} & set(changed)):
                    security.revoke_sessions(u)  # permissions changed: sign in again
                audit(request, "update" if obj else "create", "user", u.pk, f"{'Updated' if obj else 'Added'} user {u.email}", changes={k: str(form.cleaned_data[k]) for k in changed})
                if obj:
                    return _hx_refresh()
                obj = u
        elif obj and action in ("reset_password", "reset_mfa", "unlock", "archive", "restore", "sign_out"):
            if obj.pk == request.user.pk and action in ("archive", "reset_mfa"):
                raise PermissionDenied
            if action == "reset_password":
                temp = _temp_password()
                obj.set_password(temp)
                obj.must_change_password = True
                obj.failed_logins = obj.mfa_failures = 0
                obj.locked_until = None
                obj.save()
                security.revoke_sessions(obj)
            elif action == "reset_mfa":
                User.objects.filter(pk=obj.pk).update(mfa_enabled=False, totp_secret_enc="", totp_pending_enc="", totp_last_step=None)
                obj.recovery_codes.all().delete()
                security.revoke_sessions(obj)
            elif action == "unlock":
                User.objects.filter(pk=obj.pk).update(failed_logins=0, mfa_failures=0, locked_until=None)
            elif action == "archive":
                User.objects.filter(pk=obj.pk).update(is_active=False)
                security.revoke_sessions(obj)
            elif action == "restore":
                User.objects.filter(pk=obj.pk).update(is_active=True)
            elif action == "sign_out":
                security.revoke_sessions(obj)
            audit(request, f"user_{action}", "user", obj.pk, f"{action.replace('_', ' ')} for {obj.email}")
            obj.refresh_from_db()
            if not temp:
                return _hx_refresh()
    return render(request, "accounts/user_form.html", {"form": form, "obj": obj, "temp": temp, "roles": ROLES, "now": timezone.now()})


def _hx_refresh():
    from django.http import HttpResponse
    r = HttpResponse(status=204)
    r["HX-Refresh"] = "true"
    return r


@login_required
def security_log_view(request):
    if not can(request.user, "admin", "view"):
        raise PermissionDenied
    return render(request, "accounts/security_log.html", {"rows": LoginAttempt.objects.order_by("-created_at")[:300]})
