from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import F, Sum
from django.shortcuts import get_object_or_404, render

from apps.core.permissions import can
from apps.core.views import module_list

from .models import Client

# Same tabs as the old client page. (label, module slug or None)
TABS = [
    ("Overview", None), ("Contacts", "contacts"), ("Tickets", None), ("Assets", "assets"), ("Network", "networks"),
    ("Contracts", "contracts"), ("Invoices", "invoices"), ("Quotes", "quotes"), ("Projects", "projects"), ("Notes", "client_notes"),
    ("Domains", "domains"), ("Policies", "policies"), ("Training", "training"), ("Backups", None), ("Files", None), ("Checklists", None), ("Portal", None),
]


@login_required
def clients(request):
    return module_list(request, "clients", extra={"row_url": "/clients/{id}/"})


@login_required
def client_detail(request, pk):
    if not can(request.user, "clients"):
        raise PermissionDenied
    from apps.core.registry import REGISTRY

    client = get_object_or_404(Client, pk=pk)
    tabs = [(label, slug) for label, slug in TABS if slug is None or can(request.user, REGISTRY[slug].area)]
    tab = request.GET.get("tab", "Overview")
    if tab not in [t[0] for t in tabs]:
        tab = "Overview"
    slug = dict(tabs).get(tab)
    if slug and request.headers.get("HX-Request"):
        return module_list(request, slug, embedded_filter={"client_id": client.pk}, template="core/_module_table.html")
    from apps.core.ui import cell, field_label

    ctx = {"c": client, "tabs": tabs, "tab": tab, "slug": slug, "can_edit_client": can(request.user, "clients", "edit"), "tickets": None,
           "account": [(field_label(Client, f), cell(client, f)) for f in ["phone", "email", "website", "city", "state", "account_manager", "hourly_rate", "net_terms", "sla_response_hours", "sla_resolution_hours"]]}
    if can(request.user, "tickets"):
        ctx["tickets"] = client.tickets.select_related("assigned_to").order_by("-updated_at")[:20]
        ctx["open_tickets"] = client.tickets.filter(status__in=["New", "Open", "Waiting on client", "Waiting on vendor", "Scheduled"]).count()
    if can(request.user, "billing"):
        owed = client.invoices.filter(archived_at__isnull=True, status__in=["Sent", "Viewed", "Partial", "Overdue"]).aggregate(s=Sum(F("total")), p=Sum("amount_paid"))
        ctx["balance"] = (owed["s"] or 0) - (owed["p"] or 0)
    if tab == "Invoices" and can(request.user, "billing"):
        from apps.billing import stripe_api
        from apps.billing.models import Invoice
        from apps.billing.payments import _billing_people
        ctx.update(open_invoices=Invoice.objects.filter(client=client, archived_at__isnull=True, status__in=["Sent", "Viewed", "Partial", "Overdue"]).order_by("due_date"),
                   stripe_ok=stripe_api.configured(), can_billing_edit=can(request.user, "billing", "edit"), billing_to=", ".join(_billing_people(client)),
                   recent_payments=client.payments.filter(archived_at__isnull=True).select_related("invoice")[:5])
    if tab == "Backups":
        from apps.integrations import msp360
        ctx["backups"] = msp360.for_client(client)
    return render(request, "crm/client_detail.html", ctx)
