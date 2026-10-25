"""Late fees — same rules as the old app's nightly job.

An unpaid invoice more than <grace> days past its due date gets one "Late fee" line (flat amount or a percent of
the balance). If "repeat every 30 days" is on, it gets another every 30 days while it stays unpaid. Clients marked
"No late fees" are skipped. The client is emailed and a note goes on their account.
"""
import re
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core import mail
from apps.core.models import Setting

from .models import Invoice, InvoiceLine

OPEN = ["Sent", "Viewed", "Partial", "Overdue"]
LINE = re.compile(r"^\s*late fee", re.I)


def _dec(v, default="0") -> Decimal:
    try:
        return Decimal(str(v or default).replace("$", "").replace(",", "").strip() or default)
    except InvalidOperation:
        return Decimal(default)


def rules() -> dict:
    kind = "percent" if Setting.get("billing.late_fee_type", "flat") == "percent" else "flat"
    return {
        "on": Setting.get("billing.late_fee_enabled", "false") == "true",
        "kind": kind,
        "flat": _dec(Setting.get("billing.late_fee_flat", "")),
        "pct": _dec(Setting.get("billing.late_fee_pct", "")),
        "grace": max(0, int(_dec(Setting.get("billing.late_fee_grace_days", "0")))),
        "repeat": Setting.get("billing.late_fee_repeat", "true") != "false",
    }


def fee_text(r: dict | None = None) -> str:
    """'$45.00' or '1.5% of the balance' — used in the invoice terms and emails."""
    r = r or rules()
    if r["kind"] == "flat":
        return f"${r['flat']:,.2f}"
    return f"{r['pct'].normalize():f}% of the balance due"


def _old_fee_date(inv: Invoice) -> date | None:
    """Invoices brought over from the old app may carry a late-fee line but no date on record: read it from the line."""
    for ln in inv.lines.all():
        if not LINE.match(ln.description or ""):
            continue
        m = re.search(r"\(([^)]+)\)", ln.description)
        if m:
            for fmt in ("%b %d, %Y", "%m/%d/%Y", "%Y-%m-%d", "%B %d, %Y"):
                try:
                    return datetime.strptime(m.group(1).strip(), fmt).date()
                except ValueError:
                    continue
        return timezone.localdate()  # a fee line with no date: count it as charged today, so nothing doubles up
    return None


def due(inv: Invoice, r: dict, today: date) -> bool:
    if inv.client.late_fee_exempt or inv.balance <= 0:
        return False
    if (today - inv.due_date).days <= r["grace"]:
        return False
    last = inv.last_late_fee_on or _old_fee_date(inv)
    if last and not inv.last_late_fee_on:
        Invoice.objects.filter(pk=inv.pk).update(last_late_fee_on=last)
        inv.last_late_fee_on = last
    if last:
        return r["repeat"] and (today - last).days >= 30
    return True


def run(today: date | None = None) -> dict:
    r = rules()
    out = {"charged": 0, "emailed": 0, "checked": 0}
    if not r["on"] or (r["kind"] == "flat" and r["flat"] <= 0) or (r["kind"] == "percent" and r["pct"] <= 0):
        return {**out, "note": "late fees are off"}
    today = today or timezone.localdate()
    cutoff = today - timedelta(days=r["grace"])
    qs = Invoice.objects.filter(status__in=OPEN, archived_at__isnull=True, due_date__lt=cutoff)
    if not Setting.get("import.late_fees_synced", ""):
        # Invoices from the old app wait until an import has brought over which ones already had a fee and which clients
        # are exempt, so nothing is charged twice. (Any import from this version on sets this.)
        qs = qs.filter(legacy_id__isnull=True)
        out["waiting_for_import"] = Invoice.objects.filter(status__in=OPEN, archived_at__isnull=True, due_date__lt=cutoff, legacy_id__isnull=False).count()
    for pk in qs.values_list("pk", flat=True):
        with transaction.atomic():
            inv = Invoice.objects.select_for_update(skip_locked=True).select_related("client").filter(pk=pk).first()
            if not inv:
                continue
            out["checked"] += 1
            if not due(inv, r, today):
                continue
            balance = inv.balance
            amount = r["flat"] if r["kind"] == "flat" else (balance * r["pct"] / 100)
            amount = amount.quantize(Decimal("0.01"), ROUND_HALF_UP)
            if amount <= 0:
                continue
            label = f"Late fee ({today:%b} {today.day}, {today.year})" if r["kind"] == "flat" else f"Late fee ({r['pct'].normalize():f}% of balance due, {today:%b} {today.day}, {today.year})"
            last_sort = inv.lines.order_by("-sort_order").values_list("sort_order", flat=True).first() or 0
            InvoiceLine.objects.create(invoice=inv, description=label, qty=1, rate=amount, taxable=False, sort_order=last_sort + 1)
            inv.recalc()
            Invoice.objects.filter(pk=inv.pk).update(last_late_fee_on=today, status="Overdue")
            inv.status = "Overdue"
            out["charged"] += 1
            days_late = (today - inv.due_date).days
            from apps.crm.models import ClientNote

            from .payments import _billing_people
            sent = mail.send(_billing_people(inv.client), f"Late fee added to invoice {inv.number}", "email/late_fee", {
                "inv": inv, "fee": amount, "days_late": days_late, "balance": inv.balance, "over_30": days_late >= 30,
                "link": f"{settings.PORTAL_BASE}/invoices/{inv.pk}/"})
            out["emailed"] += int(bool(sent))
            ClientNote.objects.create(client=inv.client, title=f"Late fee ${amount} added to {inv.number}",
                                      body=f"{days_late} days past due. " + ("Client emailed." if sent else "No email sent (no billing email on file, or email isn't set up)."))
    return out
