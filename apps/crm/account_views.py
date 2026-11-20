"""Client page: account flags, the text-message log, and offboarding a client we're letting go."""
import csv
import io
import zipfile
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.audit import audit
from apps.core.models import EncryptedField
from apps.core.permissions import can

from .models import Client, ClientFlag, ClientText, Offboarding, OffboardingStep


def _client(request, pk, need="view"):
    if not can(request.user, "clients", need):
        raise PermissionDenied
    return get_object_or_404(Client, pk=pk)


def _date(v):
    try:
        return date.fromisoformat((v or "").strip())
    except ValueError:
        return None


# ── Flags ──
@login_required
def flags(request, pk):
    c = _client(request, pk)
    if request.method == "POST":
        _client(request, pk, "edit")
        if request.POST.get("clear"):
            f = get_object_or_404(ClientFlag, pk=request.POST["clear"], client=c, cleared_at__isnull=True)
            f.cleared_at, f.cleared_by, f.clear_note = timezone.now(), request.user, request.POST.get("clear_note", "").strip()[:255]
            f.save()
            audit(request, "flag_cleared", "client", c.pk, f"Cleared flag \"{f.label}\" on {c.name}", area="clients")
        else:
            label = request.POST.get("label", "").strip()[:120]
            level = request.POST.get("level") if request.POST.get("level") in dict(ClientFlag.LEVELS) else "warn"
            if label:
                ClientFlag.objects.create(client=c, label=label, level=level, note=request.POST.get("note", "").strip()[:2000],
                                          expires_on=_date(request.POST.get("expires_on")), set_by=request.user)
                audit(request, "flag_set", "client", c.pk, f"Flagged {c.name}: {label}", area="clients")
        return redirect(f"/clients/{c.pk}/?tab=Flags")
    rows = list(c.flags.select_related("set_by", "cleared_by"))
    return render(request, "crm/_flags.html", {"c": c, "active": [f for f in rows if f.active], "past": [f for f in rows if not f.active],
                                               "levels": ClientFlag.LEVELS, "presets": ClientFlag.PRESETS, "can_edit": can(request.user, "clients", "edit")})


# ── Text messages ──
@login_required
def texts(request, pk):
    from apps.accounts.models import User
    from apps.files.services import save_uploads
    c = _client(request, pk)
    error = ""
    if request.method == "POST":
        _client(request, pk, "edit")
        summary, when = request.POST.get("summary", "").strip()[:255], _date(request.POST.get("happened_on"))
        files = request.FILES.getlist("files")
        transcript = request.POST.get("transcript", "").strip()[:50000]
        if not summary or not when:
            error = "Add the date of the texts and a line on what they were about."
        elif not files and not transcript:
            error = "Add the screenshots, or type or paste the messages."
        else:
            from apps.helpdesk.models import Ticket
            num = request.POST.get("ticket", "").strip().lstrip("#")
            t = ClientText.objects.create(
                client=c, happened_on=when, summary=summary, transcript=transcript, created_by=request.user,
                staff=User.objects.filter(pk=request.POST.get("staff") or 0, is_active=True).first() or request.user,
                contact_name=request.POST.get("contact_name", "").strip()[:200], their_number=request.POST.get("their_number", "").strip()[:50],
                ticket=Ticket.objects.filter(number__iexact=num, client=c).first() if num else None)
            try:
                if files:
                    save_uploads(request, files, kind="client", client=c, text=t)
            except ValidationError as e:
                error = " ".join(e.messages)
            audit(request, "text_log", "client", c.pk, f"Filed text messages for {c.name}: {summary}", area="clients")
            if t.ticket_id:
                from apps.helpdesk.services import event
                event(t.ticket, f"Text messages filed on the client record by {request.user.name}: {summary}", request.user)
    if request.method == "POST" and not error:
        return redirect(f"/clients/{c.pk}/?tab=Texts")
    return render(request, "crm/_texts.html", {
        "c": c, "rows": c.texts.select_related("staff", "ticket", "created_by").prefetch_related("uploads"), "error": error, "post": request.POST,
        "staff": User.objects.filter(is_active=True).order_by("name"), "today": timezone.localdate(), "contacts": c.contacts.filter(archived_at__isnull=True),
        "can_edit": can(request.user, "clients", "edit"), "can_manage": can(request.user, "clients", "manage")})


@login_required
@require_POST
def text_delete(request, pk, text_id):
    c = _client(request, pk, "manage")
    t = get_object_or_404(ClientText, pk=text_id, client=c)
    for u in t.uploads.all():
        u.file.delete(save=False)
    audit(request, "text_delete", "client", c.pk, f"Deleted filed text messages for {c.name}: {t.summary}", area="clients")
    t.delete()
    return redirect(f"/clients/{c.pk}/?tab=Texts")


