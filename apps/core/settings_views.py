import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render

from apps.accounts.views import my_security_view, security_log_view, users_view

from .audit import audit
from .models import AuditLog, JobRun, Setting
from .permissions import AREAS, can
from .settings_catalog import DEFAULTS, SETTINGS, field_specs, find


# Short descriptions under radio-card choices
OPTION_HELP = {
    "Google Workspace (Gmail API)": "Sign in once as support@. No passwords; works on any server.",
    "Gmail / SMTP": "smtp.gmail.com with an app password.",
    "SMTP2GO (HTTPS)": "Relay service with an API key.",
    "immediate": "Charge as soon as the invoice is sent.",
    "due_date": "Charge on the invoice's due date.",
    "always": "Every new email or portal ticket.",
    "after_hours": "Only when the office is closed.",
    "everyone": "Anyone can still use a password.",
    "admins": "Only admins keep a password, as a backup.",
}


@login_required
def settings_home(request):
    q = request.GET.get("q", "").strip().lower()
    admin = can(request.user, "admin")
    groups = []
    for gid, title, desc, items in SETTINGS:
        visible = []
        for item in items:
            if item[0] != "my_security" and not admin:
                continue
            labels = " ".join(f[1] for f in item[3]) if isinstance(item[3], list) else ""
            if q and q not in f"{title} {item[1]} {item[2]} {labels}".lower():
                continue
            visible.append(item)
        if visible:
            groups.append((title, desc, visible))
    return render(request, "core/settings_home.html", {"groups": groups, "q": q, "status": _status() if admin else {}})


def _status() -> dict:
    """One-word health per settings page, shown on the Settings home list. (text, tone)"""
    from apps.accounts import google
    from apps.billing import stripe_api

    from . import mail
    st = {}
    st["email"] = ("Set up", "good") if mail.configured() else ("Not set up", "bad")
    st["email_in"] = ("On", "good") if Setting.get("email.fetch_enabled", "") == "true" else ("Off", "")
    st["payments"] = (("Live" if stripe_api.live() else "Test mode"), "good") if stripe_api.configured() else ("Not connected", "")
    st["signin"] = ("Google on", "good") if google.enabled() else ("Passwords only", "")
    st["portal"] = ("On", "good") if Setting.get("portal.enabled", "true") != "false" else ("Off", "")
    st["google_chat"] = ("On", "good") if Setting.get("chat.webhook_url", "") else ("Off", "")
    st["branding"] = ("Logo set", "good") if Setting.get("brand.logo", "") else ("No logo yet", "")
    return st


