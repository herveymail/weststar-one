"""Staff ticket screens: Classic (views rail + card rows + 3-column ticket page) and Grid (sortable table
with the ticket docked beside it). Each person picks theirs in Profile; both use the same actions."""
from datetime import datetime, time, timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.utils.html import escape
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.audit import audit
from apps.core.models import Setting
from apps.core.permissions import can
from apps.crm.models import Client, Contact

from . import queries, services
from .models import CATEGORIES, OPEN_STATUSES, PRIORITIES, STATUSES, WORK_TYPES, Queue, Ticket, TicketApproval, TicketTimer
from .signoff import SignoffRequired, completion_required

AVATAR_COLORS = ["#2c5cc5", "#12805c", "#a35b00", "#5a3fc0", "#0b6e8f", "#b83a8a", "#c2410c", "#0f766e"]
TIME_CHOICES = [(0, "0h"), (15, "15m"), (30, "30m"), (45, "45m"), (60, "1h"), (90, "1.5h"), (120, "2h"), (180, "3h"), (240, "4h"), (360, "6h"), (480, "8h")]


def _need(request, level="view"):
    if not can(request.user, "tickets", level):
        raise PermissionDenied


def _int(v):
    return int(v) if str(v or "").isdigit() else None


def saved_replies() -> list[dict]:
    """Settings › Saved replies: blocks separated by a line of ---; the first line is the name."""
    out = []
    for block in Setting.get("tickets.saved_replies", "").replace("\r", "").split("\n---"):
        lines = block.strip("\n-").split("\n")
        if lines and lines[0].strip():
            out.append({"title": lines[0].strip()[:80], "body": "\n".join(lines[1:]).strip()})
    return out


def categories() -> list[str]:
    custom = [c.strip() for c in Setting.get("tickets.categories", "").replace(",", "\n").split("\n") if c.strip()]
    return custom or CATEGORIES


# ── lists ──
@login_required
def tickets(request):
    _need(request)
    if request.user.tickets_ui == "grid":
        return _grid(request)
    return _classic(request)


def _rail(request, base):
    views = queries.classic_views(request.user)
    view_counts = queries.counts(base, views)
    open_q = base.filter(status__in=OPEN_STATUSES).filter(queries.not_snoozed())
    queue_rows = [{"q": q, "n": open_q.filter(queue=q).count(), "key": f"queue:{q.pk}"} for q in Queue.objects.filter(active=True)]
    client_rows = [dict(c, key=f"client:{c['client_id']}") for c in
                   open_q.exclude(client=None).values("client_id", "client__name").annotate(n=Count("id")).order_by("-n", "client__name")[:6]]
    agent_rows = [{"u": u, "n": open_q.filter(assigned_to=u).count(), "key": f"agent:{u.pk}"}
                  for u in User.objects.filter(is_active=True).exclude(role="viewer")]
    return {"views": [(k, label, view_counts.get(k, 0)) for k, label, _f in views], "rail_queues": queue_rows,
            "rail_clients": client_rows, "agents": agent_rows}


def _classic(request):
    base = queries.base_qs()
    views = {k: (label, f) for k, label, f in queries.classic_views(request.user)}
    view = request.GET.get("view", "unresolved")
    if view not in views:
        view = "unresolved"
    title, cond = views[view]
    qs = base.filter(cond)
    for key, field, model in (("queue", "queue_id", Queue), ("client", "client_id", Client), ("agent", "assigned_to_id", User)):
        val = _int(request.GET.get(key))
        if val:
            obj = model.objects.filter(pk=val).first()
            if obj:
                qs = base.filter(Q(status__in=OPEN_STATUSES) & queries.not_snoozed(), **{field: val})
                title, view = str(obj), f"{key}:{val}"
    qs = queries.search(qs, request.GET.get("q"))
    sort = request.GET.get("sort", "priority")
    order = {"newest": ["-created_at"], "oldest": ["created_at"], "updated": ["-updated_at"]}.get(sort)
    qs = qs.order_by(*order) if order else qs.annotate(_p=queries.priority_order()).order_by("_p", "-updated_at")
    page = Paginator(qs, 50).get_page(request.GET.get("page"))
    ctx = {"page": page, "title": title, "view": view, "sort": sort, "q": request.GET.get("q", ""), "avatar_colors": AVATAR_COLORS,
           "now": timezone.now(), **_rail(request, base)}
    return render(request, "helpdesk/classic_list.html", ctx)


