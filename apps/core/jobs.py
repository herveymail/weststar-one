"""
Background jobs — replace the old app's 42 cron scripts with one list. `python manage.py run_jobs`
runs whatever is due (the jobs container calls it every minute); each run is recorded in JobRun.
"""
import calendar
import json
from datetime import date, timedelta

from django.db import transaction
from django.utils import timezone

from .models import Counter, JobRun, Setting


def sla_watch():
    from apps.helpdesk.models import OPEN_STATUSES, PAUSED_STATUSES, Ticket, TicketMessage
    active = [s for s in OPEN_STATUSES if s not in PAUSED_STATUSES]
    late = list(Ticket.objects.filter(status__in=active, first_response_at__isnull=True, response_due_at__lt=timezone.now(), sla_breached=False))
    for t in late:
        Ticket.objects.filter(pk=t.pk).update(sla_breached=True)
        TicketMessage.objects.create(ticket=t, kind="event", body="Response SLA missed", via="system")
    return {"breached": len(late)}


def _add_months(d: date, n: int) -> date:
    m = d.month - 1 + n
    y, m = d.year + m // 12, m % 12 + 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def recurring_invoices():
    from apps.billing.models import Invoice, InvoiceLine, RecurringInvoice
    created = 0
    today = timezone.localdate()
    for sid in RecurringInvoice.objects.filter(status="Active", archived_at__isnull=True, next_run__lte=today).values_list("id", flat=True):
        with transaction.atomic():
            s = RecurringInvoice.objects.select_for_update(skip_locked=True).filter(pk=sid, next_run__lte=today).first()
            if not s:
                continue
            inv = Invoice.objects.create(
                number=f"INV-{Counter.next('invoices', 1001)}", client=s.client, status="Draft", invoice_date=s.next_run,
                due_date=s.next_run + timedelta(days=s.client.net_terms or 30), tax_rate=s.tax_rate, scope=f"{s.name} — {s.next_run}", notes=s.notes,
            )
            for i, ln in enumerate(s.lines.all()):
                InvoiceLine.objects.create(invoice=inv, description=ln.description, qty=ln.qty, rate=ln.rate, taxable=ln.taxable, sort_order=i)
            inv.recalc()
            s.next_run = _add_months(s.next_run, {"Year": 12, "Quarter": 3}.get(s.frequency, 1))
            s.save(update_fields=["next_run", "updated_at"])
            created += 1
    return {"created": created}


def overdue_invoices():
    from apps.billing.models import Invoice
    n = Invoice.objects.filter(status__in=["Sent", "Viewed", "Partial"], due_date__lt=timezone.localdate(), archived_at__isnull=True).update(status="Overdue")
    return {"overdue": n}


def auto_close():
    from apps.helpdesk.models import Ticket, TicketMessage
    try:
        days = int(Setting.get("tickets.auto_close_days", "7") or 0)
    except ValueError:
        days = 0
    if days < 1:
        return {"closed": 0}
    rows = list(Ticket.objects.filter(status="Resolved", resolved_at__lt=timezone.now() - timedelta(days=days)))
    for t in rows:
        Ticket.objects.filter(pk=t.pk).update(status="Closed", closed_at=timezone.now())
        TicketMessage.objects.create(ticket=t, kind="event", body=f"Closed automatically after {days} days resolved", via="system")
    return {"closed": len(rows)}


def cleanup():
    from django.contrib.sessions.models import Session

    from apps.accounts.models import LoginAttempt, UserSession
    s = Session.objects.filter(expire_date__lt=timezone.now()).delete()[0]
    us = UserSession.objects.filter(revoked_at__lt=timezone.now() - timedelta(days=7)).delete()[0]
    a = LoginAttempt.objects.filter(created_at__lt=timezone.now() - timedelta(days=90)).delete()[0]
    from .models import OutboxEmail
    o = OutboxEmail.objects.filter(status="sent", sent_at__lt=timezone.now() - timedelta(days=30)).delete()[0]
    return {"sessions": s + us, "attempts": a, "sent_emails": o}


def wake_snoozed():
    from apps.helpdesk.services import wake_snoozed as wake
    return {"woken": wake()}


def import_files_cleanup():
    from apps.legacy.uploaded import cleanup_old_files
    return {"deleted": cleanup_old_files()}


def fetch_email():
    from apps.helpdesk.inbound import fetch
    return fetch()


def autopay():
    from apps.billing.payments import run_autopay
    return run_autopay()


def ai_new_tickets():
    from apps.helpdesk.ai import run_new_tickets
    return run_new_tickets()


def msp360_sync():
    from apps.integrations import msp360
    if Setting.get("msp360.enabled", "false") != "true" or not msp360.configured():
        return {"skipped": "MSP360 sync is off or not set up"}
    r = msp360.sync()
    if not r["ok"]:
        raise RuntimeError(r["error"])
    return r


