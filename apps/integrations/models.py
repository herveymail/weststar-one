"""Data synced from other services. MSP360 Managed Backup: companies, computers and backup plans."""
from django.db import models

from apps.crm.models import Client

# MSP360 plan status codes
STATUS = {0: ("Success", "good"), 1: ("Overdue", "warn"), 2: ("Error", "bad"), 3: ("Running", "info"), 4: ("Unknown", ""),
          5: ("Interrupted", "bad"), 6: ("Unexpectedly closed", "bad"), 7: ("Warning", "warn")}
FAILED = (2, 5, 6)


class Msp360Company(models.Model):
    mc_id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=190)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    client_set_by_hand = models.BooleanField(default=False)
    storage_limit = models.BigIntegerField(null=True, blank=True)
    computers = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Msp360Computer(models.Model):
    key = models.CharField(max_length=190, primary_key=True)  # ComputerHID, or company/name when MSP360 gives none
    name = models.CharField(max_length=190)
    company = models.CharField(max_length=190, blank=True, db_index=True)
    user_email = models.CharField(max_length=190, blank=True)
    os = models.CharField(max_length=60, blank=True)
    online = models.BooleanField(default=False)
    last_activity = models.DateTimeField(null=True, blank=True)
    plans = models.PositiveIntegerField(default=0)
    failed = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["company", "name"]


class Msp360Plan(models.Model):
    plan_id = models.CharField(max_length=64, primary_key=True)
    name = models.CharField(max_length=255)
    plan_type = models.CharField(max_length=40, blank=True)
    computer = models.CharField(max_length=190, blank=True)
    company = models.CharField(max_length=190, blank=True, db_index=True)
    user_email = models.CharField(max_length=190, blank=True)
    storage = models.CharField(max_length=80, blank=True)
    status = models.SmallIntegerField(default=4, db_index=True)
    last_start = models.DateTimeField(null=True, blank=True)
    next_start = models.DateTimeField(null=True, blank=True)
    error = models.TextField(blank=True)
    files_copied = models.BigIntegerField(null=True, blank=True)
    files_failed = models.BigIntegerField(null=True, blank=True)
    data_copied = models.BigIntegerField(null=True, blank=True)
    total_data = models.BigIntegerField(null=True, blank=True)
    duration = models.CharField(max_length=40, blank=True)
    report_link = models.CharField(max_length=500, blank=True)
    failed_since = models.DateTimeField(null=True, blank=True)
    ticket = models.ForeignKey("helpdesk.Ticket", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    ticket_last_start = models.DateTimeField(null=True, blank=True)
    first_seen = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["company", "computer", "name"]

    @property
    def status_label(self):
        return STATUS.get(self.status, (f"Status {self.status}", ""))[0]

    @property
    def kind(self):
        """Files / Image / SQL… read from the plan name (MSP360's numeric plan types aren't documented and have changed)."""
        n = (self.name or "").lower()
        for word, label in (("image", "Image"), ("hyper-v", "Hyper-V"), ("vmware", "VMware"), ("sql", "SQL"), ("exchange", "Exchange"),
                            ("file", "Files"), ("consistency", "Consistency check"), ("restore", "Restore")):
            if word in n:
                return label
        return "" if (self.plan_type or "").startswith("Type ") else self.plan_type

    @property
    def tone(self):
        return STATUS.get(self.status, ("", ""))[1]

    @property
    def is_failure(self):
        return self.status in FAILED