GRID_SORTS = {"number": "number", "subject": "subject", "company": "client__name", "queue": "queue__name", "status": "status", "computer": "computer_name",
              "priority": "_p", "assignee": "assigned_to__name", "created": "created_by__name", "updated": "updated_at"}


def _grid(request, open_pk=None):
    base = queries.base_qs()
    tabs = queries.grid_tabs()
    tab = request.GET.get("tab", "open")
    if tab not in {k for k, _l, _f in tabs}:
        tab = "open"
    qs = base.filter(dict((k, f) for k, _l, f in tabs)[tab])
    chips = queries.grid_views(request.user)
    chip = request.GET.get("chip", "")
    if chip in {k for k, _l, _f in chips}:
        qs = qs.filter(dict((k, f) for k, _l, f in chips)[chip])
    filters = {"company": "client_id", "queue": "queue_id", "assignee": "assigned_to_id", "created_by": "created_by_id"}
    for key, field in filters.items():
        if _int(request.GET.get(key)):
            qs = qs.filter(**{field: int(request.GET[key])})
    if request.GET.get("priority") in PRIORITIES:
        qs = qs.filter(priority=request.GET["priority"])
    qs = queries.with_extras(qs)
    if request.GET.get("computer"):
        qs = qs.filter(computer_name=request.GET["computer"])
    if request.GET.get("mine"):
        qs = qs.filter(assigned_to=request.user)
    if request.GET.get("unread"):
        qs = qs.filter(_unread__gt=0)
    if request.GET.get("backup"):
        qs = qs.filter(source="MSP360")
    qs = queries.search(qs, request.GET.get("q"))
    sort = request.GET.get("sort", "updated")
    if sort not in GRID_SORTS:
        sort = "updated"
    desc = request.GET.get("dir", "desc" if sort == "updated" else "asc") == "desc"
    qs = qs.annotate(_p=queries.priority_order()).order_by(("-" if desc else "") + GRID_SORTS[sort], "-id")
    page = Paginator(qs, 25).get_page(request.GET.get("page"))
    open_pk = open_pk or _int(request.GET.get("open"))
    ctx = {"page": page, "tab": tab, "chip": chip, "sort": sort, "desc": desc, "q": request.GET.get("q", ""),
           "tabs": [(k, label, n) for (k, label, _f), n in zip(tabs, queries.counts(base, tabs).values(), strict=True)],
           "chips": [(k, label) for k, label, _f in chips], "now": timezone.now(),
           "clients": Client.objects.filter(archived_at__isnull=True).order_by("name"), "queues": Queue.objects.filter(active=True),
           "users": User.objects.filter(is_active=True).order_by("name"), "priorities": PRIORITIES, "statuses": STATUSES,
           "f": {k: request.GET.get(k, "") for k in [*filters, "priority", "computer", "mine", "unread", "backup"]}, "open_pk": open_pk,
           "computers": queries.computers(),
           "sort_cols": [("number", "Ticket"), ("subject", "Subject"), ("company", "Company"), ("queue", "Queue"), ("computer", "Computer"), ("status", "Status"),
                         ("priority", "Priority"), ("assignee", "Assignee"), ("created", "Created by"), ("updated", "Updated")]}
    if open_pk:
        t = Ticket.objects.filter(pk=open_pk).first()
        if t:
            ctx.update(_detail_ctx(request, t, panel=True))
    if request.headers.get("HX-Request") and request.headers.get("HX-Target") == "grid-body":
        return render(request, "helpdesk/_grid_table.html", ctx)
    return render(request, "helpdesk/grid_list.html", ctx)


# ── one ticket ──
def _ai_on() -> bool:
    from . import ai
    return ai.enabled()


