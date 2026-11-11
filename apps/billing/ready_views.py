"""Billing › Ready to bill (see ready.py)."""
from datetime import date

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.core import mail
from apps.core.audit import audit

from . import ready
from .models import Invoice


def _through(request):
    try:
        return date.fromisoformat(request.POST.get("through") or request.GET.get("through") or "")
    except ValueError:
        return timezone.localdate()


@login_required
def ready_page(request):
    if not can_bill(request.user, "view"):
        raise PermissionDenied
    through = _through(request)
    if request.method == "POST":
        if not can_bill(request.user, "edit"):
            raise PermissionDenied
        a = request.POST.get("action")
        if a == "create":
            ids = [int(x) for x in request.POST.getlist("client") if x.isdigit()]
            if not ids:
                messages.error(request, "Tick at least one client.")
                return redirect(f"/billing/ready/?through={through}")
            made = ready.create_drafts(ids, through, user=request.user)
            for inv in made:
                audit(request, "create", "invoice", inv.pk, f"Draft {inv.number} from Ready to bill ({inv.total})", area="billing")
            messages.success(request, f"Created {len(made)} draft invoice{'s' if len(made) != 1 else ''}. Check them, then send.")
            return redirect("/billing/ready/?made=" + ",".join(str(i.pk) for i in made))
        if a == "nocharge" and (request.POST.get("client") or "").isdigit():
            n = ready.no_charge(int(request.POST["client"]), through)
            audit(request, "update", "client", int(request.POST["client"]), f"Marked {n} unbilled item(s) no charge", area="billing")
            messages.success(request, f"Marked {n} item{'s' if n != 1 else ''} as no charge.")
            return redirect(f"/billing/ready/?through={through}")
        if a == "send":
            from .payments import _billing_people
            from .documents import default_message, default_subject
            from .views import send_doc
            sent, skipped = [], []
            for inv in Invoice.objects.filter(pk__in=[int(x) for x in request.POST.getlist("inv") if x.isdigit()], status="Draft").select_related("client"):
                to = _billing_people(inv.client)
                if not to or not inv.lines.exists():
                    skipped.append(inv.number)
                    continue
                (sent if send_doc(request, inv, "invoice", to, [], default_subject(inv, "invoice"), default_message(inv, "invoice")) else skipped).append(inv.number)
            if sent:
                messages.success(request, f"Sent {len(sent)} invoice{'s' if len(sent) != 1 else ''}: {', '.join(sent)}.")
            if skipped:
                messages.error(request, f"Not sent (no billing email or email failed): {', '.join(skipped)}. Open them to send by hand.")
            return redirect("/billing/ready/")
    made = []
    if request.GET.get("made"):
        made = list(Invoice.objects.filter(pk__in=[int(x) for x in request.GET["made"].split(",") if x.isdigit()]).select_related("client"))
    groups = ready.collect(through)
    from .payments import _billing_people
    for g in groups:
        g["emails"] = _billing_people(g["client"])
    for inv in made:
        inv.emails = _billing_people(inv.client)
    return render(request, "billing/ready.html", {
        "groups": groups, "through": through, "made": made, "can_edit": can_bill(request.user, "edit"),
        "total": sum(g["total"] for g in groups if g["preselect"]), "mail_ok": mail.configured(),
    })


def can_bill(user, level):
    from apps.core.permissions import can
    return can(user, "billing", level)
