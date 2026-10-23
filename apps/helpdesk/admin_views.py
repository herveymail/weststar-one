"""Settings › Helpdesk queues."""
import re

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render

from apps.core.audit import audit
from apps.core.permissions import can

from .models import Queue, Ticket

FIELDS = ("name", "description", "portal_label", "keywords", "color")


def queues_page(request):
    if request.method == "POST":
        if not can(request.user, "admin", "manage"):
            raise PermissionDenied
        action = request.POST.get("action")
        q = Queue.objects.filter(pk=request.POST.get("id") or 0).first()
        if action == "delete" and q:
            if Ticket.objects.filter(queue=q).exists():
                q.active = False
                q.save(update_fields=["active"])
                messages.success(request, f"{q.name} has tickets, so it was turned off instead of deleted.")
            else:
                q.delete()
                messages.success(request, "Queue deleted.")
            return redirect(request.path)
        q = q or Queue()
        data = {f: request.POST.get(f, "").strip() for f in FIELDS}
        if not data["name"]:
            messages.error(request, "A queue needs a name.")
            return redirect(request.path)
        if Queue.objects.filter(name__iexact=data["name"]).exclude(pk=q.pk).exists():
            messages.error(request, f"There's already a queue called {data['name']}.")
            return redirect(request.path)
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", data["color"]):
            data["color"] = "#2c5cc5"
        for k, v in data.items():
            setattr(q, k, v[:255] if k != "keywords" else v[:5000])
        q.sla_enabled = request.POST.get("sla_enabled") == "on"
        q.active = request.POST.get("active", "on") == "on"
        q.sort = int(request.POST.get("sort") or 0) if (request.POST.get("sort") or "0").isdigit() else 0
        q.escalate_to = Queue.objects.filter(pk=request.POST.get("escalate_to") or 0).exclude(pk=q.pk or 0).first()
        q.is_default = request.POST.get("is_default") == "on"
        q.save()
        if q.is_default:
            Queue.objects.exclude(pk=q.pk).update(is_default=False)
        audit(request, "settings", "queue", q.pk, f"Saved queue {q.name}", area="admin")
        messages.success(request, f"Saved {q.name}.")
        return redirect(request.path)
    rows = list(Queue.objects.all())
    from django.db.models import Count, Q

    from .models import OPEN_STATUSES
    open_counts = dict(Ticket.objects.filter(status__in=OPEN_STATUSES).values("queue").annotate(n=Count("id")).values_list("queue", "n"))
    for r in rows:
        r.open = open_counts.get(r.pk, 0)
    _ = Q
    return render(request, "helpdesk/queues.html", {"rows": rows, "can_manage": can(request.user, "admin", "manage")})