# ── Offboarding ──
def _billing_facts(c, request):
    """What the Final invoice and Cancel steps need to show."""
    if not can(request.user, "billing"):
        return {}
    from apps.billing import ready
    from apps.billing.models import Invoice
    unbilled = next(iter(ready.collect(timezone.localdate(), [c.pk])), None)
    open_inv = list(Invoice.objects.filter(client=c, archived_at__isnull=True, status__in=["Sent", "Viewed", "Partial", "Overdue"]).order_by("due_date"))
    return {"billing": True, "unbilled": unbilled, "open_invoices": open_inv, "owed": sum((i.balance for i in open_inv), 0),
            "drafts": Invoice.objects.filter(client=c, archived_at__isnull=True, status="Draft"),
            "recurring": c.recurring_invoices.filter(archived_at__isnull=True, status="Active"),
            "contracts": c.contracts.filter(archived_at__isnull=True, status__in=["Draft", "Sent", "Active"]),
            "renewals": c.renewals.filter(archived_at__isnull=True, status="Upcoming"), "can_bill": can(request.user, "billing", "edit")}


@login_required
def offboarding(request, pk):
    c = _client(request, pk)
    ob = c.offboardings.filter(status="Open").first()
    if request.method == "POST":
        _client(request, pk, "manage")
        act = request.POST.get("action")
        if act == "start" and ob is None:
            ob = Offboarding.objects.create(client=c, reason=request.POST.get("reason", "").strip()[:5000], last_day=_date(request.POST.get("last_day")), started_by=request.user)
            if not c.flags.filter(label="Offboarding", cleared_at__isnull=True).exists():
                ClientFlag.objects.create(client=c, label="Offboarding", level="stop", set_by=request.user,
                                          note="We are letting this client go" + (f"; last day of service {ob.last_day:%b %-d, %Y}" if ob.last_day else "") + ". Check with a manager before taking on new work.")
            audit(request, "offboarding_start", "client", c.pk, f"Started offboarding {c.name}", area="clients")
        elif ob and act == "step":
            key = request.POST.get("key")
            if key in dict((k, 1) for k, _t, _h in Offboarding.STEPS):
                row, _ = OffboardingStep.objects.get_or_create(offboarding=ob, key=key)
                done = request.POST.get("done") == "1"
                row.note = request.POST.get("note", row.note).strip()[:5000]
                if done and not row.done_at:
                    row.done_at, row.done_by = timezone.now(), request.user
                elif not done:
                    row.done_at, row.done_by = None, None
                row.save()
                audit(request, "offboarding_step", "client", c.pk, f"Offboarding {c.name}: \"{dict((k, t) for k, t, _h in Offboarding.STEPS)[key]}\" {'done' if done else 'reopened'}", area="clients")
        elif ob and act == "final_invoice" and can(request.user, "billing", "edit"):
            from apps.billing import ready
            made = ready.create_drafts([c.pk], timezone.localdate(), request.user)
            if made:
                messages.success(request, f"Draft invoice {made[0].number} created with everything unbilled. Check it, then send it.")
                return redirect(f"/billing/invoice/{made[0].pk}/")
            messages.info(request, "Nothing unbilled to put on an invoice.")
        elif ob and act == "stop_billing" and can(request.user, "billing", "edit"):
            n = c.recurring_invoices.filter(archived_at__isnull=True, status="Active").update(status="Paused")
            k = c.contracts.filter(archived_at__isnull=True, status__in=["Draft", "Sent", "Active"]).update(status="Cancelled", end_date=ob.last_day or timezone.localdate())
            r = c.renewals.filter(archived_at__isnull=True, status="Upcoming").update(status="Cancelled")
            if c.autopay_enabled:
                from apps.billing import payments
                payments.turn_off(c, by=request.user.name)
            audit(request, "offboarding_stop_billing", "client", c.pk, f"Offboarding {c.name}: paused {n} recurring, cancelled {k} contracts and {r} renewals", area="billing")
            messages.success(request, f"Paused {n} recurring schedule(s), cancelled {k} contract(s) and {r} renewal(s){', AutoPay turned off' if c.autopay_enabled else ''}. Licences bought from vendors still need cancelling with the vendor.")
        elif ob and act == "cancel":
            ob.status = "Cancelled"
            ob.save(update_fields=["status"])
            c.flags.filter(label="Offboarding", cleared_at__isnull=True).update(cleared_at=timezone.now(), cleared_by=request.user, clear_note="Offboarding called off")
            audit(request, "offboarding_cancel", "client", c.pk, f"Offboarding of {c.name} called off", area="clients")
        elif ob and act == "finish":
            if ob.left:
                messages.error(request, f"{ob.left} step(s) are still open. Tick them off (add a note if one doesn't apply) before closing the account.")
            else:
                ob.status, ob.finished_at, ob.finished_by = "Done", timezone.now(), request.user
                ob.save()
                Client.objects.filter(pk=c.pk).update(status="Former")
                c.portal_users.update(is_active=False)
                c.flags.filter(label="Offboarding", cleared_at__isnull=True).update(cleared_at=timezone.now(), cleared_by=request.user, clear_note="Offboarding finished")
                ClientFlag.objects.create(client=c, label="Former client — do not service", level="stop", set_by=request.user,
                                          note=f"Offboarded {timezone.localdate():%b %-d, %Y}. Talk to a manager before doing any work.")
                audit(request, "offboarding_done", "client", c.pk, f"Finished offboarding {c.name}; client marked Former and portal sign-ins turned off", area="clients")
                messages.success(request, f"{c.name} is offboarded: marked Former, portal sign-ins turned off.")
        return redirect(f"/clients/{c.pk}/?tab=Offboarding")
    ctx = {"c": c, "ob": ob, "past": c.offboardings.exclude(status="Open").select_related("started_by", "finished_by"), "can_manage": can(request.user, "clients", "manage"),
           "today": timezone.localdate()}
    if ob:
        ctx.update(steps=ob.steps(), **_billing_facts(c, request), portal_users=c.portal_users.filter(is_active=True).count(),
                   open_tickets=c.tickets.filter(status__in=["New", "Open", "Waiting on client", "Waiting on vendor", "Scheduled"]).count())
        for s in ctx["steps"]:
            if s["row"]:
                s["who"] = s["row"].done_by.name if s["row"].done_by else ""
    return render(request, "crm/_offboarding.html", ctx)