def _detail_ctx(request, t: Ticket, panel=False) -> dict:
    t = Ticket.objects.select_related("client", "assigned_to", "contact", "queue", "merged_into").get(pk=t.pk)
    msgs = list(t.messages.select_related("author").all())
    uploads = list(t.uploads.order_by("created_at"))
    by_msg = {}
    for u in uploads:
        by_msg.setdefault(u.message_id, []).append(u)
    for m in msgs:
        m.files = by_msg.get(m.pk, [])
    time_rows = t.time_entries.aggregate(m=Sum("minutes"), b=Sum("minutes", filter=Q(billable=True)), unbilled=Sum("minutes", filter=Q(billable=True, invoice__isnull=True)))
    timer = TicketTimer.objects.filter(ticket=t, user=request.user).first()
    other_timer = TicketTimer.objects.filter(ticket=t).exclude(user=request.user).select_related("user").first()
    rate = t.client.hourly_rate if t.client_id and t.client.hourly_rate else None
    try:
        rate = rate or float(Setting.get("billing.hourly_rate", "0") or 0) or None
    except ValueError:
        rate = None
    return {
        "t": t, "msgs": msgs, "loose_files": by_msg.get(None, []), "panel": panel,
        "computer": __import__("apps.integrations.models", fromlist=["Msp360Plan"]).Msp360Plan.objects.filter(ticket=t).first(),
        "signoffs": list(t.signoffs.select_related("user")), "approvals": list(t.approvals.select_related("user")),
        "approval_via": TicketApproval.VIA, "signoff_needed": t.is_open and completion_required(t),
        "conversation_count": sum(1 for m in msgs if m.kind != "event"),
        "history": [m for m in msgs if m.kind == "event"],
        "minutes": time_rows["m"] or 0, "billable_minutes": time_rows["b"] or 0, "unbilled_minutes": time_rows["unbilled"] or 0,
        "value": round((time_rows["m"] or 0) / 60 * float(rate), 2) if rate else None,
        "timer": timer, "other_timer": other_timer,
        "users": User.objects.filter(is_active=True).order_by("name"), "statuses": STATUSES, "priorities": PRIORITIES,
        "ai_on": _ai_on(),
        "queues": Queue.objects.filter(active=True), "categories": categories(), "work_types": WORK_TYPES, "time_choices": TIME_CHOICES,
        "saved_replies": saved_replies(), "can_edit": can(request.user, "tickets", "edit"),
        "client_open": t.client.tickets.filter(status__in=OPEN_STATUSES).exclude(pk=t.pk).order_by("-updated_at")[:5] if t.client_id else [],
        "contract": t.client.contracts.filter(status="Active", archived_at__isnull=True).first() if t.client_id else None,
        "escalate_to": t.queue.escalate_to if t.queue_id and t.queue.escalate_to_id else None,
        "now": timezone.now(), "avatar_colors": AVATAR_COLORS,
    }


@login_required
def ticket_detail(request, pk):
    _need(request)
    t = get_object_or_404(Ticket, pk=pk)
    if request.user.tickets_ui == "grid" and request.GET.get("classic") != "1":
        return _grid(request, open_pk=t.pk)
    base = queries.base_qs()
    return render(request, "helpdesk/ticket_page.html", {**_detail_ctx(request, t), **_rail(request, base), "view": ""})


@login_required
def ticket_panel(request, pk):
    _need(request)
    t = get_object_or_404(Ticket, pk=pk)
    return render(request, "helpdesk/_panel.html", _detail_ctx(request, t, panel=True))


def _after_change(request, t, signoff_needed=False):
    """Re-render whatever the change came from: the grid's panel, or reload the classic page."""
    if signoff_needed:
        messages.error(request, f"{t.number} is a break/fix ticket: get the customer's sign-off (or override it) before closing.")
    if request.POST.get("ctx") == "panel" or request.GET.get("ctx") == "panel":
        resp = render(request, "helpdesk/_panel.html", {**_detail_ctx(request, t, panel=True), "signoff_needed": signoff_needed})
        resp["HX-Trigger"] = "ticketsChanged"
        return resp
    if request.headers.get("HX-Request"):
        r = HttpResponse(status=204)
        r["HX-Refresh"] = "true"
        return r
    return redirect(f"/tickets/{t.pk}/")