def late_fees():
    from apps.billing.latefees import run
    return run()


STEP = {"Week": (0, 7), "2 weeks": (0, 14), "Month": (1, 0), "Quarter": (3, 0), "6 months": (6, 0), "Year": (12, 0)}


def recurring_tickets():
    """Open tickets from Recurring tickets schedules whose day has come (one per client; empty client = every managed client)."""
    from apps.crm.models import Client
    from apps.helpdesk import services
    from apps.helpdesk.models import RecurringTicket, Ticket
    today = timezone.localdate()
    made = 0
    for sid in RecurringTicket.objects.filter(status="Active", archived_at__isnull=True, next_run__lte=today).values_list("id", flat=True):
        with transaction.atomic():
            s = RecurringTicket.objects.select_for_update(skip_locked=True).select_related("template").filter(pk=sid, next_run__lte=today).first()
            if s is None:
                continue
            tpl = s.template
            clients = [s.client] if s.client_id else list(Client.objects.filter(archived_at__isnull=True, status="Active", plan__startswith="Managed").order_by("name"))
            for c in clients:
                subject, details = tpl.render(c, s.next_run)
                t = services.create_ticket(subject=subject, details=details, client=c, priority=tpl.priority, source="Manual",
                                           assigned_to=s.assigned_to, queue=tpl.queue, category=tpl.category,
                                           due_date=s.next_run + timedelta(days=s.due_days))
                Ticket.objects.filter(pk=t.pk).update(billable=tpl.billable)
                services.event(t, f"Opened automatically by the recurring schedule \"{s.name}\"")
                made += 1
            months, days = STEP.get(s.frequency, (1, 0))
            nxt = s.next_run
            while nxt <= today:  # catch up without opening a pile of old tickets
                nxt = _add_months(nxt, months) if months else nxt + timedelta(days=days)
            s.last_run, s.next_run = today, nxt
            s.save(update_fields=["last_run", "next_run", "updated_at"])
    return {"opened": made}


def morning_summary():
    from .today import morning_summary as run
    return run()


def renewal_notices():
    from .today import renewal_notices as run
    return run()


def payment_reminders():
    from apps.billing.reminders import run
    return run()


def outbox():
    from .mail import deliver_outbox
    return deliver_outbox()


JOBS = {
    "outbox": {"label": "Send waiting emails (and retry any that failed)", "every_minutes": 1, "run": outbox},
    "ai-tickets": {"label": "AI: triage and first response for new tickets", "every_minutes": 1, "run": ai_new_tickets},
    "autopay": {"label": "AutoPay: charge cards on file", "every_minutes": 15, "run": autopay},
    "fetch-email": {"label": "Email to ticket (support mailbox)", "every_minutes": 1, "run": fetch_email},
    "sla-watch": {"label": "SLA watch", "every_minutes": 5, "run": sla_watch},
    "wake-snoozed": {"label": "Bring back snoozed tickets", "every_minutes": 5, "run": wake_snoozed},
    "recurring-invoices": {"label": "Recurring invoices", "every_minutes": 60, "run": recurring_invoices},
    "overdue-invoices": {"label": "Mark overdue invoices", "every_minutes": 60, "run": overdue_invoices},
    "msp360": {"label": "MSP360: sync backups, tickets for failed plans", "every_minutes": 15, "run": msp360_sync},
    "recurring-tickets": {"label": "Recurring tickets", "every_minutes": 60, "run": recurring_tickets},
    "morning-summary": {"label": "Morning summary emails (people who turned it on in Profile)", "every_minutes": 30, "run": morning_summary},
    "renewal-notices": {"label": "Renewal, domain and SSL heads-up emails", "every_minutes": 360, "run": renewal_notices},
    "payment-reminders": {"label": "Payment reminders to clients", "every_minutes": 60, "run": payment_reminders},
    "late-fees": {"label": "Late fees on past-due invoices", "every_minutes": 360, "run": late_fees},
    "auto-close": {"label": "Auto-close resolved tickets", "every_minutes": 60, "run": auto_close},
    "cleanup": {"label": "Clean up old sessions and sign-in records", "every_minutes": 1440, "run": cleanup},
    "import-files": {"label": "Delete leftover import uploads (after 24 hours)", "every_minutes": 60, "run": import_files_cleanup},
}


def run_due(force: bool = False) -> dict:
    results = {}
    now = timezone.now()
    for name, job in JOBS.items():
        row, _ = JobRun.objects.get_or_create(name=name)
        if not force and row.last_run_at and now - row.last_run_at < timedelta(minutes=job["every_minutes"]):
            continue
        try:
            result = job["run"]()
            ok = True
        except Exception as exc:  # noqa: BLE001 — record and carry on with the other jobs
            result, ok = {"error": str(exc)[:500]}, False
        JobRun.objects.filter(name=name).update(last_run_at=now, last_result=json.dumps(result), last_ok=ok)
        results[name] = result
    return results
