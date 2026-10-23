from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.core.permissions import can
from apps.crm.models import Client, Contact

from . import services
from .models import OPEN_STATUSES, PAUSED_STATUSES, PRIORITIES, STATUSES, Ticket

FILTERS = [("open", "Open"), ("unassigned", "Unassigned"), ("risk", "SLA at risk"), ("closed", "Closed"), ("all", "All")]


def _filter_q(name: str):
    soon = timezone.now() + timedelta(hours=1)
    return {
        "open": Q(status__in=OPEN_STATUSES),
        "unassigned": Q(status__in=OPEN_STATUSES, assigned_to__isnull=True),
        "risk": Q(status__in=[s for s in OPEN_STATUSES if s not in PAUSED_STATUSES], first_response_at__isnull=True, response_due_at__lt=soon),
        "closed": ~Q(status__in=OPEN_STATUSES),
        "all": Q(),
    }[name]


def _need(request, level="view"):
    if not can(request.user, "tickets", level):
        raise PermissionDenied


@login_required
def tickets(request, pk=None):
    _need(request)
    view = request.GET.get("view") or request.session.get("tickets_view", "inbox")
    if view not in ("inbox", "board", "queue"):
        view = "inbox"
    request.session["tickets_view"] = view
    flt = request.GET.get("filter", "open")
    if flt not in dict(FILTERS):
        flt = "open"
    q = request.GET.get("q", "").strip()[:200]
    base = Ticket.objects.select_related("client", "assigned_to")
    if view == "queue":
        base = base.filter(assigned_to=request.user)
    if q:
        base = base.filter(Q(subject__icontains=q) | Q(number__icontains=q) | Q(contact_name__icontains=q) | Q(client__name__icontains=q))
    ctx = {"view": view, "filter": flt, "q": q, "filters": [(k, label, base.filter(_filter_q(k)).count()) for k, label in FILTERS]}
    if view == "board":
        cols = [("New", ["New"]), ("Open", ["Open", "Scheduled"]), ("Waiting", PAUSED_STATUSES), ("Done", ["Resolved", "Closed"])]
        ctx["columns"] = [(name, list(base.filter(status__in=sts).order_by("-updated_at")[: 25 if name == "Done" else 300])) for name, sts in cols]
        return render(request, "helpdesk/board.html", ctx)
    from django.db.models import Case, IntegerField, Value, When
    order = Case(*[When(priority=p, then=Value(i)) for i, p in enumerate(PRIORITIES)], output_field=IntegerField())
    closed_last = Case(When(status__in=OPEN_STATUSES, then=Value(0)), default=Value(1), output_field=IntegerField())
    rows = list(base.filter(_filter_q(flt)).annotate(_p=order, _c=closed_last).order_by("_c", "_p", "-updated_at")[:200])
    selected = get_object_or_404(Ticket, pk=pk) if pk else (rows[0] if rows else None)
    ctx.update({"rows": rows, "selected": selected})
    if selected:
        ctx.update(_pane_ctx(request, selected))
    return render(request, "helpdesk/tickets.html", ctx)


def _pane_ctx(request, t: Ticket) -> dict:
    t = Ticket.objects.select_related("client", "assigned_to", "contact").get(pk=t.pk)
    minutes = t.time_entries.aggregate(m=Sum("minutes"))["m"] or 0
    uploads = list(t.uploads.order_by("created_at"))
    return {
        "t": t, "messages_list": t.messages.select_related("author").all(), "minutes": minutes,
        "users": User.objects.filter(is_active=True).order_by("name"), "statuses": STATUSES, "priorities": PRIORITIES,
        "can_edit": can(request.user, "tickets", "edit"),
        "uploads": uploads, "loose_uploads": [u for u in uploads if not u.message_id],
    }


@login_required
def ticket_pane(request, pk):
    _need(request)
    t = get_object_or_404(Ticket, pk=pk)
    return render(request, "helpdesk/_pane.html", _pane_ctx(request, t))


