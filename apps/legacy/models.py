from django.conf import settings
from django.db import models

from apps.core.models import EncryptedField


class ImportRun(models.Model):
    STATUSES = [("queued", "Waiting to start"), ("running", "Running"), ("done", "Finished"), ("failed", "Failed")]
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    dry_run = models.BooleanField(default=False)
    summary = models.JSONField(null=True, blank=True)
    error = models.TextField(blank=True)
    # Uploaded through Settings › Import (the background jobs worker does the work).
    status = models.CharField(max_length=10, choices=STATUSES, default="done")
    log = models.TextField(blank=True)
    work_dir = models.CharField(max_length=300, blank=True)  # uploaded files; deleted when the run ends
    dump_name = models.CharField(max_length=255, blank=True)
    uploads_name = models.CharField(max_length=255, blank=True)
    old_app_key = EncryptedField()        # cleared when the run ends
    old_encryption_key = EncryptedField()  # cleared when the run ends
    requested_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-started_at"]

    @property
    def total(self):
        return sum(s.get("imported", 0) for s in (self.summary or []))

    @property
    def warnings(self):
        return sum(len(s.get("warnings", [])) for s in (self.summary or []))


class LegacySetting(models.Model):
    """Every setting from the old Weststar One, kept for reference (Settings › Old system settings).
    `mapped_to` is the new setting it was copied into, if the new app has one."""
    key = models.CharField(max_length=191, unique=True)
    value = models.TextField(blank=True)          # plain settings
    secret_value = EncryptedField()               # passwords / keys (decrypted from the old app, encrypted again here)
    is_secret = models.BooleanField(default=False)
    decrypt_failed = models.BooleanField(default=False)
    mapped_to = models.CharField(max_length=191, blank=True)
    copied = models.BooleanField(default=False)   # False when the new app already had its own value
    imported_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["key"]
