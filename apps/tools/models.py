from django.conf import settings
from django.db import models

from apps.core.choices import C, money
from apps.core.models import EncryptedField, Record
from apps.crm.models import Client, Contact


class CalendarEvent(Record):
    title = models.CharField("Event", max_length=255)
    starts_at = models.DateTimeField("Starts")
    ends_at = models.DateTimeField("Ends", null=True, blank=True)
    who = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    location = models.CharField(max_length=255, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.title


class InventoryItem(Record):
    name = models.CharField("Item", max_length=255)
    sku = models.CharField("SKU", max_length=100, blank=True)
    on_hand = models.IntegerField(default=0)
    reorder_at = models.IntegerField(null=True, blank=True)
    cost = money()
    price = money()
    location = models.CharField("Stored at", max_length=200, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class MileageTrip(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False, verbose_name="Driver")
    trip_date = models.DateField("Date")
    trip = models.CharField("From → To", max_length=255)
    miles = models.DecimalField(max_digits=8, decimal_places=1)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    billable = models.BooleanField(default=False)

    def __str__(self):
        return self.trip


class SecureMessage(Record):
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="+")
    contact = models.ForeignKey(Contact, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    subject = models.CharField(max_length=255)
    direction = models.CharField(max_length=10, choices=C("Inbound", "Outbound"), default="Outbound")
    status = models.CharField(max_length=10, choices=C("Unread", "Read", "Archived"), default="Unread")
    body = EncryptedField("Message")
    # Threads: replies point at the first message of the conversation.
    thread = models.ForeignKey("self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies", editable=False)
    portal_user = models.ForeignKey("portal.PortalUser", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False,
                                    help_text="Empty = for everyone at the client with message access.")
    author = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)
    client_read_at = models.DateTimeField(null=True, blank=True, editable=False)

    def __str__(self):
        return self.subject


class Domain(Record):
    name = models.CharField("Domain", max_length=255)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="domains")
    registrar = models.CharField(max_length=200, blank=True)
    expires_on = models.DateField("Expires", null=True, blank=True)
    dns_provider = models.CharField("DNS provider", max_length=200, blank=True)
    ssl_status = models.CharField("SSL", max_length=20, choices=C("Valid", "Expiring", "Expired", "None", "Unknown"), default="Unknown")
    ssl_expires_on = models.DateField("SSL expires", null=True, blank=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class BackupJob(Record):
    device = models.CharField(max_length=200)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    plan = models.CharField(max_length=200, blank=True)
    last_run_at = models.DateTimeField("Last run", null=True, blank=True)
    last_result = models.CharField("Result", max_length=20, choices=C("Success", "Warning", "Failed", "Running", "Unknown"), default="Unknown")
    storage_gb = models.DecimalField("Storage (GB)", max_digits=10, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return self.device


class RmmDevice(Record):
    name = models.CharField("Device", max_length=200)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    os = models.CharField("OS", max_length=100, blank=True)
    last_seen_at = models.DateTimeField("Last seen", null=True, blank=True)
    status = models.CharField(max_length=20, choices=C("OK", "Warning", "Critical", "Offline"), default="OK")
    rmm_uid = models.CharField("RMM device ID", max_length=100, blank=True)

    def __str__(self):
        return self.name


class KbArticle(Record):
    title = models.CharField("Article", max_length=255)
    category = models.CharField(max_length=100, blank=True)
    visibility = models.CharField(max_length=20, choices=C("Staff only", "Portal", "Draft"), default="Staff only")
    views = models.PositiveIntegerField(default=0, editable=False)
    body = models.TextField("Article", blank=True)

    def __str__(self):
        return self.title


class Workflow(Record):
    name = models.CharField("Workflow", max_length=255)
    trigger = models.CharField("When", max_length=40, choices=C("Ticket created", "Ticket updated", "SLA at risk", "Invoice overdue", "Client created", "Contract expiring"))
    conditions = models.TextField("Only if", blank=True, help_text="Example: priority = Critical")
    action = models.CharField("Then", max_length=40, choices=C("Send email", "Notify Google Chat", "Assign to", "Set priority", "Create task"))
    action_value = models.CharField("Action details", max_length=255, blank=True)
    status = models.CharField(max_length=10, choices=C("Active", "Paused"), default="Paused")
    runs = models.PositiveIntegerField(default=0, editable=False)

    def __str__(self):
        return self.name
