from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.choices import C
from apps.crm.models import Client, Contact

PRIORITIES = ["Critical", "High", "Medium", "Low"]
STATUSES = ["New", "Open", "Waiting on client", "Waiting on vendor", "Scheduled", "Resolved", "Closed"]
OPEN_STATUSES = ["New", "Open", "Waiting on client", "Waiting on vendor", "Scheduled"]
PAUSED_STATUSES = ["Waiting on client", "Waiting on vendor"]
SOURCES = ["Manual", "Email", "Portal", "Phone", "Alert", "Import"]
# Minutes to first response when the client has no tighter SLA of its own.
DEFAULT_RESPONSE_MINUTES = {"Critical": 60, "High": 240, "Medium": 1440, "Low": 4320}


class Ticket(models.Model):
    number = models.CharField(max_length=30, unique=True)
    subject = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    contact_name = models.CharField(max_length=150, blank=True)
    contact_email = models.EmailField(blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="assigned_tickets")
    priority = models.CharField(max_length=10, choices=C(*PRIORITIES), default="Medium")
    status = models.CharField(max_length=30, choices=C(*STATUSES), default="New", db_index=True)
    category = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=10, choices=C(*SOURCES), default="Manual")
    billable = models.BooleanField(default=True)
    due_date = models.DateField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    sla_breached = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    imported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]

    def __str__(self):
        return f"{self.number} {self.subject}"

    @property
    def is_open(self):
        return self.status in OPEN_STATUSES

    @property
    def sla(self) -> str:
        """done · paused · ok · risk (under an hour left) · breached"""
        if not self.is_open:
            return "done"
        if self.status in PAUSED_STATUSES:
            return "paused"
        if self.first_response_at or not self.response_due_at:
            return "ok"
        left = (self.response_due_at - timezone.now()).total_seconds()
        return "breached" if left < 0 else "risk" if left < 3600 else "ok"


class TicketMessage(models.Model):
    KINDS = [("reply", "Reply"), ("note", "Internal note"), ("event", "Event")]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    kind = models.CharField(max_length=10, choices=KINDS)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    author_name = models.CharField(max_length=200, blank=True)
    via = models.CharField(max_length=20, default="web")
    body = models.TextField()
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]

    @property
    def who(self):
        return self.author_name or (self.author.name if self.author else "Unknown")


class TimeEntry(models.Model):
    WORK_TYPES = C("Remote", "On-site", "Phone", "Travel", "Project")
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="time_entries")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    minutes = models.PositiveIntegerField()
    work_type = models.CharField(max_length=20, choices=WORK_TYPES, default="Remote")
    description = models.TextField(blank=True)
    billable = models.BooleanField(default=True)
    work_date = models.DateField()
    invoice = models.ForeignKey("billing.Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