SKIP = ("stripe", "autopay", "token", "legacy_id", "imported_at", "created_by", "password", "secret")


def _csv(qs) -> str:
    """Every plain column of these rows as CSV. Encrypted values, payment-provider ids and internal bookkeeping are left out."""
    model = qs.model
    fields = [f for f in model._meta.concrete_fields if not isinstance(f, EncryptedField) and not any(x in f.name for x in SKIP)]
    out = io.StringIO()
    w = csv.writer(out)
    w.writerow([f.verbose_name.title() if f.verbose_name.islower() else f.verbose_name for f in fields])
    for o in qs:
        row = []
        for f in fields:
            v = getattr(o, f.name)
            v = "" if v is None else str(v)
            row.append("'" + v if v[:1] in "=+-@" and not v[1:2].isdigit() else v)  # no spreadsheet formulas
        w.writerow(row)
    return out.getvalue()


@login_required
def offboarding_export(request, pk):
    """A ZIP of the client's records to hand back to them. Private notes, saved secrets and payment ids are not included."""
    from apps.core.registry import REGISTRY
    c = _client(request, pk, "manage")
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("README.txt", f"Records for {c.name}, exported {timezone.localtime():%B %-d, %Y %-I:%M %p}.\n\n"
                   "Spreadsheets (.csv) open in Excel or Google Sheets. The tickets folder has one text file per ticket.\n"
                   "Not included: our internal notes, saved passwords, and payment-processor details.\n")
        z.writestr("client.csv", _csv(Client.objects.filter(pk=c.pk)))
        for slug in ("contacts", "assets", "networks", "domains", "contracts", "invoices", "quotes", "payments", "projects", "renewals", "policies"):
            m = REGISTRY.get(slug)
            if m is None or not any(f.name == "client" for f in m.model._meta.concrete_fields):
                continue
            qs = m.model.objects.filter(client=c)
            if hasattr(m.model, "archived_at"):
                qs = qs.filter(archived_at__isnull=True)
            if qs.exists():
                z.writestr(f"{slug}.csv", _csv(qs))
        tickets = c.tickets.order_by("created_at")
        if tickets.exists():
            z.writestr("tickets.csv", _csv(tickets))
            for t in tickets:
                lines = [f"{t.number} · {t.subject}", f"Opened {timezone.localtime(t.created_at):%b %-d, %Y %-I:%M %p} · Status {t.status}", "", (t.details or "").strip(), ""]
                for m in t.messages.filter(kind="reply").order_by("created_at"):
                    lines += [f"--- {m.author_name or 'Weststar'} · {timezone.localtime(m.created_at):%b %-d, %Y %-I:%M %p}", (m.body or "").strip(), ""]
                if t.resolution:
                    lines += ["--- Resolution", t.resolution.strip()]
                z.writestr(f"tickets/{t.number or t.pk}.txt", "\n".join(lines))
        n = 0
        for u in c.uploads.filter(text__isnull=True):
            try:
                with u.file.open("rb") as fh:
                    z.writestr(f"files/{u.pk}-{u.original_name}", fh.read())
                    n += 1
            except OSError:
                continue
            if n >= 500:
                break
    audit(request, "export", "client", c.pk, f"Exported the records of {c.name} (offboarding)", area="clients")
    r = HttpResponse(buf.getvalue(), content_type="application/zip")
    r["Content-Disposition"] = f'attachment; filename="{"".join(ch if ch.isalnum() else "-" for ch in c.name).strip("-")}-records-{timezone.localdate():%Y-%m-%d}.zip"'
    return r
