from datetime import timedelta
from decimal import Decimal

from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Count, Q, Sum
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .audit import audit
from .forms import build_form_class, build_line_formset, encrypted_fields
from .models import Counter, get_secret
from .permissions import can
from .registry import NAV, REGISTRY, Module
from .ui import cell, field_label


def module_or_404(slug: str) -> Module:
    m = REGISTRY.get(slug)
    if m is None:
        raise Http404("No such page")
    return m


def guard(request, m: Module, need: str) -> None:
    if m.owner_scoped and need in ("view", "edit"):
        return  # everyone can see/add their own; scoped() below limits the rows
    if not can(request.user, m.area, need):
        raise PermissionDenied


def is_manager(user, m: Module) -> bool:
    return can(user, m.area, "manage")


def scoped(request, m: Module):
    qs = m.model.objects.all()
    if m.owner_scoped and not is_manager(request.user, m):
        qs = qs.filter(user=request.user)
    return qs


def refresh() -> HttpResponse:
    r = HttpResponse(status=204)
    r["HX-Refresh"] = "true"
    return r


@login_required
def module_list(request, slug, embedded_filter=None, template="core/module_list.html", extra=None):
    m = module_or_404(slug)
    guard(request, m, "view")
    qs = scoped(request, m)
    archived = request.GET.get("archived") == "1" and is_manager(request.user, m)
    qs = qs.filter(archived_at__isnull=not archived)
    if embedded_filter:
        qs = qs.filter(**embedded_filter)
    counts, status = {}, request.GET.get("status", "")
    if m.status_field:
        counts = {r[m.status_field]: r["n"] for r in qs.values(m.status_field).annotate(n=Count("id"))}
        valid = [c[0] for c in m.model._meta.get_field(m.status_field).choices]
        if status in valid:
            qs = qs.filter(**{m.status_field: status})
    q = request.GET.get("q", "").strip()[:200]
    if q and m.search_fields:
        cond = Q()
        for f in m.search_fields:
            cond |= Q(**{f"{f}__icontains": q})
        qs = qs.filter(cond)
    sortable = set(m.list_fields)
    sort = request.GET.get("sort", "")
    if sort.lstrip("-") in sortable:
        qs = qs.order_by(sort, "-id")
    else:
        qs = qs.order_by(*m.ordering)
    related = [f for f in m.list_fields if m.model._meta.get_field(f).is_relation]
    qs = qs.select_related(*related)
    page = Paginator(qs, 50 if not embedded_filter else 25).get_page(request.GET.get("page"))
    rows = [{"obj": o, "cells": [cell(o, f) for f in m.list_fields]} for o in page.object_list]
    ctx = {
        "m": m, "rows": rows, "page": page, "q": q, "status": status, "archived": archived, "sort": sort,
        "columns": [(f, field_label(m.model, f)) for f in m.list_fields],
        "statuses": [(c[0], counts.get(c[0], 0)) for c in m.model._meta.get_field(m.status_field).choices] if m.status_field else [],
        "all_count": sum(counts.values()) if counts else None,
        "can_add": can(request.user, m.area, "edit") or m.owner_scoped,
        "can_manage": is_manager(request.user, m),
        "embedded": bool(embedded_filter),
        "filter_qs": "&".join(f"{k}={v}" for k, v in (embedded_filter or {}).items()),
    }
    if extra:
        ctx.update(extra)
    return render(request, template, ctx)


def _defaults_from_query(request, m: Module) -> dict:
    """Pre-fill e.g. client=12 when adding from a client page."""
    initial = {}
    for key, value in request.GET.items():
        if key.endswith("_id") and value.isdigit():
            name = key[:-3]
            try:
                if m.model._meta.get_field(name).is_relation:
                    initial[name] = int(value)
            except Exception:  # noqa: BLE001
                pass
    return initial


