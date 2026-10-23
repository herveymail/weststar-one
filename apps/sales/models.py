from django.conf import settings
from django.db import models

from apps.core.choices import C, money
from apps.core.models import Record


class Lead(Record):
    company = models.CharField(max_length=200)
    contact_name = models.CharField("Contact", max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    stage = models.CharField(max_length=20, choices=C("New", "Contacted", "Qualified", "Proposal", "Negotiation", "Won", "Lost"), default="New")
    source = models.CharField(max_length=100, blank=True)
    value = money(verbose_name="Monthly value")
    next_followup = models.DateField("Next follow-up", null=True, blank=True)
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.company


class Campaign(Record):
    name = models.CharField("Campaign", max_length=200)
    type = models.CharField(max_length=20, choices=C("Email", "Call list", "Review request", "Survey"), default="Email")
    audience = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=20, choices=C("Draft", "Scheduled", "Active", "Sent", "Paused"), default="Draft")
    send_date = models.DateField(null=True, blank=True)
    subject = models.CharField("Subject line", max_length=255, blank=True)
    body = models.TextField("Message / script", blank=True)

    def __str__(self):
        return self.name
