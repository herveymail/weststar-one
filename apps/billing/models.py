from decimal import ROUND_HALF_UP, Decimal

from django.db import models

from apps.core.choices import C, money
from apps.core.models import EncryptedField, Record
from apps.crm.models import Client

CENT = Decimal("0.01")


class Vendor(Record):
    name = models.CharField("Vendor", max_length=200)
    category = models.CharField(max_length=100, blank=True)
    contact_name = models.CharField("Account rep", max_length=200, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    website = models.URLField(blank=True)
    account_number = EncryptedField("Our account number")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class LinedDocument(Record):
    """Invoices, quotes and recurring schedules: totals are always calculated here, never typed in."""

    tax_rate = models.DecimalField("Tax rate %", max_digits=6, decimal_places=3, null=True, blank=True)
    subtotal = money(editable=False)
    tax_amount = money(verbose_name="Tax", editable=False)
    total = money(editable=False)

    class Meta:
        abstract = True

    def recalc(self):
        lines = list(self.lines.all())
        sub = sum((ln.line_total or Decimal(0) for ln in lines), Decimal(0))
        taxable = sum((ln.line_total or Decimal(0) for ln in lines if ln.taxable), Decimal(0))
        tax = (taxable * (self.tax_rate or Decimal(0)) / 100).quantize(CENT, ROUND_HALF_UP)
        self.subtotal, self.tax_amount, self.total = sub.quantize(CENT), tax, (sub + tax).quantize(CENT)
        type(self).objects.filter(pk=self.pk).update(subtotal=self.subtotal, tax_amount=self.tax_amount, total=self.total)


class Line(models.Model):
    description = models.CharField(max_length=500)
    qty = models.DecimalField(max_digits=12, decimal_places=2, default=1)
    rate = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    taxable = models.BooleanField(default=True)
    line_total = models.DecimalField(max_digits=14, decimal_places=2, default=0, editable=False)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        abstract = True
        ordering = ["sort_order", "id"]

    def save(self, *args, **kwargs):
        self.line_total = (Decimal(self.qty or 0) * Decimal(self.rate or 0)).quantize(CENT, ROUND_HALF_UP)
        super().save(*args, **kwargs)


class Invoice(LinedDocument):
    number = models.CharField("Invoice #", max_length=50, unique=True, null=True, blank=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="invoices")
    status = models.CharField(max_length=20, choices=C("Draft", "Sent", "Viewed", "Partial", "Paid", "Overdue", "Void"), default="Draft")
    invoice_date = models.DateField("Date")
    due_date = models.DateField("Due")
    amount_paid = money(verbose_name="Paid")
    scope = models.TextField("Description of work", blank=True)
    notes = models.TextField("Notes to client", blank=True)
    autopay_attempts = models.PositiveIntegerField(default=0, editable=False)
    autopay_next_at = models.DateTimeField(null=True, blank=True, editable=False)
    autopay_error = models.CharField(max_length=255, blank=True, editable=False)
    # Paid in the old app with no matching payment record (kept so the paid total never drops on import).
    paid_outside = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def __str__(self):
        return self.number or f"Invoice {self.pk}"

    @property
    def balance(self):
        return (self.total or Decimal(0)) - (self.amount_paid or Decimal(0))

    def apply_payments(self):
        """Paid amount and status from the payments recorded against this invoice."""
        from django.db.models import Sum
        paid = (self.payments.filter(archived_at__isnull=True, status="Succeeded").aggregate(s=Sum("amount"))["s"] or Decimal(0)) + (self.paid_outside or 0)
        status = self.status
        if self.status not in ("Draft", "Void"):
            if paid >= (self.total or 0) and (self.total or 0) > 0:
                status = "Paid"
            elif paid > 0:
                status = "Partial"
            elif self.status in ("Paid", "Partial"):
                status = "Sent"
        Invoice.objects.filter(pk=self.pk).update(amount_paid=paid, status=status)
        self.amount_paid, self.status = paid, status


class Payment(Record):
    METHODS = C("Card", "Bank account (ACH)", "Check", "Cash", "Bank transfer", "Trade account", "Other")
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="payments", editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.PROTECT, related_name="payments")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    method = models.CharField(max_length=30, choices=METHODS, default="Check")
    paid_on = models.DateField("Date")
    reference = models.CharField("Check # / reference", max_length=255, blank=True)
    status = models.CharField(max_length=12, choices=C("Succeeded", "Pending", "Failed", "Refunded"), default="Succeeded")
    source = models.CharField(max_length=10, choices=C("staff", "online", "autopay"), default="staff", editable=False)
    stripe_payment_intent = models.CharField(max_length=64, blank=True, editable=False, db_index=True)
    receipt_url = models.URLField(max_length=500, blank=True, editable=False)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-paid_on", "-id"]

    def __str__(self):
        return f"${self.amount} on {self.invoice}"

    def save(self, *args, **kwargs):
        if self.invoice_id:
            self.client_id = self.invoice.client_id
        super().save(*args, **kwargs)
        self.invoice.apply_payments()


