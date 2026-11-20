from django.conf import settings
from django.db import models

from apps.core.choices import C, money
from apps.core.models import EncryptedField, Record


class Client(Record):
    name = models.CharField("Client name", max_length=200)
    status = models.CharField(max_length=20, choices=C("Active", "Lead", "Inactive", "Former"), default="Active")
    type = models.CharField(max_length=20, choices=C("Business", "Residential", "Nonprofit", "Government"), default="Business")
    plan = models.CharField(max_length=40, choices=C("Managed", "Managed · Gold", "Managed · Silver", "Managed · Bronze", "Break/fix", "Project"), blank=True)
    industry = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    email_domains = models.CharField("Email domains", max_length=500, blank=True,
                                     help_text="Emails from these domains become this client's tickets, e.g. desertdental.com, dd-mail.com")
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    zip = models.CharField("ZIP", max_length=20, blank=True)
    account_manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    hourly_rate = money()
    tax_rate = models.DecimalField("Tax rate %", max_digits=6, decimal_places=3, null=True, blank=True)
    net_terms = models.PositiveIntegerField("Net terms (days)", default=30)
    late_fee_exempt = models.BooleanField("No late fees", default=False, help_text="Never add late fees to this client's invoices.")
    sla_response_hours = models.PositiveIntegerField("SLA response (hours)", default=4)
    sla_resolution_hours = models.PositiveIntegerField("SLA resolution (hours)", default=24)
    # The client's own business hours: shown on its tickets so techs know when they can call or go onsite.
    hours_open = models.TimeField("Opens", null=True, blank=True, help_text="When the client's office opens, their local time.")
    hours_close = models.TimeField("Closes", null=True, blank=True)
    hours_days = models.CharField("Open days", max_length=40, blank=True, default="Mon,Tue,Wed,Thu,Fri", help_text="e.g. Mon,Tue,Wed,Thu,Fri")
    hours_timezone = models.CharField("Their time zone", max_length=40, blank=True, choices=[
        ("", "Same as ours"), ("America/Phoenix", "Arizona (Phoenix)"), ("America/Denver", "Mountain (El Paso, Denver)"), ("America/Chicago", "Central"),
        ("America/Los_Angeles", "Pacific"), ("America/New_York", "Eastern")])
    hours_note = models.CharField("Hours note", max_length=255, blank=True, help_text="e.g. Closed for lunch 12–1. Call the office manager before going onsite.")
    account_alert = models.CharField(max_length=255, blank=True, help_text="Shown in red on every ticket for this client.")
    notes = models.TextField("Internal notes", blank=True)
    # Stripe / AutoPay (the card or bank account itself stays at Stripe; only its ids and last 4 are kept here)
    stripe_customer_id = models.CharField(max_length=64, blank=True, editable=False)
    autopay_enabled = models.BooleanField("AutoPay", default=False, editable=False)
    autopay_method_id = models.CharField(max_length=64, blank=True, editable=False)
    autopay_method_type = models.CharField(max_length=20, blank=True, editable=False)  # card / us_bank_account
    autopay_brand = models.CharField(max_length=30, blank=True, editable=False)
    autopay_last4 = models.CharField(max_length=4, blank=True, editable=False)
    autopay_enrolled_at = models.DateTimeField(null=True, blank=True, editable=False)
    autopay_last_attempt_at = models.DateTimeField(null=True, blank=True, editable=False)
    autopay_last_status = models.CharField(max_length=20, blank=True, editable=False)
    autopay_last_error = models.CharField(max_length=255, blank=True, editable=False)

    class Meta:
        ordering = ["name"]

    @property
    def autopay_label(self) -> str:
        if not self.autopay_method_id:
            return ""
        kind = "Bank account" if self.autopay_method_type == "us_bank_account" else (self.autopay_brand or "Card").title()
        return f"{kind} ending {self.autopay_last4}" if self.autopay_last4 else kind

    def __str__(self):
        return self.name


def domain_list(raw: str) -> list[str]:
    out = []
    for d in (raw or "").replace(";", ",").replace(" ", ",").split(","):
        d = d.strip().lower().lstrip("@")
        if d.startswith("http"):
            d = d.split("//", 1)[-1]
        d = d.split("/", 1)[0].removeprefix("www.")
        if d and "." in d and d not in out:
            out.append(d)
    return out


class Contact(Record):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="contacts")
    name = models.CharField(max_length=200)
    title = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    mobile = models.CharField(max_length=50, blank=True)
    role = models.CharField(max_length=30, choices=C("Decision maker", "Technical", "Billing", "End user", "Other"), default="Other")
    is_primary = models.BooleanField("Primary contact", default=False)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Asset(Record):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="assets")
    name = models.CharField(max_length=200)
    type = models.CharField(max_length=20, choices=C("Workstation", "Laptop", "Server", "Network", "Printer", "Mobile", "Other"), default="Workstation")
    status = models.CharField(max_length=20, choices=C("Active", "Storage", "RMA", "Retired"), default="Active")
    make = models.CharField(max_length=100, blank=True)
    model = models.CharField(max_length=100, blank=True)
    serial = models.CharField(max_length=100, blank=True)
    os = models.CharField("Operating system", max_length=100, blank=True)
    ip = models.CharField("IP address", max_length=45, blank=True)
    mac = models.CharField("MAC address", max_length=17, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    warranty_expires = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Network(Record):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="networks")
    name = models.CharField("Network name", max_length=200)
    subnet = models.CharField(max_length=100, blank=True)
    gateway = models.CharField(max_length=100, blank=True)
    dns = models.CharField("DNS servers", max_length=200, blank=True)
    isp = models.CharField("ISP", max_length=100, blank=True)
    isp_account = EncryptedField("ISP account number")
    wifi_ssid = models.CharField("Wi-Fi name", max_length=100, blank=True)
    wifi_password = EncryptedField("Wi-Fi password")
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class ClientNote(Record):
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="client_notes")
    title = models.CharField(max_length=200)
    body = models.TextField("Note", blank=True)

    def __str__(self):
        return self.title


