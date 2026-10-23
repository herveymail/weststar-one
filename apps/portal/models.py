"""Client portal: client people who sign in to see their tickets, invoices, quotes, contracts and more.

Portal users are completely separate from staff accounts (own table, own sign-in, own session cookie),
so a portal session can never reach a staff page.
"""
import hashlib

from django.contrib.auth.hashers import check_password, make_password
from django.db import models
from django.db.models.functions import Lower
from django.utils import timezone

from apps.core.models import EncryptedField

PERMS = [
    ("billing", "Invoices & quotes"),
    ("contracts", "Contracts"),
    ("policies", "Policies"),
    ("assets", "Assets"),
    ("submit_tickets", "Open tickets"),
    ("all_tickets", "See all company tickets"),
    ("messages", "Secure messages"),
    ("kb", "Help articles"),
]


class PortalGroup(models.Model):
    name = models.CharField(max_length=200, unique=True)
    description = models.CharField(max_length=255, blank=True)
    can_billing = models.BooleanField("Invoices & quotes", default=False)
    can_contracts = models.BooleanField("Contracts", default=False)
    can_policies = models.BooleanField("Policies", default=True)
    can_assets = models.BooleanField("Assets", default=True)
    can_submit_tickets = models.BooleanField("Open tickets", default=True)
    can_all_tickets = models.BooleanField("See all company tickets", default=False)
    can_messages = models.BooleanField("Secure messages", default=True)
    can_kb = models.BooleanField("Help articles", default=True)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PortalUser(models.Model):
    ROLES = [("standard", "Standard"), ("admin", "Client admin")]
    client = models.ForeignKey("crm.Client", on_delete=models.CASCADE, related_name="portal_users")
    contact = models.ForeignKey("crm.Contact", null=True, blank=True, on_delete=models.SET_NULL, related_name="portal_users")
    name = models.CharField(max_length=200)
    email = models.EmailField(max_length=254)
    password = models.CharField(max_length=255, blank=True)  # empty = hasn't set one yet (invite pending)
    role = models.CharField(max_length=10, choices=ROLES, default="standard",
                            help_text="Client admins see every ticket for their company and can invite coworkers.")
    group = models.ForeignKey(PortalGroup, null=True, blank=True, on_delete=models.SET_NULL, related_name="users",
                              help_text="A group's permissions replace the boxes below.")
    can_billing = models.BooleanField("Invoices & quotes", default=False)
    can_contracts = models.BooleanField("Contracts", default=False)
    can_policies = models.BooleanField("Policies", default=True)
    can_assets = models.BooleanField("Assets", default=True)
    can_submit_tickets = models.BooleanField("Open tickets", default=True)
    can_all_tickets = models.BooleanField("See all company tickets", default=False)
    can_messages = models.BooleanField("Secure messages", default=True)
    can_kb = models.BooleanField("Help articles", default=True)
    is_active = models.BooleanField(default=True)
    mfa_enabled = models.BooleanField(default=False)
    totp_secret_enc = EncryptedField()
    totp_pending_enc = EncryptedField()
    totp_last_step = models.BigIntegerField(null=True, blank=True)
    failed_logins = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    last_login = models.DateTimeField(null=True, blank=True)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [models.UniqueConstraint(Lower("email"), name="portal_email_unique_ci")]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    def save(self, *args, **kwargs):
        self.email = (self.email or "").strip().lower()
        super().save(*args, **kwargs)

    # ── passwords (Argon2; old bcrypt hashes from the PHP portal still work and get upgraded) ──
    def set_password(self, raw: str) -> None:
        self.password = make_password(raw)

    def check_password(self, raw: str) -> bool:
        def upgrade(new_raw):
            self.set_password(new_raw)
            PortalUser.objects.filter(pk=self.pk).update(password=self.password)
        return bool(self.password) and check_password(raw, self.password, upgrade)

    @property
    def has_password(self) -> bool:
        return bool(self.password) and not self.password.startswith("!")

    # ── what this person may see ──
    def can(self, perm: str) -> bool:
        if perm == "tickets":
            return True  # everyone sees their own tickets
        if perm == "all_tickets" and self.role == "admin":
            return True
        src = self.group if self.group_id else self
        return bool(getattr(src, f"can_{perm}", False))

    @property
    def first_name(self):
        return (self.name or self.email).split()[0]


class PortalToken(models.Model):
    """One-use links: password reset (1 hour), sign-in link (15 minutes), invitation (7 days).
    Only a SHA-256 of the token is stored."""
    KINDS = [("reset", "Password reset"), ("magic", "Sign-in link"), ("invite", "Invitation")]
    user = models.ForeignKey(PortalUser, on_delete=models.CASCADE, related_name="tokens")
    kind = models.CharField(max_length=10, choices=KINDS)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @staticmethod
    def hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()


class QuoteApproval(models.Model):
    quote = models.ForeignKey("billing.Quote", on_delete=models.CASCADE, related_name="approvals")
    portal_user = models.ForeignKey(PortalUser, null=True, on_delete=models.SET_NULL, related_name="+")
    decision = models.CharField(max_length=10, choices=[("accepted", "Accepted"), ("declined", "Declined")])
    signed_name = models.CharField(max_length=200)
    comment = models.TextField(blank=True)
    total = models.DecimalField(max_digits=14, decimal_places=2, null=True)
    ip = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class ContractSignature(models.Model):
    contract = models.ForeignKey("billing.Contract", on_delete=models.CASCADE, related_name="signatures")
    portal_user = models.ForeignKey(PortalUser, null=True, on_delete=models.SET_NULL, related_name="+")
    signed_name = models.CharField(max_length=200)
    signed_title = models.CharField(max_length=200, blank=True)
    content_hash = models.CharField(max_length=64, help_text="SHA-256 of the contract text that was signed.")
    ip = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class PolicyAck(models.Model):
    policy = models.ForeignKey("billing.Policy", on_delete=models.CASCADE, related_name="acks")
    portal_user = models.ForeignKey(PortalUser, null=True, on_delete=models.SET_NULL, related_name="policy_acks")
    version = models.CharField(max_length=20, blank=True)
    signed_name = models.CharField(max_length=200)
    ip = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
