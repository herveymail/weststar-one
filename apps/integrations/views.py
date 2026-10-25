import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import audit
from apps.core.models import Setting
from apps.core.permissions import can

from . import msp360
from .models import STATUS, Msp360Company, Msp360Computer, Msp360Plan


def _back(request, default="/backups/"):
    nxt = request.POST.get("next", "")
    return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else default)


@login_required
def backups(request):
    if not can(request.user, "tools", "view"):
        raise PermissionDenied
    show = request.GET.get("show", "problems")
    plans = Msp360Plan.objects.select_related("ticket")
    if show == "problems":
        plans = plans.exclude(status__in=[0, 3])
    plans = sorted(plans, key=lambda p: (p.status == 0, p.status == 3, p.company.lower(), p.computer.lower(), p.name))
    from apps.crm.models import Client
    companies = list(Msp360Company.objects.select_related("client"))
    ctx = {"s": msp360.summary(), "plans": plans, "show": show, "companies": companies, "computers": Msp360Computer.objects.all(),
           "clients": Client.objects.filter(archived_at__isnull=True).exclude(status="Former").only("id", "name").order_by("name"),
           "configured": msp360.configured(), "enabled": Setting.get("msp360.enabled", "false") == "true",
           "can_manage": can(request.user, "tools", "manage") or can(request.user, "admin", "manage"),
           "summary": json.loads(Setting.get("msp360.last_summary", "") or "{}"), "statuses": STATUS}
    return render(request, "integrations/backups.html", ctx)


def _manage(request):
    if not (can(request.user, "tools", "manage") or can(request.user, "admin", "manage")):
        raise PermissionDenied


@login_required
@require_POST
def backups_sync(request):
    _manage(request)
    r = msp360.sync()
    audit(request, "sync", "msp360", "", "MSP360 sync now", area="tools")
    if r["ok"]:
        msg = f"Synced {r['companies']} companies, {r['computers']} computers and {r['plans']} backup plans."
        if r.get("tickets_opened") or r.get("tickets_resolved") or r.get("tickets_noted"):
            msg += f" Tickets: {r.get('tickets_opened', 0)} opened, {r.get('tickets_noted', 0)} updated, {r.get('tickets_resolved', 0)} resolved."
        messages.success(request, msg)
    else:
        messages.error(request, f"MSP360 sync failed: {r['error']}")
    return _back(request)


@login_required
@require_POST
def backups_test(request):
    _manage(request)
    r = msp360.test()
    if r["ok"]:
        messages.success(request, f"Connected to MSP360: {r['companies']} companies, {r['plans']} backup plans.")
    else:
        messages.error(request, r["error"])
    return _back(request, "/settings/msp360/")


@login_required
@require_POST
def backups_companies(request):
    _manage(request)
    from apps.crm.models import Client
    changed = 0
    for co in Msp360Company.objects.all():
        field = f"client_{co.pk}"
        if field not in request.POST:
            continue
        raw = request.POST.get(field, "")
        client = Client.objects.filter(pk=int(raw)).first() if raw.isdigit() else None
        if client != co.client:
            co.client, co.client_set_by_hand = client, True
            co.save(update_fields=["client", "client_set_by_hand"])
            changed += 1
    if changed:
        audit(request, "update", "msp360", "", f"Matched {changed} MSP360 companies to clients", area="tools")
    messages.success(request, f"Saved. {changed} compan{'y' if changed == 1 else 'ies'} changed." if changed else "No changes.")
    return redirect("/backups/?show=companies")


# ── Settings › Integrations ──
def _card(key, name, desc, state, tone, detail="", settings_url="", actions=(), open_url="", built=True):
    return {"key": key, "name": name, "desc": desc, "state": state, "tone": tone, "detail": detail, "settings_url": settings_url,
            "actions": actions, "open_url": open_url, "built": built}


def _ago(iso: str) -> str:
    from datetime import datetime

    from django.utils import timezone
    from django.utils.timesince import timesince
    try:
        return timesince(datetime.fromisoformat(iso), timezone.now()).split(",")[0] + " ago"
    except (ValueError, TypeError):
        return ""