def _pane_response(request, t):
    resp = render(request, "helpdesk/_pane.html", _pane_ctx(request, t))
    resp["HX-Trigger"] = "ticketsChanged"
    return resp


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
        if v == "me":
            changes["assigned_to"] = request.user
        elif v == "":
            changes["assigned_to"] = None
        else:
            changes["assigned_to"] = get_object_or_404(User, pk=v, is_active=True)
    services.update_ticket(t, user=request.user, request=request, **changes)
    return _pane_response(request, t)


@login_required
@require_POST
def ticket_message(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    body = request.POST.get("body", "").strip()[:50000]
    kind = "note" if request.POST.get("kind") == "note" else "reply"
    try:
        minutes = max(0, min(int(request.POST.get("minutes") or 0), 1440))
    except ValueError:
        minutes = 0
    files = request.FILES.getlist("files")
    if not body and files:
        body = "Attached " + ", ".join(f.name for f in files[:5]) + ("…" if len(files) > 5 else "")
    problem = ""
    if body:
        msg = services.add_message(t, user=request.user, kind=kind, body=body, minutes=minutes, request=request)
        if files:
            from django.core.exceptions import ValidationError

            from apps.files.services import save_uploads
            try:
                save_uploads(request, files, kind="ticket", ticket=t, message=msg)
            except ValidationError as e:
                problem = " ".join(e.messages)
    resp = _pane_response(request, t)
    if problem:
        messages.error(request, problem)
        resp = render(request, "helpdesk/_pane.html", {**_pane_ctx(request, t), "upload_error": problem})
        resp["HX-Trigger"] = "ticketsChanged"
    return resp


@login_required
@require_POST
def ticket_time(request, pk):
    _need(request, "edit")
    t = get_object_or_404(Ticket, pk=pk)
    try:
        minutes = max(1, min(int(request.POST.get("minutes") or 15), 1440))
    except ValueError:
        minutes = 15
    services.log_time(t, user=request.user, minutes=minutes, billable=request.POST.get("billable", "1") == "1", request=request)
    return _pane_response(request, t)


class NewTicketForm(forms.Form):
    subject = forms.CharField(max_length=255, widget=forms.TextInput(attrs={"class": "input", "autofocus": True, "placeholder": "What's going on?"}))
    client = forms.ModelChoiceField(Client.objects.none(), required=False, widget=forms.Select(attrs={"class": "select"}))
    contact = forms.ModelChoiceField(Contact.objects.none(), required=False, widget=forms.Select(attrs={"class": "select"}))
    priority = forms.ChoiceField(choices=[(p, p) for p in PRIORITIES], initial="Medium", widget=forms.Select(attrs={"class": "select"}))
    details = forms.CharField(required=False, max_length=50000, widget=forms.Textarea(attrs={"class": "textarea", "rows": 4}))

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self.fields["client"].queryset = Client.objects.filter(archived_at__isnull=True).order_by("name")
        self.fields["contact"].queryset = Contact.objects.filter(archived_at__isnull=True).select_related("client").order_by("name")
        self.fields["contact"].label_from_instance = lambda c: f"{c.name} — {c.client.name}"

    def clean(self):
        data = super().clean()
        c, k = data.get("client"), data.get("contact")
        if k and not c:
            data["client"] = k.client
        elif k and c and k.client_id != c.pk:
            self.add_error("contact", "That contact belongs to a different client.")
        return data


@login_required
def ticket_new(request):
    _need(request, "edit")
    initial = {}
    if request.GET.get("client_id", "").isdigit():
        initial["client"] = int(request.GET["client_id"])
    form = NewTicketForm(request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        d = form.cleaned_data
        t = services.create_ticket(user=request.user, subject=d["subject"], details=d["details"], client=d["client"], contact=d["contact"], priority=d["priority"], request=request)
        messages.success(request, f"Created {t.number}.")
        resp = HttpResponse(status=204)
        resp["HX-Redirect"] = f"/tickets/{t.pk}/"
        return resp
    return render(request, "helpdesk/_new.html", {"form": form}, status=422 if request.method == "POST" else 200)


_ = redirect
