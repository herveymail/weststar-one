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
from .settings_catalog import SETTINGS, field_specs, find


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
    return render(request, "core/settings_home.html", {"groups": groups, "q": q})


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
    if target == "import":
        from apps.legacy.models import ImportRun
        return render(request, "core/import_help.html", {"runs": ImportRun.objects.order_by("-started_at")[:20]})
    fields = field_specs(item)
    if request.method == "POST":
        if not can(request.user, "admin", "manage"):
            raise PermissionDenied
        errors, changed = [], []
        for f in fields:
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
    stored = {s.key: s for s in Setting.objects.filter(key__in=[f["key"] for f in fields])}
    for f in fields:
        row = stored.get(f["key"])
        f = dict(f)
        if f["type"] == "secret":
            f["is_set"] = bool(row and row.value)
            f["value"] = ""
        else:
            f["value"] = row.value if row else ""
        values.append(f)
    return render(request, "core/settings_page.html", {"group": group, "item": item, "fields": values, "can_manage": can(request.user, "admin", "manage")})


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