def cards() -> list[dict]:
    from apps.accounts import google
    from apps.billing import stripe_api
    from apps.core import gmail, mail
    from apps.helpdesk import ai

    out = []
    # MSP360
    m_on, m_cfg = Setting.get("msp360.enabled", "false") == "true", msp360.configured()
    err, last = Setting.get("msp360.last_error", ""), Setting.get("msp360.last_sync", "")
    if not m_cfg:
        st = ("Not set up", "")
    elif err:
        st = ("Error", "bad")
    elif not m_on:
        st = ("Off", "warn")
    else:
        st = ("Connected", "good")
    s = msp360.summary()
    detail = (f"Last sync {_ago(last)} · {s['computers']} computers · {s['plans']} plans · {s['failed']} failed · {s['overdue']} overdue"
              if last else "Never synced yet.") + (f"\n{err}" if err else "")
    out.append(_card("msp360", "MSP360 backups", "Backup health per client. Opens a ticket when a plan fails and resolves it when the backup succeeds.",
                     *st, detail, "/settings/msp360/", [("Test connection", "/backups/test/"), ("Sync now", "/backups/sync/")] if m_cfg else (), "/backups/"))
    # Email
    out.append(_card("gmail", "Google Workspace mailbox", "Sends email as support@ and reads it for email-to-ticket.",
                     *(("Connected", "good") if gmail.connected() else ("Not connected", "")), gmail.address() or "", "/settings/email/"))
    out.append(_card("email", "Email sending", "How Weststar One sends email to clients and staff.",
                     *(("Working", "good") if mail.configured() else ("Not set up", "bad")), f"Provider: {mail.provider()}", "/settings/email/"))
    fetch = Setting.get("email.fetch_enabled", "") == "true"
    out.append(_card("email_in", "Email to ticket", "Turns email to the support mailbox into tickets.",
                     *(("On", "good") if fetch else ("Off", "")), f"Last checked {_ago(Setting.get('email.last_fetch', ''))}" if fetch and Setting.get("email.last_fetch", "") else "", "/settings/email_in/"))
    out.append(_card("google_sso", "Google sign-in", "Staff sign in with their Google Workspace account.",
                     *(("On", "good") if google.enabled() else ("Off", "")), Setting.get("google.domains", ""), "/settings/signin/"))
    pay = stripe_api.configured()
    out.append(_card("stripe", "Stripe payments & AutoPay", "Card and bank payments in the portal, AutoPay.",
                     *((("Live" if stripe_api.live() else "Test mode"), "good") if pay else ("Not connected", "")),
                     "" if not pay else ("Webhook secret saved" if Setting.get("stripe.webhook_secret", "") else "Webhook secret missing: bank payments and refunds won't update"),
                     "/settings/payments/"))
    out.append(_card("ai", "AI assistant", "Ticket triage, summaries, reply drafts and automatic first responses.",
                     *(("On", "good") if ai.enabled() else ("Off", "")), (Setting.get("ai.provider", "") + " " + Setting.get("ai.model", "")).strip(), "/settings/ai/"))
    out.append(_card("google_chat", "Google Chat", "Ticket alerts in a Google Chat space.",
                     *(("On", "good") if Setting.get("chat.webhook_url", "") else ("Off", "")), "", "/settings/google_chat/"))
    out.append(_card("offsite", "Offsite backups (Wasabi / S3)", "Where the nightly backup of this app is copied.",
                     *(("Set up", "good") if Setting.get("backup.s3_bucket", "") and Setting.get("backup.s3_key", "") else ("Not set up", "")), Setting.get("backup.s3_bucket", ""), "/settings/offsite/"))
    # Not rebuilt yet — say so plainly.
    for key, name, desc, url, saved in (
        ("yeastar", "Yeastar phone system", "Call log sync and recordings on tickets and clients.", "/settings/phone/", Setting.get("phone.yeastar_client_id", "")),
        ("rmm", "Datto RMM", "Devices and alerts per client.", "/settings/rmm/", Setting.get("rmm.api_key", "")),
        ("staffshield", "StaffShield training", "Security training courses and certificates.", "", ""),
        ("zoho_assist", "Zoho Assist", "Start remote sessions from a ticket.", "", ""),
    ):
        out.append(_card(key, name, desc, "Being rebuilt", "warn", "Your settings from the old app are saved and will be used once this is rebuilt." if saved else "Not rebuilt yet.", url, built=False))
    return out


def hub(request):
    """Settings › Integrations (called from settings_page)."""
    return render(request, "integrations/hub.html", {"cards": cards(), "can_manage": can(request.user, "admin", "manage")})