class StripeEvent(models.Model):
    """Stripe webhook events already handled (Stripe can send the same event more than once)."""
    event_id = models.CharField(max_length=80, unique=True)
    type = models.CharField(max_length=80)
    created_at = models.DateTimeField(auto_now_add=True)


class AutoPayLink(models.Model):
    """A one-use link a client can open (no portal login needed) to put a card or bank account on file."""
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="+")
    token_hash = models.CharField(max_length=64, unique=True)
    created_by = models.ForeignKey("accounts.User", null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    legacy_id = models.BigIntegerField(null=True, blank=True, unique=True)


class InvoiceLine(Line):
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="lines")


class RecurringInvoice(LinedDocument):
    name = models.CharField("Schedule", max_length=200)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="recurring_invoices")
    frequency = models.CharField("Every", max_length=10, choices=C("Month", "Quarter", "Year"), default="Month")
    next_run = models.DateField()
    status = models.CharField(max_length=10, choices=C("Active", "Paused"), default="Active")
    autopay = models.BooleanField("AutoPay", default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.name


class RecurringLine(Line):
    schedule = models.ForeignKey(RecurringInvoice, on_delete=models.CASCADE, related_name="lines")


class Quote(LinedDocument):
    number = models.CharField("Quote #", max_length=50, unique=True, null=True, blank=True, editable=False)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="quotes")
    status = models.CharField(max_length=20, choices=C("Draft", "Sent", "Accepted", "Declined", "Invoiced"), default="Draft")
    quote_date = models.DateField("Date")
    expires_on = models.DateField("Expires", null=True, blank=True)
    scope = models.TextField("Scope of work", blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-quote_date", "-id"]

    def __str__(self):
        return self.number or f"Quote {self.pk}"


class QuoteLine(Line):
    quote = models.ForeignKey(Quote, on_delete=models.CASCADE, related_name="lines")


class BankTransaction(Record):
    posted_on = models.DateField("Date")
    description = models.CharField(max_length=255)
    account = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    match_status = models.CharField("Status", max_length=20, choices=C("Unmatched", "Matched", "Ignored"), default="Unmatched")
    invoice = models.ForeignKey(Invoice, null=True, blank=True, on_delete=models.SET_NULL, related_name="+", verbose_name="Matched invoice")
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-posted_on", "-id"]

    def __str__(self):
        return self.description


class Contract(Record):
    number = models.CharField("Contract #", max_length=50, unique=True, null=True, blank=True, editable=False)
    name = models.CharField("Contract", max_length=255)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="contracts")
    type = models.CharField(max_length=20, choices=C("Managed", "Break/fix", "Project", "BAA", "NDA", "Other"), default="Managed")
    status = models.CharField(max_length=20, choices=C("Draft", "Sent", "Active", "Expired", "Cancelled"), default="Draft")
    start_date = models.DateField("Starts", null=True, blank=True)
    end_date = models.DateField("Ends", null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    monthly_rate = money()
    included_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    overage_rate = money()
    scope = models.TextField(blank=True)
    terms = models.TextField(blank=True)

    def __str__(self):
        return self.name


class Policy(Record):
    name = models.CharField("Policy", max_length=255)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="policies", help_text="Leave blank for all clients.")
    version = models.CharField(max_length=20, blank=True)
    status = models.CharField(max_length=20, choices=C("Draft", "Current", "Review due", "Retired"), default="Draft")
    next_review = models.DateField(null=True, blank=True)
    body = models.TextField("Policy text", blank=True)

    class Meta:
        verbose_name_plural = "policies"

    def __str__(self):
        return self.name


class TrainingAssignment(Record):
    course = models.CharField(max_length=500)
    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="training")
    learners = models.PositiveIntegerField(null=True, blank=True)
    due_date = models.DateField("Due", null=True, blank=True)
    progress = models.PositiveIntegerField("Progress %", null=True, blank=True)
    status = models.CharField(max_length=20, choices=C("Not started", "In progress", "Complete"), default="Not started")

    def __str__(self):
        return self.course


class Renewal(Record):
    item = models.CharField(max_length=255)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="renewals")
    type = models.CharField(max_length=20, choices=C("License", "Domain", "Warranty", "Contract", "Subscription", "Other"), blank=True)
    renews_on = models.DateField("Renews")
    cost = money()
    status = models.CharField(max_length=20, choices=C("Upcoming", "Renewed", "Cancelled"), default="Upcoming")
    notes = models.TextField(blank=True)

    def __str__(self):
        return self.item


class Expense(Record):
    spent_on = models.DateField("Date")
    vendor = models.ForeignKey(Vendor, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses")
    category = models.CharField(max_length=100, blank=True)
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    client = models.ForeignKey(Client, null=True, blank=True, on_delete=models.SET_NULL, related_name="expenses", verbose_name="Bill to client")
    billable = models.BooleanField(default=False)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-spent_on", "-id"]

    def __str__(self):
        return self.description or f"Expense {self.pk}"