@login_required
def settings_page(request, page):
    group, item = find(page)
    if not item:
        raise Http404
    target = item[3]
    if target == "my_security":
        return my_security_view(request)
    if not can(request.user, "admin"):
        raise PermissionDenied
    if target == "users":
        return users_view(request)
    if target == "security_log":
        return security_log_view(request)
    if target == "audit":
        return audit_view(request)
    if target == "jobs":
        return render(request, "core/jobs.html", {"jobs": _jobs()})
    if target == "email_designs":
        return render(request, "core/email_designs.html", {"samples": [(k, v[0]) for k, v in _samples().items()], "pick": request.GET.get("e", "ticket_reply")})
    if target == "queues":
        from apps.helpdesk.admin_views import queues_page
        return queues_page(request)
    if target == "portal_groups":
        from apps.portal.staff_views import groups_page
        return groups_page(request)
    if target == "old_settings":
        from apps.legacy.views import old_settings
        return old_settings(request)
    if target == "import":
        from apps.legacy.views import import_page
        return import_page(request)
    fields = field_specs(item)
    if request.method == "POST":
        if not can(request.user, "admin", "manage"):
            raise PermissionDenied
        errors, changed = [], []
        for f in fields:
            if f["type"] == "section":
                continue
            if f["type"] == "image":
                from .branding import remove_logo, save_logo
                if request.POST.get(f["key"] + "__remove"):
                    remove_logo()
                    changed.append(f["key"])
                elif request.FILES.get(f["key"]):
                    problem = save_logo(request.FILES[f["key"]])
                    if problem:
                        errors.append(problem)
                    else:
                        changed.append(f["key"])
                continue
            raw = request.POST.get(f["key"], "")
            if f["type"] == "bool":
                raw = "true" if request.POST.get(f["key"]) == "on" else "false"
            if f["type"] == "secret" and raw == "":
                continue  # blank secret = keep the saved one
            if f["type"] == "int" and raw and not raw.lstrip("-").isdigit():
                errors.append(f"{f['label']} must be a whole number.")
                continue
            if f["type"] == "select" and raw and raw not in f["options"]:
                errors.append(f"{f['label']}: pick one of the options.")
                continue
            if Setting.get(f["key"], None) != raw:
                Setting.put(f["key"], raw[:20000], secret=f["type"] == "secret", user=request.user)
                changed.append(f["key"])
        if errors:
            for e in errors:
                messages.error(request, e)
        else:
            if changed:
                audit(request, "settings", "settings", page, f"Changed {', '.join(changed)}", area="admin",
                      changes={k: ("[secret changed]" if next(x for x in fields if x["key"] == k)["type"] == "secret" else request.POST.get(k, "")) for k in changed})
            messages.success(request, "Settings saved.")
            return redirect(request.path)
    values = []
    stored = {s.key: s for s in Setting.objects.filter(key__in=[f["key"] for f in fields if f["key"]])}
    for f in fields:
        row = stored.get(f["key"])
        f = dict(f)
        if f["type"] == "section":
            values.append(f)
            continue
        if f["type"] == "image":
            from .branding import logo_url
            f["value"] = logo_url() if f["key"] == "brand.logo" else ""
            values.append(f)
            continue
        if f["type"] == "secret":
            f["is_set"] = bool(row and row.value)
            f["value"] = ""
        else:
            f["value"] = row.value if row else DEFAULTS.get(f["key"], "")
        values.append(f)
    sections, cur = [], {"title": "", "help": "", "fields": []}
    for f in values:
        if f["type"] == "section":
            if cur["fields"] or cur["title"]:
                sections.append(cur)
            cur = {"title": f["label"], "help": f["help"], "fields": []}
        else:
            cur["fields"].append(f)
    sections.append(cur)
    ctx = {"group": group, "item": item, "fields": values, "sections": [x for x in sections if x["fields"]], "can_manage": can(request.user, "admin", "manage"),
           "option_help": OPTION_HELP}
    if item[0] in ("email", "email_in"):
        from . import gmail
        ctx.update(gmail_connected=gmail.connected(), gmail_address=gmail.address(), gmail_redirect=gmail.redirect_uri(),
                   diag=request.session.pop("mail_diag", None))
    if item[0] == "payments":
        from django.conf import settings as dj
        ctx["webhook_url"] = f"{dj.APP_URL}/stripe/webhook/"
    if item[0] == "signin":
        from apps.accounts.google import redirect_uri
        ctx["google_redirect"] = redirect_uri()
    if item[0] == "email_in":
        from apps.helpdesk.models import InboundEmail
        ctx["inbound"] = InboundEmail.objects.select_related("ticket")[:25]
        ctx["last_fetch"] = Setting.get("email.last_fetch", "")
    return render(request, "core/settings_page.html", ctx)


@login_required
def email_test(request):
    """Settings › Email buttons: send a test email / check the support mailbox."""
    if request.method != "POST" or not can(request.user, "admin", "manage"):
        raise PermissionDenied
    if request.POST.get("what") == "diagnose":
        from . import mail
        request.session["mail_diag"] = mail.diagnose()
        return redirect("/settings/email/#diag")
    if request.POST.get("what") == "inbox":
        from apps.helpdesk.inbound import test_connection
        problem = test_connection()
        ok_text = "Signed in to the mailbox. Email to ticket can be turned on."
        back = "/settings/email_in/"
    else:
        from . import mail
        to = request.POST.get("to", "").strip() or request.user.email
        problem = mail.test(to)
        ok_text = f"Test email sent to {to}."
        back = "/settings/email/"
    (messages.error if problem else messages.success)(request, problem or ok_text)
    return redirect(back)


def audit_view(request):
    # Only entries for areas this person can see — e.g. managers without H/R access never see H/R changes.
    areas = [a for a in AREAS if can(request.user, a)]
    qs = AuditLog.objects.select_related("user").filter(Q(area__in=areas) | Q(area=""))
    q = request.GET.get("q", "").strip()[:200]
    if q:
        qs = qs.filter(summary__icontains=q)
    page = Paginator(qs, 100).get_page(request.GET.get("page"))
    for row in page.object_list:
        row.changes_text = json.dumps(row.changes, default=str)[:400] if row.changes else ""
    return render(request, "core/audit.html", {"page": page, "q": q})


def _jobs():
    from .jobs import JOBS
    runs = {r.name: r for r in JobRun.objects.all()}
    return [{"name": name, "label": j["label"], "every": j["every_minutes"], "run": runs.get(name)} for name, j in JOBS.items()]


