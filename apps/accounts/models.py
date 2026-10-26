from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.functions import Lower

from apps.core.permissions import ROLES


class UserManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra):
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user


class User(AbstractBaseUser):
    email = models.EmailField(unique=True, max_length=254)
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=20, choices=ROLES, default="tech")
    hr_access = models.BooleanField("H/R access", default=False)
    title = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    menu_style = models.CharField("Side menu", max_length=10, choices=[("icons", "Icon bar with pop-out menus"), ("list", "Full list, everything open")], default="icons")
    ui_style = models.CharField("Style", max_length=20, choices=[(t[0], t[1]) for t in __import__("apps.core.ui_styles", fromlist=["STYLES"]).STYLES], default="classic")
    look = models.CharField("Theme", max_length=20, choices=[(t[0], t[1]) for t in __import__("apps.core.themes", fromlist=["THEMES"]).THEMES], default="indigo")
    tickets_ui = models.CharField("Ticket screen", max_length=10, choices=[("classic", "Classic (views on the left, full ticket page)"),
                                                                           ("grid", "Grid (sortable table, ticket opens beside it)")], default="classic")
    google_only = models.BooleanField("Must sign in with Google", default=False,
                                      help_text="Their password stops working once Google sign-in is set up (like the old app's linked accounts).")
    google_email = models.EmailField("Google account email (if different)", max_length=254, blank=True, default="",
                                     help_text="Only if they sign in to Google with a different address than their staff email above.")
    google_linked_at = models.DateTimeField(null=True, blank=True, editable=False)
    is_active = models.BooleanField(default=True)  # False = archived (cannot sign in)

    # Two-factor (TOTP). Seeds are encrypted with APP_ENCRYPTION_KEY.
    mfa_enabled = models.BooleanField(default=False)
    totp_secret_enc = models.TextField(blank=True, default="")
    totp_pending_enc = models.TextField(blank=True, default="")
    totp_last_step = models.BigIntegerField(null=True, blank=True)  # a code is accepted only once

    # Lockout. Password failures and 2FA failures are counted separately: a correct password must
    # never reset the 2FA counter (otherwise someone with a stolen password could guess codes forever).
    failed_logins = models.IntegerField(default=0)
    mfa_failures = models.IntegerField(default=0)
    lock_count = models.IntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()
    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    class Meta:
        ordering = ["name"]
        # PostgreSQL compares text case-sensitively: make "Amy@…" and "amy@…" the same account.
        constraints = [models.UniqueConstraint(Lower("email"), name="user_email_unique_ci")]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        self.google_email = (self.google_email or "").strip().lower()
        super().save(*args, **kwargs)

    def get_full_name(self):
        return self.name

    def get_short_name(self):
        return self.name.split(" ")[0] if self.name else self.email

    @property
    def initials(self):
        parts = [p for p in self.name.split() if p][:2]
        return "".join(p[0].upper() for p in parts) or "?"


class RecoveryCode(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="recovery_codes")
    code_hash = models.CharField(max_length=64, db_index=True)
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class UserSession(models.Model):
    """One row per signed-in browser, so people can see and end their sessions and an admin can
    sign someone out everywhere. The session key itself is never shown; `fingerprint` is."""

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sessions")
    session_key = models.CharField(max_length=64, unique=True)
    fingerprint = models.CharField(max_length=16, unique=True)
    ip = models.CharField(max_length=64, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(auto_now_add=True)
    revoked_at = models.DateTimeField(null=True, blank=True)


class LoginAttempt(models.Model):
    email = models.CharField(max_length=254, blank=True)
    ip = models.CharField(max_length=64, blank=True, db_index=True)
    success = models.BooleanField()
    reason = models.CharField(max_length=60, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