@login_required
@require_POST
def ticket_update(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    changes = {}
    if request.POST.get("status") in STATUSES:
        changes["status"] = request.POST["status"]
    if request.POST.get("priority") in PRIORITIES:
        changes["priority"] = request.POST["priority"]
    if "assigned_to" in request.POST:
        v = request.POST["assigned_to"]
        changes["assigned_to"] = request.user if v == "me" else None if v == "" else get_object_or_404(User, pk=_int(v) or 0, is_active=True)
    if "queue" in request.POST:
        v = request.POST["queue"]
        changes["queue"] = None if v == "" else get_object_or_404(Queue, pk=_int(v) or 0)
    if "category" in request.POST:
        changes["category"] = request.POST["category"][:100]
    if "billable" in request.POST:
        changes["billable"] = request.POST["billable"] in ("1", "on", "true")
    if request.POST.get("subject", "").strip():
        changes["subject"] = request.POST["subject"].strip()[:255]
    if "cc" in request.POST:
        changes["cc"] = request.POST["cc"].strip()[:1000]
    try:
        services.update_ticket(t, user=request.user, request=request, **changes)
    except SignoffRequired:
        return _after_change(request, t, signoff_needed=True)
    return _after_change(request, t)


@login_required
@require_POST
def ticket_message(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    kind = request.POST.get("kind", "reply")
    if kind not in ("reply", "note", "work"):
        kind = "reply"
    body = request.POST.get("body", "").strip()[:50000]
    files = request.FILES.getlist("files")
    if not body and files:
        body = "Attached " + ", ".join(f.name for f in files[:5]) + ("…" if len(files) > 5 else "")
    if not body:
        messages.error(request, "Write a message first.")
        return _after_change(request, t)
    try:
        if request.POST.get("hours", "").strip():
            minutes = round(float(request.POST["hours"]) * 60)  # the grid panel asks in hours, like the old app
        else:
            minutes = int(request.POST.get("minutes") or 0)
        minutes = max(0, min(minutes, 1440))
    except ValueError:
        minutes = 0
    work_type = request.POST.get("work_type") if request.POST.get("work_type") in WORK_TYPES else "Remote"
    status_after = request.POST.get("status_after", "") if request.POST.get("status_after") in STATUSES else ""
    msg = services.add_message(t, user=request.user, kind=kind, body=body, minutes=minutes, work_type=work_type,
                               billable=request.POST.get("billable") in ("1", "on", "true"), status_after=status_after,
                               cc=request.POST.get("cc", "")[:1000] if kind == "reply" else "", request=request)
    if files:
        from apps.files.services import save_uploads
        try:
            save_uploads(request, files, kind="ticket", ticket=t, message=msg)
        except ValidationError as e:
            messages.error(request, " ".join(e.messages))
    return _after_change(request, t)


@login_required
@require_POST
def ticket_timer(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    action = request.POST.get("action")
    if action == "start":
        services.start_timer(t, request.user)
    elif action in ("stop", "discard"):
        n = services.stop_timer(t, request.user, save=action == "stop", request=request)
        if action == "stop" and n:
            messages.success(request, f"Logged {n} min.")
    return _after_change(request, t)


SNOOZE_PRESETS = [("1h", "1 hour"), ("4h", "4 hours"), ("tomorrow", "Tomorrow 8 AM"), ("monday", "Next Monday 8 AM")]


@login_required
@require_POST
def ticket_snooze(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    choice, now = request.POST.get("until", ""), timezone.localtime()
    at8 = lambda d: timezone.make_aware(datetime.combine(d, time(8, 0)))  # noqa: E731
    until = {"1h": now + timedelta(hours=1), "4h": now + timedelta(hours=4), "tomorrow": at8(now.date() + timedelta(days=1)),
             "monday": at8(now.date() + timedelta(days=(7 - now.weekday()) or 7)), "wake": None}.get(choice, "bad")
    if until == "bad":
        try:
            until = timezone.make_aware(datetime.fromisoformat(choice))
        except ValueError:
            messages.error(request, "Pick when to bring it back.")
            return _after_change(request, t)
    services.snooze(t, user=request.user, until=until, request=request)
    return _after_change(request, t)


@login_required
@require_POST
def ticket_merge(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    target = Ticket.objects.filter(number__iexact=request.POST.get("into", "").strip().lstrip("#"), merged_into__isnull=True).first()
    if target is None or target.pk == t.pk:
        messages.error(request, "No other open ticket with that number.")
        return _after_change(request, t)
    services.merge(t, target, user=request.user, request=request)
    messages.success(request, f"Merged into {target.number}.")
    r = HttpResponse(status=204)
    r["HX-Redirect"] = f"/tickets/{target.pk}/"
    return r if request.headers.get("HX-Request") else redirect(f"/tickets/{target.pk}/")


@login_required
@require_POST
def ticket_resolve(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    note = request.POST.get("resolution", "").strip()[:5000]
    if not note:
        messages.error(request, "Add a short resolution note.")
        return _after_change(request, t)
    try:
        services.update_ticket(t, user=request.user, request=request, status="Resolved", resolution=note)
    except SignoffRequired:
        return _after_change(request, t, signoff_needed=True)
    return _after_change(request, t)


@login_required
@require_POST
def bulk(request):
    _need(request, "edit")
    ids = [int(i) for i in request.POST.getlist("ids") if i.isdigit()][:200]
    action, value = request.POST.get("action"), request.POST.get("value", "")

    def apply(t):
        if action == "assign":
            user = None if value == "" else User.objects.filter(pk=_int(value) or 0, is_active=True).first()
            services.update_ticket(t, user=request.user, request=request, assigned_to=user)
        elif action == "status" and value in STATUSES:
            services.update_ticket(t, user=request.user, request=request, status=value)
        elif action == "queue":
            services.update_ticket(t, user=request.user, request=request, queue=Queue.objects.filter(pk=_int(value) or 0).first())
        elif action == "close":
            services.update_ticket(t, user=request.user, request=request, status="Closed")
        else:
            return False
        return True

    n, held = 0, []
    for t in Ticket.objects.filter(pk__in=ids):
        try:
            n += apply(t)
        except SignoffRequired:
            held.append(t.number)
    messages.success(request, f"Updated {n} ticket{'s' if n != 1 else ''}.")
    if held:
        messages.error(request, f"Not closed (break/fix, customer sign-off needed first): {', '.join(held)}.")
    r = HttpResponse(status=204)
    r["HX-Refresh"] = "true"
    return r


@login_required
@require_POST
def switch_ui(request):
    ui = request.POST.get("ui")
    if ui in ("classic", "grid"):
        User.objects.filter(pk=request.user.pk).update(tickets_ui=ui)
    return redirect("/tickets/")


# ── new ticket ──
class NewTicketForm(forms.Form):
    """Same fields and order as the old Weststar One "New ticket" box."""
    client = forms.ModelChoiceField(Client.objects.none(), required=False, widget=forms.Select(attrs={"class": "select", "size": "1"}))
    subject = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "input", "placeholder": "Brief description of the issue"}))
    details = forms.CharField(required=False, max_length=50000, widget=forms.Textarea(attrs={"class": "textarea", "rows": 4, "placeholder": "What is happening, what was tried…"}))
    priority = forms.ChoiceField(choices=[(p, p) for p in PRIORITIES], initial="Low", widget=forms.Select(attrs={"class": "select"}))
    queue = forms.ModelChoiceField(Queue.objects.none(), required=False, empty_label="Auto — trigger words / AI", widget=forms.Select(attrs={"class": "select"}))
    assigned_to = forms.ModelChoiceField(User.objects.none(), required=False, label="Assignee", empty_label="Unassigned", widget=forms.Select(attrs={"class": "select"}))
    contact_name = forms.CharField(required=False, max_length=150, label="Requester name", widget=forms.TextInput(attrs={"class": "input", "placeholder": "Who has the issue?", "list": "nt-contacts", "autocomplete": "off"}))
    contact_email = forms.EmailField(required=False, label="Requester email", widget=forms.EmailInput(attrs={"class": "input", "placeholder": "name@client.com"}))
    device = forms.CharField(required=False, max_length=150, widget=forms.TextInput(attrs={"class": "input", "placeholder": "PC-07, ACME-DC01…"}))
    category = forms.ChoiceField(required=False, widget=forms.Select(attrs={"class": "select"}))
    due_date = forms.DateField(required=False, label="Due date", widget=forms.DateInput(attrs={"class": "input", "type": "date"}))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["client"].queryset = Client.objects.filter(archived_at__isnull=True).order_by("name")
        self.fields["client"].empty_label = ""
        self.fields["queue"].queryset = Queue.objects.filter(active=True)
        self.fields["assigned_to"].queryset = User.objects.filter(is_active=True).order_by("name")
        self.fields["category"].choices = [("", "—")] + [(c, c) for c in categories()]

    def clean(self):
        data = super().clean()
        if not data.get("client"):
            self.add_error("client", "Pick the client.")
        # Link the requester to a saved contact when the email matches one at this client.
        data["contact"] = None
        c, em = data.get("client"), (data.get("contact_email") or "").strip().lower()
        if c and em:
            data["contact"] = Contact.objects.filter(client=c, email__iexact=em, archived_at__isnull=True).first()
        return data


@login_required
def ticket_new(request):
    _need(request, "edit")
    if request.method == "GET" and not request.headers.get("HX-Request"):
        from urllib.parse import urlencode
        return redirect("/tickets/?" + urlencode({"open_form": request.get_full_path()}))
    initial = {}
    if _int(request.GET.get("client_id")):
        initial["client"] = int(request.GET["client_id"])
    form = NewTicketForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        t = services.create_ticket(user=request.user, subject=d["subject"], details=d["details"], client=d["client"], contact=d["contact"],
                                   priority=d["priority"], queue=d["queue"], assigned_to=d["assigned_to"], category=d["category"] or "",
                                   contact_name=d["contact_name"], contact_email=(d["contact_email"] or "").lower(), device=d["device"],
                                   due_date=d["due_date"], request=request)
        messages.success(request, f"Created {t.number}.")
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = f"/tickets/{t.pk}/"
        return resp
    contacts = [{"n": n, "e": e, "c": c} for n, e, c in Contact.objects.filter(archived_at__isnull=True).exclude(email="")
                .order_by("name").values_list("name", "email", "client_id")]
    return render(request, "helpdesk/_new.html", {"form": form, "contacts": contacts}, status=422 if request.method == "POST" else 200)


_ = Http404


@login_required
@require_POST
def ticket_ai(request, pk):
    """AI buttons on a ticket: triage apply/dismiss/re-run, summary, draft reply."""
    from . import ai
    if not can(request.user, "tickets", "edit"):
        raise PermissionDenied
    t = get_object_or_404(Ticket.objects.select_related("client", "queue"), pk=pk)
    action = request.POST.get("action")
    try:
        if action == "draft":
            return HttpResponse(ai.draft_reply(t, request.user), content_type="text/plain; charset=utf-8")
        if action == "summary":
            ai.summarize(t, request.user)
        elif action == "triage":
            ai.run_triage(t)
        elif action == "apply":
            ai.apply_triage(t, request.user)
        elif action == "dismiss":
            Ticket.objects.filter(pk=t.pk).update(ai_triage_status="dismissed")
            ai.AiLog.objects.create(feature="triage", outcome="dismissed", ticket=t, user=request.user)
    except ai.AiError as e:
        return HttpResponse(f'<div class="banner" role="alert">{escape(str(e))}</div>', status=200 if action != "draft" else 502)
    t.refresh_from_db()
    if action == "apply":
        resp = HttpResponse("")
        resp["HX-Refresh"] = "true"
        return resp
    return render(request, "helpdesk/_ai.html", {"t": t, "ai_on": True})


# ── customer sign-off, approvals, delete (from the old classic ticket page) ──
@login_required
def ticket_signoff(request, pk):
    """Full-screen page for the tech's phone or tablet: the customer signs for completed work or a drop-off."""
    from . import signoff as so
    _need(request, "edit")
    t = get_object_or_404(Ticket.objects.select_related("client", "contact"), pk=pk)
    kind = "dropoff" if request.GET.get("type", request.POST.get("type")) == "dropoff" else "completion"
    error = ""
    if request.method == "POST":
        data = {k: request.POST.get(k, "") for k in ("signer_name", "signer_title", "signer_email", "signature", "summary", "items",
                                                     "hours", "parts_desc", "parts_amount", "override_reason")}
        data["type"], data["override"] = kind, request.POST.get("override") == "1"
        rec, error = so.record(t, data, request.user, ip=request.META.get("REMOTE_ADDR", ""))
        if rec:
            close = kind == "completion" and request.POST.get("close") == "1"
            if close and t.status not in ("Resolved", "Closed"):
                services.update_ticket(t, user=request.user, request=request, status="Resolved",
                                       resolution=t.resolution or (data["summary"] or "Completed and signed off by the customer"))
            what = "Drop-off" if kind == "dropoff" else "Completion"
            messages.success(request, f"{what} sign-off overridden and noted on the ticket." if rec.overridden else
                             f"{what} signed by the customer." + (" A copy was emailed to them." if (rec.signer_email or t.contact_email) else ""))
            return redirect(f"/tickets/{t.pk}/?classic=1")
    ch = so.charges(t)
    summary = t.resolution or (t.messages.filter(kind__in=["work", "reply"], author__isnull=False).order_by("-created_at").values_list("body", flat=True).first() or "")[:1000]
    return render(request, "helpdesk/signoff.html", {
        "t": t, "kind": kind, "ch": ch, "breakfix": so.is_breakfix(t.client), "error": error, "post": request.POST,
        "summary": summary, "signer_name": t.contact.name if t.contact else t.contact_name, "signer_email": t.contact.email if t.contact else t.contact_email,
        "signer_title": t.contact.title if t.contact else "", "history": t.signoffs.select_related("user"),
        "company": Setting.get("company.name", "") or "Weststar MSP"}, status=422 if error else 200)


@login_required
@require_POST
def ticket_approval(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    if request.POST.get("delete"):
        a = TicketApproval.objects.filter(ticket=t, pk=_int(request.POST["delete"]) or 0).first()
        if a:
            a.delete()
            audit(request, "delete", "ticket", t.pk, f"{t.number}: removed a scope/budget approval", area="tickets")
            messages.success(request, "Approval removed.")
        return redirect(f"/tickets/{t.pk}/?classic=1")
    desc = request.POST.get("description", "").strip()[:500]
    if not desc:
        messages.error(request, "Describe what the client approved.")
        return redirect(f"/tickets/{t.pk}/?classic=1")
    via = request.POST.get("via", "email") if request.POST.get("via") in dict(TicketApproval.VIA) else "email"
    TicketApproval.objects.create(ticket=t, description=desc, approved_by=request.POST.get("approved_by", "").strip()[:200], via=via, user=request.user)
    services.event(t, f"✅ Scope/budget approval logged: {desc}", request.user)
    audit(request, "create", "ticket", t.pk, f"{t.number}: scope/budget approval logged", area="tickets")
    messages.success(request, "Approval logged.")
    return redirect(f"/tickets/{t.pk}/?classic=1")


@login_required
@require_POST
def ticket_delete(request, pk):
    """Admins only, like the old app. Messages, time and files go with it."""
    if request.user.role != "admin":
        raise PermissionDenied
    t = get_object_or_404(Ticket, pk=pk)
    if request.POST.get("confirm") != t.number:
        messages.error(request, f"Type {t.number} to confirm the delete.")
        return redirect(f"/tickets/{t.pk}/?classic=1")
    number = t.number
    for u in t.uploads.all():
        u.file.delete(save=False)
        u.delete()
    t.delete()
    audit(request, "delete", "ticket", pk, f"Deleted ticket {number}", area="tickets")
    messages.success(request, f"Deleted {number}.")
    return redirect("/tickets/")