@login_required
def gmail_connect(request):
    """Settings › Email sending › Connect Google mailbox (and the return from Google)."""
    from . import gmail
    if not can(request.user, "admin", "manage"):
        raise PermissionDenied
    if request.method == "POST":
        if request.POST.get("action") == "disconnect":
            gmail.disconnect()
            audit(request, "settings", "settings", "email", "Disconnected the Google mailbox", area="admin")
            messages.success(request, "Google mailbox disconnected.")
            return redirect("/settings/email/")
        try:
            return redirect(gmail.start(request.session, hint=Setting.get("email.support_address", "") or Setting.get("email.imap_user", "")))
        except gmail.GmailError as e:
            messages.error(request, str(e))
            return redirect("/settings/email/")
    try:
        addr = gmail.finish(request.session, request.GET)
    except Exception as e:  # noqa: BLE001 — shown to the admin in plain words
        messages.error(request, str(e))
        return redirect("/settings/email/")
    Setting.put("email.provider", "Google Workspace (Gmail API)", user=request.user)
    if not Setting.get("email.from_address", ""):
        Setting.put("email.from_address", addr, user=request.user)
    audit(request, "settings", "settings", "email", f"Connected the Google mailbox {addr}", area="admin")
    messages.success(request, f"Connected {addr}. Email now goes out through Google, and email to ticket can read this inbox without an app password. Send a test email to check.")
    return redirect("/settings/email/")


def _samples() -> dict:
    """Example data for previewing each email (nothing is sent)."""
    from types import SimpleNamespace as N

    from django.conf import settings as dj
    from django.utils import timezone

    portal = dj.PORTAL_BASE
    from datetime import timedelta
    t = N(number="ITDS-00921", subject="Printer won't print", contact_name="Maria Lopez", status="Resolved", resolution="Replaced the stuck print job and updated the driver.",
          response_due_at=timezone.now() + timedelta(hours=4))
    m = N(body="Hi Maria,\n\nThanks for the details. Please turn the printer off for 30 seconds, then on again, and try printing a test page.\n\nIf it still says offline, reply here and I'll connect remotely.", author_name="Casey Hervey")
    inv = N(number="INV-0451", balance="263.26", total="263.26", due_date=timezone.localdate() + timedelta(days=15))
    c = N(name="Franklin Title Co.", autopay_label="Visa ending 4242")
    p = N(amount="263.26", paid_on=timezone.localdate(), source="autopay", receipt_url="", invoice=inv)
    u = N(first_name="Maria", name="Maria Lopez", email="maria@example.com")
    return {
        "ticket_reply": ("Reply on a ticket", "email/ticket_reply", "Re: [ITDS-00921] Printer won't print", {"t": t, "m": m, "link": portal + "/tickets/1/"}),
        "ticket_received": ("We got your request", "email/ticket_received", "[ITDS-00921] Printer won't print", {"t": t, "link": portal + "/tickets/1/"}),
        "ticket_closed": ("Ticket resolved", "email/ticket_closed", "[ITDS-00921] Resolved: Printer won't print", {"t": t, "link": portal + "/tickets/1/", "footer": "If this isn't fully fixed, just reply to this email."}),
        "payment_receipt": ("Payment receipt", "email/payment_receipt", "Payment received — INV-0451", {"p": p, "inv": N(number="INV-0451", balance=0), "link": portal + "/invoices/1/", "message": "Thank you for your payment!"}),
        "autopay_failed": ("AutoPay declined", "email/autopay_failed", "We couldn't charge your Visa ending 4242 — INV-0451", {"inv": inv, "c": c, "message": "Your card was declined.", "give_up": False, "retry_days": 3, "link": portal + "/autopay/"}),
        "autopay_setup_link": ("AutoPay setup link", "email/autopay_setup_link", "Set up AutoPay", {"c": c, "link": portal + "/autopay/link/x/", "expires": timezone.now() + timedelta(days=7)}),
        "portal_invite": ("Portal invitation", "email/portal_invite", "You're invited to our client portal", {"u": u, "link": portal + "/link/x/", "invited_by": "Casey Hervey", "minutes": 10080}),
        "portal_magic": ("Portal sign-in link", "email/portal_magic", "Your sign-in link", {"u": u, "link": portal + "/link/x/", "minutes": 15}),
        "portal_reset": ("Portal password reset", "email/portal_reset", "Reset your portal password", {"u": u, "link": portal + "/link/x/", "minutes": 60}),
        "portal_secure_notice": ("New secure message", "email/portal_secure_notice", "You have a new secure message", {"u": u, "link": portal + "/messages/1/"}),
    }


@login_required
def email_preview(request, name):
    """One email rendered with example data, shown inside Settings › Email designs."""
    from django.http import Http404, HttpResponse
    from django.template.loader import render_to_string

    from . import mail
    if not can(request.user, "admin"):
        raise PermissionDenied
    smp = _samples().get(name)
    if not smp:
        raise Http404
    _label, tpl, subject, ctx = smp
    ctx = {"company": Setting.get("company.name") or "Weststar MSP", **ctx}
    html = mail.render_html(tpl, ctx, render_to_string(f"{tpl}.txt", ctx), subject)
    r = HttpResponse(html)
    r["Content-Security-Policy"] = "default-src 'none'; img-src 'self' https: data:; style-src 'unsafe-inline'; frame-ancestors 'self'; sandbox"
    r["X-Frame-Options"] = "SAMEORIGIN"
    return r
