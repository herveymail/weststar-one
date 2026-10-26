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
SOURCES = ["Manual", "Email", "Portal", "Phone", "Alert", "MSP360", "Import"]
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
    # AI (Settings › AI assistant): triage suggestion waiting for a person to apply or dismiss
    ai_triage = models.JSONField(null=True, blank=True, editable=False)
    ai_triage_status = models.CharField(max_length=12, blank=True, editable=False)  # suggested / applied / dismissed / none
    ai_summary = models.TextField(blank=True, editable=False)
    ai_summary_at = models.DateTimeField(null=True, blank=True, editable=False)
    ai_first_response = models.CharField(max_length=12, blank=True, editable=False)  # sent / skipped
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


def _grid_short(secs: float) -> str:
    secs = abs(secs)
    if secs < 3600:
        return f"{max(1, int(secs // 60))}m"
    if secs < 86400:
        return f"{secs / 3600:.1f}".rstrip("0").rstrip(".") + "h"
    return f"{secs / 86400:.1f}".rstrip("0").rstrip(".") + "d"


def grid_sla(t) -> list[dict]:
    """The old grid's SLA chips: 'Resp 57m' (green), 'Resolve overdue 2h' (red), 'Resolve paused' (grey)."""
    if not t.is_open:
        return []
    now, out = timezone.now(), []
    for short, noun, due, done in (("Resp", "Response", t.response_due_at, t.first_response_at), ("Resolve", "Resolution", t.resolve_due_at, None)):
        if not due or done:
            continue
        if t.status in PAUSED_STATUSES:
            out.append({"cls": "muted", "text": f"{short} paused", "title": f"{noun} clock paused (waiting on the client)"})
            continue
        left = (due - now).total_seconds()
        warn_at = 3600 if short == "Resp" else 4 * 3600
        if left < 0:
            out.append({"cls": "bad", "text": f"{short} overdue {_grid_short(left)}", "title": f"{noun} target missed by {_grid_short(left)}"})
        else:
            out.append({"cls": "warn" if left < warn_at else "ok", "text": f"{short} {_grid_short(left)}", "title": f"{noun} due in {_grid_short(left)}"})
    return out


Ticket.grid_sla = property(grid_sla)


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


class AiLog(models.Model):
    """What the AI assistant did (like the old app's ticket_ai_log)."""
    feature = models.CharField(max_length=20)   # triage / suggest / firstresponse / summary / selfhelp
    outcome = models.CharField(max_length=30)
    ticket = models.ForeignKey(Ticket, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    detail = models.CharField(max_length=500, blank=True)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


class TicketSignoff(models.Model):
    """Customer sign-off (old app 2026.0.89). completion: break/fix customer confirms the work is done, working, and
    agrees to the charges. dropoff: customer confirms they received equipment. A tech may override with a reason."""
    TYPES = [("completion", "Work completed"), ("dropoff", "Drop-off")]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="signoffs")
    type = models.CharField(max_length=12, choices=TYPES)
    signer_name = models.CharField(max_length=200, blank=True)
    signer_title = models.CharField(max_length=100, blank=True)
    signer_email = models.EmailField(blank=True)
    signature = models.TextField(blank=True)  # PNG data: URL, checked on save
    summary = models.TextField(blank=True)
    items = models.TextField(blank=True)
    hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    rate = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    parts_desc = models.CharField(max_length=255, blank=True)
    parts_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    tax_rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    total = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    statement = models.TextField(blank=True)
    hash = models.CharField(max_length=64, blank=True)
    overridden = models.BooleanField(default=False)
    override_reason = models.TextField(blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ip = models.CharField(max_length=45, blank=True)
    via = models.CharField(max_length=20, default="web")
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]


class TicketApproval(models.Model):
    """Scope/budget approval log: the client OK'd out-of-scope or over-budget work (protects against billing disputes)."""
    VIA = [("email", "Email"), ("phone", "Phone"), ("in_person", "In person"), ("text", "Text message"), ("portal", "Portal")]
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="approvals")
    description = models.CharField(max_length=500)
    approved_by = models.CharField(max_length=200, blank=True)
    via = models.CharField(max_length=20, choices=VIA, default="email")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-created_at"]
