from django.conf import settings
from django.db import models, transaction
from django.db.models import F

from .crypto import decrypt, encrypt


class EncryptedField(models.TextField):
    """Holds ciphertext ("v1:…"). Never decrypted automatically — use get_secret()/set_secret().
    Lists and API responses never include the value; showing it is an explicit, audited action."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("blank", True)
        kwargs.setdefault("default", "")
        super().__init__(*args, **kwargs)


def set_secret(obj, field: str, plain: str | None) -> None:
    setattr(obj, field, encrypt(plain or ""))


def get_secret(obj, field: str) -> str:
    return decrypt(getattr(obj, field))


class Record(models.Model):
    """Base for every business record: who created it, soft-archive, and where it came from."""

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)
    created_at = models.DateTimeField(auto_now_add=True, editable=False)
    updated_at = models.DateTimeField(auto_now=True, editable=False)
    archived_at = models.DateTimeField(null=True, blank=True, editable=False)
    # Set for rows that came from the old PHP Weststar One.
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True, editable=False)
    imported_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True


class AuditLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    action = models.CharField(max_length=40)
    entity = models.CharField(max_length=60, db_index=True)
    entity_id = models.CharField(max_length=60, blank=True)
    # Permission area of the record, so people only see audit entries for areas they can see.
    area = models.CharField(max_length=20, blank=True, db_index=True)
    summary = models.CharField(max_length=500, blank=True)
    changes = models.JSONField(null=True, blank=True)
    ip = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class Setting(models.Model):
    key = models.CharField(max_length=120, primary_key=True)
    value = models.TextField(blank=True, default="")
    is_secret = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    updated_at = models.DateTimeField(auto_now=True)

    @classmethod
    def get(cls, key: str, default: str = "") -> str:
        row = cls.objects.filter(key=key).first()
        if row is None:
            return default
        if row.is_secret:
            try:
                return decrypt(row.value)
            except Exception:  # noqa: BLE001
                return default
        return row.value

    @classmethod
    def put(cls, key: str, value: str, secret: bool = False, user=None) -> None:
        cls.objects.update_or_create(key=key, defaults={"value": encrypt(value) if secret else value, "is_secret": secret, "updated_by": user})


class Counter(models.Model):
    """Number sequences: tickets, invoices, quotes …"""

    name = models.CharField(max_length=60, primary_key=True)
    value = models.BigIntegerField()

    @classmethod
    def next(cls, name: str, start: int) -> int:
        with transaction.atomic():
            row, created = cls.objects.select_for_update().get_or_create(name=name, defaults={"value": start})
            if created:
                return start
            cls.objects.filter(pk=name).update(value=F("value") + 1)
            row.refresh_from_db()
            return row.value

    @classmethod
    def at_least(cls, name: str, value: int) -> None:
        with transaction.atomic():
            row, created = cls.objects.select_for_update().get_or_create(name=name, defaults={"value": value})
            if not created and row.value < value:
                cls.objects.filter(pk=name).update(value=value)


class JobRun(models.Model):
    name = models.CharField(max_length=60, primary_key=True)
    last_run_at = models.DateTimeField(null=True)
    last_result = models.TextField(blank=True)
    last_ok = models.BooleanField(default=True)


class BackupRun(models.Model):
    """Backups made (or restores done) from Settings › Backups, by a person or the nightly job."""
    KINDS = [("backup", "Backup"), ("restore", "Restore")]
    kind = models.CharField(max_length=10, choices=KINDS, default="backup")
    status = models.CharField(max_length=10, default="queued")  # queued / running / done / failed
    trigger = models.CharField(max_length=20, default="manual")  # manual / nightly / before-restore
    name = models.CharField(max_length=100, blank=True)  # e.g. ws_2026-11-10_0230 (files: <name>.dump, <name>_files.tar.gz)
    db_bytes = models.BigIntegerField(default=0)
    files_bytes = models.BigIntegerField(default=0)
    offsite = models.CharField(max_length=200, blank=True)  # "" / "copied" / error text
    message = models.TextField(blank=True)
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]


class OutboxEmail(models.Model):
    """An email waiting to go out. Ticket emails are queued here so the screen updates straight away;
    a background thread sends them a moment later and the jobs loop retries any that failed."""

    STATUSES = [("pending", "Waiting"), ("sending", "Sending"), ("sent", "Sent"), ("failed", "Failed")]
    status = models.CharField(max_length=10, choices=STATUSES, default="pending", db_index=True)
    to = models.TextField()
    cc = models.TextField(blank=True)
    subject = models.CharField(max_length=255)
    payload = models.JSONField()  # body, html, from, reply_to, headers, attachments (base64)
    after = models.JSONField(null=True, blank=True)  # what to record on the ticket once it's sent
    tries = models.PositiveSmallIntegerField(default=0)
    last_error = models.TextField(blank=True)
    next_try_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]


class SlowRequest(models.Model):
    """Pages or saves that took longer than a second — shown on Settings › Speed & server health."""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    method = models.CharField(max_length=8)
    path = models.CharField(max_length=300)
    status = models.PositiveSmallIntegerField(default=0)
    total_ms = models.PositiveIntegerField()
    db_ms = models.PositiveIntegerField(default=0)
    queries = models.PositiveIntegerField(default=0)
    user = models.CharField(max_length=150, blank=True)

    class Meta:
        ordering = ["-created_at"]


class LegalAcceptance(models.Model):
    """Someone agreed to a legal text (Settings › Legal & terms): which one, which version, when, from where."""
    doc = models.CharField(max_length=40, db_index=True)
    version = models.CharField(max_length=20)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="legal_acceptances")
    portal_user = models.ForeignKey("portal.PortalUser", null=True, blank=True, on_delete=models.CASCADE, related_name="legal_acceptances")
    signed_name = models.CharField(max_length=200, blank=True)
    ip = models.CharField(max_length=45, blank=True)
    accepted_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-accepted_at"]