@login_required
def module_edit(request, slug, pk=None):
    m = module_or_404(slug)
    if m.hidden and slug not in ("contacts", "assets", "networks", "client_notes", "employees", "pto", "timeclock"):
        raise Http404
    guard(request, m, "edit")
    obj = get_object_or_404(scoped(request, m), pk=pk) if pk else None
    manager = is_manager(request.user, m)
    # Private records (time off, timeclock): once approved, only H/R can change them.
    if obj and m.owner_scoped and not manager and m.owner_initial_status and getattr(obj, m.status_field) != m.owner_initial_status:
        locked = True
    else:
        locked = False
    if obj and obj.archived_at:
        locked = True
    FormClass = build_form_class(m, request.user)
    Lines = build_line_formset(m)
    if request.method == "POST":
        if locked:
            raise PermissionDenied
        form = FormClass(request.POST, instance=obj, initial=_defaults_from_query(request, m))
        lines = Lines(request.POST, instance=obj or m.model(), prefix="lines") if Lines else None
        if form.is_valid() and (lines is None or lines.is_valid()):
            with transaction.atomic():
                before = {f: getattr(obj, f) for f in form.changed_data} if obj else {}
                new = form.save(commit=False)
                if not obj:
                    new.created_by = request.user
                    if m.owner_scoped:
                        new.user = request.user
                    if m.number:
                        from .numbering import next_number
                        setattr(new, m.number[0], next_number(slug.rstrip("s")))
                new.save()
                if lines is not None:
                    lines.instance = new
                    lines.save()
                    new.recalc()
                secrets = set(encrypted_fields(m.model))
                changes = {f: {"from": None if f in secrets else _plain(before.get(f)), "to": "[changed]" if f in secrets else _plain(form.cleaned_data.get(f))} for f in form.changed_data}
                audit(request, "update" if obj else "create", slug, new.pk, f"{'Updated' if obj else 'Created'} {m.singular.lower()} {new}", changes=changes, area=m.area)
            return refresh()
        status = 422
    else:
        form = FormClass(instance=obj, initial=_defaults_from_query(request, m))
        lines = Lines(instance=obj or m.model(), prefix="lines") if Lines else None
        status = 200
    return render(request, "core/module_form.html", {
        "m": m, "obj": obj, "form": form, "lines": lines, "locked": locked,
        "can_manage": manager, "readonly_values": _readonly(obj, m) if obj else [],
        "can_reveal": obj is not None and can(request.user, m.area, "manage" if m.area == "hr" else "edit"),
    }, status=status)


def _plain(v):
    if v is None or isinstance(v, (str, int, float, bool)):
        return v
    if isinstance(v, Decimal):
        return str(v)
    return str(v)


def _readonly(obj, m: Module):
    out = []
    for f in obj._meta.get_fields():
        if f.concrete and not getattr(f, "editable", True) and f.name in ("number", "subtotal", "tax_amount", "total", "views", "runs", "user"):
            if m.lines and f.name in ("subtotal", "tax_amount", "total"):
                continue  # shown under the line items
            out.append((field_label(m.model, f.name), cell(obj, f.name)))
    return out


@login_required
@require_POST
def module_archive(request, slug, pk):
    m = module_or_404(slug)
    guard(request, m, "manage")
    obj = get_object_or_404(scoped(request, m), pk=pk)
    restoring = request.POST.get("restore") == "1"
    obj.archived_at = None if restoring else timezone.now()
    obj.save(update_fields=["archived_at", "updated_at"])
    audit(request, "restore" if restoring else "archive", slug, pk, f"{'Restored' if restoring else 'Archived'} {m.singular.lower()} {obj}", area=m.area)
    return refresh()


