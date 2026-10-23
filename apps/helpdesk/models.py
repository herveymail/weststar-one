from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.core.choices import C
from apps.crm.models import Client, Contact

PRIORITIES = ["Critical", "High", "Medium", "Low"]
STATUSES = ["New", "Open", "In progress", "Waiting on client", "Waiting on vendor", "Scheduled", "Resolved", "Closed"]
OPEN_STATUSES = ["New", "Open", "In progress", "Waiting on client", "Waiting on vendor", "Scheduled"]
DONE_STATUSES = ["Resolved", "Closed"]
WORK_TYPES = ["Remote", "On-site", "Phone", "Travel", "Project"]
CATEGORIES = ["Remote Support", "Onsite Support", "Server Maintenance", "Network/Firewall", "Backup & Recovery", "Security/Antivirus",
              "Email/Google Workspace", "Hardware Repair", "Software Install", "New User Setup", "Offboarding", "Project Work",
              "Vendor Coordination", "Documentation", "Monitoring Alert", "Other"]


def _short(secs: float) -> str:
    m = int(secs // 60)
    return f"{m}m" if m < 60 else f"{m // 60}h {m % 60}m" if m < 1440 else f"{m // 1440}d"


class Queue(models.Model):
    """Help desk queues (Level 1, Level 2, Billing …). The portal shows `portal_label` as "What do you need help with?"."""
    name = models.CharField(max_length=80, unique=True)
    description = models.CharField(max_length=255, blank=True)
    color = models.CharField(max_length=7, default="#2c5cc5")
    sla_enabled = models.BooleanField("Track SLA", default=True)
    keywords = models.TextField(blank=True, help_text="Comma-separated words that route new tickets here.")
    portal_label = models.CharField("Shown in the portal as", max_length=120, blank=True, help_text="Leave blank to hide from the portal.")
    escalate_to = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    is_default = models.BooleanField(default=False)
    active = models.BooleanField(default=True)
    sort = models.PositiveIntegerField(default=0)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)

    class Meta:
        ordering = ["sort", "name"]

    def __str__(self):
        return self.name
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
    queue = models.ForeignKey(Queue, null=True, blank=True, on_delete=models.SET_NULL, related_name="tickets")
    cc = models.TextField("Also notify", blank=True, help_text="Comma-separated email addresses that get copies of replies.")
    snoozed_until = models.DateTimeField(null=True, blank=True)
    merged_into = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="merged_from")
    resolution = models.TextField(blank=True)
    source = models.CharField(max_length=10, choices=C(*SOURCES), default="Manual")
    billable = models.BooleanField(default=True)
    due_date = models.DateField(null=True, blank=True)
    response_due_at = models.DateTimeField(null=True, blank=True)
    first_response_at = models.DateTimeField(null=True, blank=True)
    resolve_due_at = models.DateTimeField(null=True, blank=True)
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

    @property
    def is_snoozed(self):
        return bool(self.snoozed_until and self.snoozed_until > timezone.now())

    @property
    def sla_chips(self) -> list[dict]:
        """Small SLA badges like the old app: [{'text': 'Respond in 18m', 'tone': 'bad'|'warn'|'ok'|'muted'}]."""
        if not self.is_open:
            return []
        if self.status in PAUSED_STATUSES:
            return [{"text": "SLA paused", "tone": "muted"}]
        now, chips = timezone.now(), []
        for label, due, done in (("Respond", self.response_due_at, self.first_response_at), ("Resolve", self.resolve_due_at, None)):
            if not due or done:
                continue
            secs = (due - now).total_seconds()
            if secs < 0:
                chips.append({"text": f"{label} overdue {_short(-secs)}", "tone": "bad"})
            elif secs < 3600 * (1 if label == "Respond" else 4):
                chips.append({"text": f"{label} in {_short(secs)}", "tone": "warn" if secs > 900 else "bad"})
        return chips


class TicketMessage(models.Model):
    KINDS = [("reply", "Reply"), ("note", "Internal note"), ("work", "Work log"), ("event", "Event")]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="messages")
    kind = models.CharField(max_length=10, choices=KINDS)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    author_name = models.CharField(max_length=200, blank=True)
    via = models.CharField(max_length=20, default="web")
    portal_user = models.ForeignKey("portal.PortalUser", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    cc = models.TextField(blank=True)
    body = models.TextField()
    email_message_id = models.CharField(max_length=255, blank=True, db_index=True)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["created_at", "id"]

    @property
    def public(self):
        """Shown to the client in the portal (replies only, never notes, work logs or events)."""
        return self.kind == "reply"

    @property
    def from_client(self):
        return self.via in ("portal", "email", "client") and self.author_id is None

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


class TicketTimer(models.Model):
    """A running "Start timer" for one tech on one ticket; stopping it logs the time."""
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="timers")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="+")
    started_at = models.DateTimeField(default=timezone.now)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["ticket", "user"], name="one_timer_per_ticket_user")]


class InboundEmail(models.Model):
    """One row per email read from the support mailbox: what happened to it (also stops duplicates)."""
    RESULTS = [("ticket", "New ticket"), ("reply", "Added to ticket"), ("skipped", "Skipped"), ("error", "Problem")]
    message_id = models.CharField(max_length=255, unique=True)
    uid = models.BigIntegerField(null=True, blank=True)
    from_address = models.CharField(max_length=254, blank=True)
    from_name = models.CharField(max_length=200, blank=True)
    subject = models.CharField(max_length=255, blank=True)
    result = models.CharField(max_length=10, choices=RESULTS)
    note = models.CharField(max_length=500, blank=True)
    ticket = models.ForeignKey(Ticket, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    received_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-received_at", "-id"]
