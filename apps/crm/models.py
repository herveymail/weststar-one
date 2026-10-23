from django.conf import settings
from django.db import models

from apps.core.choices import C, money
from apps.core.models import EncryptedField, Record


class Client(Record):
    name = models.CharField("Client name", max_length=200)
    status = models.CharField(max_length=20, choices=C("Active", "Lead", "Inactive", "Former"), default="Active")
    type = models.CharField(max_length=20, choices=C("Business", "Residential", "Nonprofit", "Government"), default="Business")
    plan = models.CharField(max_length=40, choices=C("Managed · Gold", "Managed · Silver", "Managed · Bronze", "Break/fix", "Project"), blank=True)
    industry = models.CharField(max_length=100, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=50, blank=True)
    zip = models.CharField("ZIP", max_length=20, blank=True)
    account_manager = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    hourly_rate = money()
    tax_rate = models.DecimalField("Tax rate %", max_digits=6, decimal_places=3, null=True, blank=True)
    net_terms = models.PositiveIntegerField("Net terms (days)", default=30)
    sla_response_hours = models.PositiveIntegerField("SLA response (hours)", default=4)
    sla_resolution_hours = models.PositiveIntegerField("SLA resolution (hours)", default=24)
    account_alert = models.CharField(max_length=255, blank=True, help_text="Shown in red on every ticket for this client.")
    notes = models.TextField("Internal notes", blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


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