@login_required
@require_POST
def module_reveal(request, slug, pk, field):
    """Show one encrypted value. Needs edit rights (manage for H/R), is rate limited, and always audited."""
    m = module_or_404(slug)
    if field not in encrypted_fields(m.model):
        raise Http404
    need = "manage" if m.area == "hr" else "edit"
    if not can(request.user, m.area, need):
        raise PermissionDenied
    key = f"reveal:{request.user.pk}"
    n = cache.get(key, 0)
    if n >= 30:
        return HttpResponse("Too many reveals in a short time. Wait a minute.", status=429)
    cache.set(key, n + 1, 60)
    obj = get_object_or_404(scoped(request, m), pk=pk)
    audit(request, "reveal", slug, pk, f"Viewed {field_label(m.model, field)} on {obj}", area=m.area)
    try:
        value = get_secret(obj, field)
    except Exception:  # noqa: BLE001
        value = "(could not decrypt — check APP_ENCRYPTION_KEY)"
    return render(request, "core/_revealed.html", {"value": value})


@login_required
def dashboard(request):
    from apps.billing.models import Invoice
    from apps.helpdesk.models import OPEN_STATUSES, Ticket
    from apps.tools.models import BackupJob, Domain

    u = request.user
    ctx = {}
    soon = timezone.now() + timedelta(hours=1)
    if can(u, "tickets"):
        open_q = Ticket.objects.filter(status__in=OPEN_STATUSES)
        risk = open_q.filter(status__in=["New", "Open", "Scheduled"], first_response_at__isnull=True, response_due_at__lt=soon)
        ctx["tickets"] = {"open": open_q.count(), "mine": open_q.filter(assigned_to=u).count(), "unassigned": open_q.filter(assigned_to__isnull=True).count(), "risk": risk.count()}
        ctx["attention"] = open_q.filter(Q(priority="Critical") | Q(response_due_at__lt=soon, first_response_at__isnull=True)).order_by("response_due_at")[:8]
    if can(u, "billing"):
        unpaid = Invoice.objects.filter(archived_at__isnull=True, status__in=["Sent", "Viewed", "Partial", "Overdue"])
        agg = unpaid.aggregate(total=Sum("total"), paid=Sum("amount_paid"))
        ctx["billing"] = {"unpaid": unpaid.count(), "amount": (agg["total"] or 0) - (agg["paid"] or 0), "overdue": unpaid.filter(due_date__lt=timezone.localdate()).count()}
    if can(u, "tools"):
        today = timezone.localdate()
        ctx["tools"] = {
            "backup_failures": BackupJob.objects.filter(archived_at__isnull=True, last_result="Failed").count(),
            "domains_expiring": Domain.objects.filter(archived_at__isnull=True, expires_on__gte=today, expires_on__lt=today + timedelta(days=30)).count(),
        }
    hour = timezone.localtime().hour
    ctx["greeting"] = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    return render(request, "core/dashboard.html", ctx)


@login_required
def jump(request):
    """Top-bar search: pages, clients and tickets as you type."""
    from apps.crm.models import Client
    from apps.helpdesk.models import Ticket

    q = request.GET.get("q", "").strip()[:100]
    if not q:
        return HttpResponse("")
    ql = q.lower()
    pages = []
    for group, _short, _icon, items in NAV:
        for item_id, label, url, area in items:
            if (area == "*" or can(request.user, area)) and (ql in label.lower() or (group and ql in group.lower())):
                pages.append({"label": label, "url": url, "icon": item_id, "group": group or ""})
    clients = list(Client.objects.filter(archived_at__isnull=True, name__icontains=q)[:4]) if can(request.user, "clients") and len(q) >= 2 else []
    tickets = list(Ticket.objects.filter(Q(subject__icontains=q) | Q(number__icontains=q))[:5]) if can(request.user, "tickets") and len(q) >= 2 else []
    return render(request, "core/_jump.html", {"pages": pages[:6], "clients": clients, "tickets": tickets})


def health(request):
    return HttpResponse("ok", content_type="text/plain")


def forbidden(request, exception=None):
    return render(request, "core/403.html", status=403)


def not_found(request, exception=None):
    return render(request, "core/404.html", status=404)
