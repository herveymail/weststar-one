"""Uploaded files: ticket attachments, client files and project files.

Files live in MEDIA_ROOT, which is never served directly by the web server. Every download goes
through files.views.download, which checks the person's access first.
"""
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

KINDS = [("ticket", "Ticket"), ("client", "Client"), ("project", "Project")]
# Same list the old app allowed, so imported files and new uploads follow one rule.
ALLOWED_EXT = {"pdf", "doc", "docx", "xls", "xlsx", "csv", "txt", "log", "png", "jpg", "jpeg", "gif", "webp", "heic", "zip", "7z", "msg", "eml"}
INLINE_EXT = {"png", "jpg", "jpeg", "gif", "webp", "pdf"}
AREA = {"ticket": "tickets", "client": "clients", "project": "projects"}


def stored_path(instance, filename):
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    owner = instance.ticket_id or instance.client_id or instance.project_id or 0
    return f"{instance.kind}s/{owner}/{timezone.now():%Y%m}-{secrets.token_hex(12)}.{ext}"


class Upload(models.Model):
    kind = models.CharField(max_length=10, choices=KINDS)
    ticket = models.ForeignKey("helpdesk.Ticket", null=True, blank=True, on_delete=models.CASCADE, related_name="uploads")
    message = models.ForeignKey("helpdesk.TicketMessage", null=True, blank=True, on_delete=models.SET_NULL, related_name="uploads")
    client = models.ForeignKey("crm.Client", null=True, blank=True, on_delete=models.CASCADE, related_name="uploads")
    project = models.ForeignKey("crm.Project", null=True, blank=True, on_delete=models.CASCADE, related_name="uploads")
    file = models.FileField(upload_to=stored_path, max_length=255)
    original_name = models.CharField(max_length=255)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)
    notes = models.CharField(max_length=500, blank=True)
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    uploaded_by_name = models.CharField(max_length=200, blank=True)
    legacy_id = models.CharField(max_length=40, null=True, blank=True, unique=True)  # "ticket:12", "client:4"…
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return self.original_name

    @property
    def ext(self):
        return self.original_name.rsplit(".", 1)[-1].lower() if "." in self.original_name else ""

    @property
    def area(self):
        return AREA[self.kind]

    @property
    def who(self):
        return self.uploaded_by.name if self.uploaded_by else (self.uploaded_by_name or "Imported")
