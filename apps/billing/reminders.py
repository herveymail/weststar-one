"""Automatic payment reminders (Settings › Invoice defaults › Payment reminders).

Before the due date (default 3 days), on the due date, and after it (default 7, 14 and 30 days late) — each at most once
per invoice. Skipped: drafts, paid/void invoices, $0 balances, and clients on AutoPay (they're charged automatically).
Only sent during the day (8 AM–6 PM office time) so clients don't get them at 2 AM.
"""
from datetime import timedelta

from django.utils import timezone

from apps.core import mail
from apps.core.models import Setting

OPEN = ["Sent", "Viewed", "Partial", "Overdue"]


def enabled() -> bool:
    return Setting.get("billing.reminders_on", "false") == "true"


def _days(key, default) -> list[int]:
    out = []
    for x in (Setting.get(key, "") or default).replace(";", ",").split(","):
        x = x.strip()
        if x.isdigit() and 0 < int(x) <= 365:
            out.append(int(x))
    return sorted(set(out))


def plan() -> list[tuple[str, int]]:
    """[(step, days relative to due date)] — negative = before."""
    steps = [(f"before{d}", -d) for d in _days("billing.remind_before_days", "3")]
    if Setting.get("billing.remind_on_due", "true") != "false":
        steps.append(("due", 0))
    steps += [(f"after{d}", d) for d in _days("billing.remind_after_days", Setting.get("billing.reminder_days", "") or "7,14,30")]
    return steps


def due_steps(inv, today):
    """Steps whose day has come for this invoice and haven't been sent (latest first — we only send the newest one)."""
    sent = set(inv.reminders.values_list("step", flat=True))
    ready = [(s, d) for s, d in plan() if inv.due_date + timedelta(days=d) <= today and s not in sent]
    # Never send a "3 days before" reminder once the invoice is already due, etc.: only the most recent step counts.
    return sorted(ready, key=lambda x: x[1])[-1:] if ready else []


def message_for(inv, step, days):
    from .documents import default_message  # noqa: F401 — keeps the import path alive for the preview
    if days < 0:
        return (f"Invoice {inv.number} reminder",
                f"This is a friendly reminder that invoice {inv.number} for ${inv.balance:,.2f} is due on {inv.due_date:%B %-d, %Y}.")
    if days == 0:
        return (f"Invoice {inv.number} is due today", f"Invoice {inv.number} for ${inv.balance:,.2f} is due today.")
    return (f"Past due: invoice {inv.number}",
            f"Invoice {inv.number} was due on {inv.due_date:%B %-d, %Y} and is now {days} day{'s' if days != 1 else ''} past due. The balance is ${inv.balance:,.2f}.")


def run(now=None, force=False) -> str:
    from .models import Invoice, InvoiceReminder, invoice_link
    from .payments import _billing_people
    if not enabled():
        return "off"
    now = timezone.localtime(now or timezone.now())
    if not force and not (8 <= now.hour < 18):
        return "outside sending hours"
    today = now.date()
    sent = skipped = 0
    company = Setting.get("company.name", "") or "Weststar MSP"
    horizon = today + timedelta(days=max([-d for _s, d in plan() if d < 0] or [0]))
    qs = (Invoice.objects.filter(status__in=OPEN, archived_at__isnull=True, due_date__lte=horizon, client__autopay_enabled=False)
          .select_related("client"))
    for inv in qs:
        if inv.balance <= 0 or inv.client.archived_at:
            continue
        for step, days in due_steps(inv, today):
            to = _billing_people(inv.client)
            if not to:
                skipped += 1
                continue
            subject, intro = message_for(inv, step, days)
            ok = mail.send(to, subject, "email/payment_reminder", {
                "inv": inv, "intro": intro, "link": invoice_link(inv), "company": company, "days": days,
                "extra": Setting.get("billing.reminder_note", ""), "meta": f"Invoice {inv.number}"}, background=True)
            if ok:
                InvoiceReminder.objects.get_or_create(invoice=inv, step=step, defaults={"sent_to": ", ".join(to)[:500]})
                # Earlier steps that were skipped count as done, so they don't go out later.
                for s, d in plan():
                    if d < days:
                        InvoiceReminder.objects.get_or_create(invoice=inv, step=s, defaults={"sent_to": "(skipped — later reminder sent)"})
                sent += 1
    return f"{sent} sent" + (f", {skipped} with no billing email" if skipped else "")
