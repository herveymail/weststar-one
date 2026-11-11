"""Billing › Receivables: who owes what and how late (aging), statements, and the reminder log."""
from collections import OrderedDict
from decimal import Decimal

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core import mail
from apps.core.audit import audit
from apps.core.models import Setting
from apps.core.permissions import can
from apps.crm.models import Client

from .models import Invoice, InvoiceReminder, invoice_link
from .reminders import OPEN

BUCKETS = [("current", "Not due yet"), ("d30", "1–30 days"), ("d60", "31–60"), ("d90", "61–90"), ("d90p", "Over 90")]


def _bucket(days_late):
    return "current" if days_late <= 0 else "d30" if days_late <= 30 else "d60" if days_late <= 60 else "d90" if days_late <= 90 else "d90p"


def open_invoices(client=None):
    qs = Invoice.objects.filter(status__in=OPEN, archived_at__isnull=True).select_related("client").order_by("due_date", "id")
    if client is not None:
        qs = qs.filter(client=client)
    today = timezone.localdate()
    out = []
    for inv in qs:
        if inv.balance <= 0:
            continue
        inv.days_late = (today - inv.due_date).days
        inv.bucket = _bucket(inv.days_late)
        out.append(inv)
    return out


def aging():
    rows: "OrderedDict[int, dict]" = OrderedDict()
    totals = {k: Decimal(0) for k, _ in BUCKETS} | {"total": Decimal(0)}
    for inv in open_invoices():
        r = rows.setdefault(inv.client_id, {"client": inv.client, "invoices": [], "total": Decimal(0), "oldest": 0, **{k: Decimal(0) for k, _ in BUCKETS}})
        r["invoices"].append(inv)
        r[inv.bucket] += inv.balance
        r["total"] += inv.balance
        r["oldest"] = max(r["oldest"], inv.days_late)
        totals[inv.bucket] += inv.balance
        totals["total"] += inv.balance
    return sorted(rows.values(), key=lambda r: (-r["oldest"], -r["total"])), totals


@login_required
def ar_page(request):
    from . import reminders
    if not can(request.user, "billing", "view"):
        raise PermissionDenied
    rows, totals = aging()
    return render(request, "billing/ar.html", {
        "rows": rows, "totals": totals, "buckets": BUCKETS, "today": timezone.localdate(),
        "reminders_on": reminders.enabled(), "plan": reminders.plan(),
        "log": InvoiceReminder.objects.select_related("invoice", "invoice__client").exclude(sent_to__startswith="(skipped")[:25],
        "can_edit": can(request.user, "billing", "edit"),
    })


def _statement_ctx(client):
    invs = open_invoices(client)
    for i in invs:
        i.link = invoice_link(i)
    return {"client": client, "invoices": invs, "total": sum((i.balance for i in invs), Decimal(0)), "today": timezone.localdate(),
            "company": Setting.get("company.name", "") or "Weststar MSP", "buckets": BUCKETS,
            "by_bucket": [(label, sum((i.balance for i in invs if i.bucket == k), Decimal(0))) for k, label in BUCKETS]}


@login_required
def statement(request, client_id):
    """A printable statement of everything a client owes; Email statement sends it with a pay link per invoice."""
    from .payments import _billing_people
    if not can(request.user, "billing", "view"):
        raise PermissionDenied
    client = get_object_or_404(Client, pk=client_id)
    ctx = _statement_ctx(client)
    if request.method == "POST":
        if not can(request.user, "billing", "edit"):
            raise PermissionDenied
        to = [a.strip() for a in request.POST.get("to", "").replace(";", ",").split(",") if "@" in a]
        if not to:
            messages.error(request, "Add an email address.")
        elif not ctx["invoices"]:
            messages.error(request, "Nothing is owed — no statement to send.")
        else:
            msg = request.POST.get("message", "").strip()[:5000] or "Here is your account statement. Each invoice has its own link to view and pay online."
            ok = mail.send(to, f"Account statement — {ctx['company']}", "email/statement",
                           {**ctx, "message": msg, "link": ctx["invoices"][0].link, "sender": request.user.name, "meta": f"Statement · {client.name}"})
            if ok:
                audit(request, "send", "client", client.pk, f"Emailed statement ({ctx['total']}) to {', '.join(to)}", area="billing")
                messages.success(request, f"Statement sent to {', '.join(to)}.")
                return redirect(f"/billing/ar/statement/{client.pk}/")
            messages.error(request, "The email couldn't be sent. Check Settings › Email sending.")
    return render(request, "billing/statement.html", {**ctx, "to": ", ".join(_billing_people(client)), "can_edit": can(request.user, "billing", "edit"),
                                                      "app_url": settings.APP_URL, "mail_ok": mail.configured()})
