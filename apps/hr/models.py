from django.conf import settings
from django.db import models

from apps.core.choices import C
from apps.core.models import EncryptedField, Record


class Employee(Record):
    name = models.CharField("Employee", max_length=200)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Login account")
    title = models.CharField(max_length=100, blank=True)
    office = models.CharField(max_length=20, choices=C("El Paso", "Phoenix", "Remote"), blank=True)
    status = models.CharField(max_length=20, choices=C("Active", "Onboarding", "On leave", "Terminated"), default="Active")
    hire_date = models.DateField("Started", null=True, blank=True)
    email = models.EmailField("Work email", blank=True)
    phone = models.CharField(max_length=50, blank=True)
    pay_type = models.CharField(max_length=10, choices=C("Hourly", "Salary"), blank=True)
    pto_balance_hours = models.DecimalField("PTO balance (hours)", max_digits=8, decimal_places=2, null=True, blank=True)
    ssn = EncryptedField("SSN")
    bank_routing = EncryptedField("Bank routing #")
    bank_account = EncryptedField("Bank account #")
    emergency_contact = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name


class TimeOffRequest(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False, verbose_name="Employee")
    kind = models.CharField("Type", max_length=20, choices=C("Vacation", "Sick", "Personal", "Unpaid"), default="Vacation")
    starts_on = models.DateField("From")
    ends_on = models.DateField("To")
    hours = models.DecimalField(max_digits=6, decimal_places=2)
    status = models.CharField(max_length=10, choices=C("Pending", "Approved", "Denied"), default="Pending")
    reason = models.CharField("Note", max_length=255, blank=True)

    def __str__(self):
        return f"{self.kind} {self.starts_on}"


class TimeclockEntry(Record):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False, verbose_name="Employee")
    clock_in = models.DateTimeField()
    clock_out = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=C("Open", "Submitted", "Approved"), default="Open")
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name_plural = "timeclock entries"

    def __str__(self):
        return f"{self.clock_in:%Y-%m-%d %H:%M}"
