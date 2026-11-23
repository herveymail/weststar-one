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
    public_token = models.CharField(max_length=48, blank=True, default="", editable=False, db_index=True,
                                    help_text="Secret part of the view-and-pay link in invoice emails (no sign-in needed).")
    autopay_next_at = models.DateTimeField(null=True, blank=True, editable=False)
    autopay_error = models.CharField(max_length=255, blank=True, editable=False)
    # Paid in the old app with no matching payment record (kept so the paid total never drops on import).
    paid_outside = models.DecimalField(max_digits=12, decimal_places=2, default=0, editable=False)
    last_late_fee_on = models.DateField("Last late fee", null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-invoice_date", "-id"]

    def __str__(self):
        return self.number or f"Invoice {self.pk}"

    @property
    def balance(self):
        return (self.total or Decimal(0)) - (self.amount_paid or Decimal(0))

    COMPUTED = ("Sent", "Viewed", "Partial", "Paid", "Overdue")  # set by the system from payments and the due date

    def sync(self):
        """Paid amount and status from the facts: the payments recorded, the total and the due date.
        Draft and Void are choices a person makes and are left alone (a draft that gets paid stops being a draft)."""
        from django.db.models import Sum
        from django.utils import timezone
        paid = (self.payments.filter(archived_at__isnull=True, status="Succeeded").aggregate(s=Sum("amount"))["s"] or Decimal(0)) + (self.paid_outside or 0)
        total, status = self.total or Decimal(0), self.status
        if status == "Draft" and paid > 0:
            status = "Sent"
        if status not in ("Draft", "Void"):
            if paid >= total and total > 0:
                status = "Paid"
            elif self.due_date and self.due_date < timezone.localdate() and total > paid:
                status = "Overdue"
            elif paid > 0:
                status = "Partial"
            elif status in ("Paid", "Partial", "Overdue"):
                status = "Sent"
        Invoice.objects.filter(pk=self.pk).update(amount_paid=paid, status=status)
        self.amount_paid, self.status = paid, status

    apply_payments = sync

    def release_work(self) -> int:
        """A void or archived invoice bills nothing: its ticket time, mileage and parts go back to Ready to bill."""
        from apps.helpdesk.models import TicketSignoff, TimeEntry
        from apps.tools.models import MileageTrip
        return sum(m.objects.filter(invoice=self).update(invoice=None) for m in (TimeEntry, MileageTrip, TicketSignoff))

    def after_edit(self) -> str:
        """Run after the invoice (or its lines) is saved, voided, archived or restored. Returns a note for the person, if any."""
        self.sync()
        Payment.objects.filter(invoice=self).exclude(client_id=self.client_id).update(client_id=self.client_id)
        if self.status == "Void" or self.archived_at:
            n = self.release_work()
            if n:
                return f"{n} item{'s' if n != 1 else ''} of ticket time, mileage or parts went back to Ready to bill."
        return ""

    # ── the edit form ──
    @classmethod
    def tune_form(cls, form):
        cur = form.instance.status if form.instance.pk else "Draft"
        is_open = cur in cls.COMPUTED
        f = form.fields["status"]
        f.choices = [("Draft", "Draft"), ("Sent", f"Open ({cur})" if is_open else "Open (sent to the client)"), ("Void", "Void")]
        f.help_text = "Partial, Paid and Overdue set themselves from the payments and the due date. To mark it paid, use Record payment."
        if is_open:
            form.initial["status"] = "Sent"

    @classmethod
    def check_form(cls, form, data):
        if data.get("invoice_date") and data.get("due_date") and data["due_date"] < data["invoice_date"]:
            form.add_error("due_date", "The due date is before the invoice date.")
        if data.get("status") == "Sent" and form.instance.pk:
            was = cls.objects.filter(pk=form.instance.pk).values_list("status", flat=True).first()
            if was in cls.COMPUTED:
                data["status"] = was  # "Open" keeps what it was; sync() then works out the right one
        return data


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
        was = Payment.objects.filter(pk=self.pk).values_list("invoice_id", flat=True).first() if self.pk else None
        super().save(*args, **kwargs)
        self.invoice.sync()
        if was and was != self.invoice_id:  # moved to another invoice: the one it left needs its balance back
            Invoice.objects.get(pk=was).sync()

    @classmethod
    def check_form(cls, form, data):
        inv, amount = data.get("invoice"), data.get("amount")
        if amount is not None and amount <= 0:
            form.add_error("amount", "Enter an amount above zero. To take a payment back, set its status to Refunded.")
        if inv and inv.status == "Void":
            form.add_error("invoice", f"{inv} is void. Pick another invoice.")
        return data


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
    public_token = models.CharField(max_length=48, blank=True, default="", editable=False, db_index=True,
                                    help_text="Secret part of the review-and-approve link in quote emails (no sign-in needed).")
    deposit_invoice = models.ForeignKey("Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)

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
    type = models.CharField(max_length=20, choices=C("MSA", "Managed", "Break/fix", "Project", "BAA", "NDA", "Other"), default="Managed")
    status = models.CharField(max_length=20, choices=C("Draft", "Sent", "Active", "Expired", "Cancelled"), default="Draft")
    start_date = models.DateField("Starts", null=True, blank=True)
    end_date = models.DateField("Ends", null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    monthly_rate = money()
    included_hours = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    overage_rate = money()
    scope = models.TextField(blank=True)
    terms = models.TextField(blank=True)
    public_token = models.CharField(max_length=48, blank=True, default="", editable=False, db_index=True,
                                    help_text="Secret part of the review-and-sign link in contract emails (no sign-in needed).")
    # ── Filled in by the contract builder (Billing › Contracts › New agreement); the wording above is built from these ──
    built = models.BooleanField(default=False, editable=False)
    include_msa = models.BooleanField("Include the MSA terms in this contract", default=True)
    msa = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="schedules", verbose_name="Under MSA")
    term_months = models.PositiveIntegerField("Initial term (months)", null=True, blank=True)
    renewal_months = models.PositiveIntegerField("Renewal term (months)", null=True, blank=True)
    notice_days = models.PositiveIntegerField("Notice to cancel (days)", default=30)
    increase_pct = models.DecimalField("Increase at renewal (%)", max_digits=5, decimal_places=2, null=True, blank=True)
    users = models.PositiveIntegerField(null=True, blank=True)
    user_rate = money()
    workstations = models.PositiveIntegerField(null=True, blank=True)
    workstation_rate = money()
    servers = models.PositiveIntegerField(null=True, blank=True)
    server_rate = money()
    flat_fee = money()
    setup_fee = money()
    after_hours_rate = money()
    trip_fee = money()
    services = models.JSONField(default=list, blank=True)
    service_notes = models.TextField("Extra services or details", blank=True)
    exclusions = models.TextField("Extra exclusions", blank=True)
    our_signer = models.CharField(max_length=200, blank=True)
    our_title = models.CharField(max_length=200, blank=True)
    our_signed_at = models.DateTimeField(null=True, blank=True, editable=False)
    recurring = models.ForeignKey("RecurringInvoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="contracts", editable=False)
    setup_invoice = models.ForeignKey("Invoice", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)

    BUILDER_FIELDS = ["include_msa", "msa", "term_months", "renewal_months", "notice_days", "increase_pct", "users", "user_rate", "workstations",
                      "workstation_rate", "servers", "server_rate", "flat_fee", "setup_fee", "after_hours_rate", "trip_fee", "services", "service_notes",
                      "exclusions", "our_signer", "our_title"]

    def __str__(self):
        return self.name

    @property
    def signed(self):
        return self.signatures.exists()

    @classmethod
    def check_form(cls, form, data):
        """A signed agreement is a record of what was agreed: its wording and prices can't be edited afterwards."""
        if form.instance.pk and form.instance.signatures.exists():
            locked = [f for f in ("scope", "terms", "monthly_rate", "included_hours", "overage_rate", "start_date", "client", "type") if f in form.changed_data]
            if locked:
                form.add_error(None, "This agreement is signed, so its wording, prices and dates can't be changed. Make a new agreement (or an amendment) instead.")
        return data


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
    notified_on = models.DateField(null=True, blank=True, editable=False)  # heads-up email sent for this renewal date
    quote = models.ForeignKey("Quote", null=True, blank=True, on_delete=models.SET_NULL, related_name="+", editable=False)

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


def invoice_link(inv: "Invoice") -> str:
    """The link clients get by email: view, download and pay this invoice without signing in.
    It lives on the main address (APP_URL/pay/…), not the client portal, so it works even when the portal is
    off or not set up. Falls back to the portal page only when links without sign-in are turned off."""
    import secrets

    from django.conf import settings as dj

    from apps.core.models import Setting
    if Setting.get("billing.public_links", "true") == "false":
        return f"{dj.PORTAL_BASE}/invoices/{inv.pk}/"
    if not inv.public_token:
        inv.public_token = secrets.token_urlsafe(24)
        Invoice.objects.filter(pk=inv.pk).update(public_token=inv.public_token)
    return f"{dj.APP_URL}/pay/{inv.public_token}/"


def _token_for(obj) -> str:
    import secrets
    if not obj.public_token:
        obj.public_token = secrets.token_urlsafe(24)
        type(obj).objects.filter(pk=obj.pk).update(public_token=obj.public_token)
    return obj.public_token


def quote_link(q: "Quote") -> str:
    """Review, approve or decline this quote without signing in (APP_URL/quote/…)."""
    from django.conf import settings as dj

    from apps.core.models import Setting
    if Setting.get("billing.public_links", "true") == "false":
        return f"{dj.PORTAL_BASE}/quotes/{q.pk}/"
    return f"{dj.APP_URL}/quote/{_token_for(q)}/"


def contract_link(c: "Contract") -> str:
    """Read and sign this contract without signing in (APP_URL/sign/…)."""
    from django.conf import settings as dj

    from apps.core.models import Setting
    if Setting.get("billing.public_links", "true") == "false":
        return f"{dj.PORTAL_BASE}/contracts/{c.pk}/"
    return f"{dj.APP_URL}/sign/{_token_for(c)}/"


class InvoiceReminder(models.Model):
    """One row per automatic payment reminder sent, so the same reminder never goes out twice."""
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name="reminders")
    step = models.CharField(max_length=20)  # before3 / due / after7 / after14 …
    sent_to = models.CharField(max_length=500, blank=True)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["invoice", "step"], name="one_reminder_per_step")]
        ordering = ["-sent_at"]