class Project(Record):
    number = models.CharField("Project #", max_length=30, unique=True, null=True, blank=True, editable=False)
    name = models.CharField("Project", max_length=255)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="projects")
    owner = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=20, choices=C("Planning", "In progress", "On hold", "Complete", "Cancelled"), default="Planning")
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField("Due", null=True, blank=True)
    budget_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    billable = models.BooleanField(default=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.number or ''} {self.name}".strip()


# ── Account flags, text-message log, offboarding ──
class ClientFlag(models.Model):
    """A warning the whole team sees on the client and on every one of its tickets. Cleared flags are kept as history."""
    LEVELS = [("stop", "Stop — check before doing any work"), ("warn", "Warning"), ("info", "Good to know")]
    PRESETS = ["Past due — get approval before any work", "Prepay only", "Do not go onsite", "VIP — call the owner", "Texts staff on personal phones",
               "Offboarding", "Former client — do not service", "Legal hold — do not delete anything"]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="flags")
    label = models.CharField(max_length=120)
    level = models.CharField(max_length=5, choices=LEVELS, default="warn")
    note = models.TextField(blank=True)
    expires_on = models.DateField(null=True, blank=True)
    set_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    cleared_at = models.DateTimeField(null=True, blank=True)
    cleared_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    clear_note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["cleared_at", "-created_at"]

    def __str__(self):
        return self.label

    @property
    def active(self):
        from django.utils import timezone
        return self.cleared_at is None and (self.expires_on is None or self.expires_on >= timezone.localdate())


def active_flags(client):
    """Flags to show right now, most serious first."""
    from django.db.models import Q
    from django.utils import timezone
    if client is None:
        return []
    order = {"stop": 0, "warn": 1, "info": 2}
    qs = client.flags.filter(cleared_at__isnull=True).filter(Q(expires_on__isnull=True) | Q(expires_on__gte=timezone.localdate()))
    return sorted(qs, key=lambda f: (order.get(f.level, 9), -f.pk))


Client.active_flags = property(active_flags)


class ClientText(models.Model):
    """Text messages a client sent to a staff member's own phone, filed here so the record isn't stuck on that phone."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="texts")
    happened_on = models.DateField("Date of the texts")
    staff = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Whose phone")
    contact_name = models.CharField("Who texted", max_length=200, blank=True)
    their_number = models.CharField("Their number", max_length=50, blank=True)
    summary = models.CharField("What it was about", max_length=255)
    transcript = models.TextField("The messages (typed or pasted)", blank=True)
    ticket = models.ForeignKey("helpdesk.Ticket", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-happened_on", "-id"]

    def __str__(self):
        return f"{self.happened_on:%b %-d, %Y} · {self.summary}"


class Offboarding(models.Model):
    """Letting a client go: one checklist, who did each step and when."""
    STEPS = [
        ("passwords", "Return passwords and admin access",
         "Hand over every admin login we hold: Microsoft 365 / Google admin, domain registrar and DNS, firewall, Wi-Fi, servers, backups, line-of-business apps. "
         "Send them securely (never in a ticket or plain email). Write down who received them and how."),
        ("agents", "Remove our agents and our access",
         "Uninstall the RMM agent, antivirus, backup agent and remote-access tools from every computer. Remove our admin accounts, our MFA devices, "
         "and partner / delegated admin access in Microsoft 365 and Google."),
        ("invoice", "Final invoice", "Bill everything still unbilled, send the final invoice, and note the balance they still owe."),
        ("cancel", "Cancel services", "Stop recurring billing, end contracts, cancel renewals and the licences we buy for them, and turn off AutoPay."),
        ("export", "Export their data", "Download their records (contacts, devices, network notes, tickets, invoices, files) and give the client a copy."),
        ("close", "Close the account", "Turn off their portal sign-ins and mark the client Former."),
    ]
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="offboardings")
    status = models.CharField(max_length=10, choices=C("Open", "Done", "Cancelled"), default="Open")
    reason = models.TextField("Why we're parting ways", blank=True)
    last_day = models.DateField("Last day of service", null=True, blank=True)
    started_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    finished_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")

    class Meta:
        ordering = ["-started_at"]

    def steps(self):
        saved = {s.key: s for s in self.step_rows.all()}
        return [{"key": k, "title": t, "hint": h, "row": saved.get(k), "done": bool(saved.get(k) and saved[k].done_at)} for k, t, h in self.STEPS]

    @property
    def left(self):
        return sum(1 for s in self.steps() if not s["done"])


class OffboardingStep(models.Model):
    offboarding = models.ForeignKey(Offboarding, on_delete=models.CASCADE, related_name="step_rows")
    key = models.CharField(max_length=20)
    done_at = models.DateTimeField(null=True, blank=True)
    done_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    note = models.TextField(blank=True)

    class Meta:
        unique_together = [("offboarding", "key")]
