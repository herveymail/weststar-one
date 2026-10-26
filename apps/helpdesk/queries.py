"""Ticket list filters shared by the classic list and the grid (same views as the old Weststar One)."""
from datetime import timedelta

from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.utils import timezone

from .models import DONE_STATUSES, OPEN_STATUSES, PAUSED_STATUSES, PRIORITIES, Ticket

WAITING = [*PAUSED_STATUSES, "Scheduled"]


def not_snoozed():
    return Q(snoozed_until__isnull=True) | Q(snoozed_until__lte=timezone.now())


# Classic left rail: (key, label, filter)
def classic_views(user):
    unresolved = Q(status__in=OPEN_STATUSES) & not_snoozed()
    return [
        ("unresolved", "All unresolved", unresolved),
        ("mine", "My open", unresolved & Q(assigned_to=user)),
        ("unassigned", "Unassigned", unresolved & Q(assigned_to__isnull=True)),
        ("open", "Open", Q(status__in=["New", "Open"]) & not_snoozed()),
        ("progress", "In progress", Q(status="In progress") & not_snoozed()),
        ("waiting", "Waiting", Q(status__in=WAITING) & not_snoozed()),
        ("critical", "Critical", unresolved & Q(priority="Critical")),
        ("snoozed", "Snoozed", Q(status__in=OPEN_STATUSES, snoozed_until__gt=timezone.now())),
        ("closed", "Resolved / Closed (30d)", Q(status__in=DONE_STATUSES, updated_at__gte=timezone.now() - timedelta(days=30))),
    ]


# Grid status tabs and quick views
def grid_tabs():
    return [
        ("all", "All", Q()),
        ("open", "Open", Q(status__in=["New", "Open"])),
        ("progress", "In progress", Q(status="In progress")),
        ("pending", "Pending", Q(status__in=WAITING)),
        ("closed", "Closed", Q(status__in=DONE_STATUSES)),
    ]


def grid_views(user):
    now = timezone.now()
    return [
        ("mine", "My open", Q(status__in=OPEN_STATUSES, assigned_to=user)),
        ("unassigned", "Unassigned", Q(status__in=OPEN_STATUSES, assigned_to__isnull=True)),
        ("overdue", "Overdue", Q(status__in=OPEN_STATUSES) & ((Q(first_response_at__isnull=True) & Q(response_due_at__lt=now)) | Q(resolve_due_at__lt=now))),
        ("waiting", "Waiting on client", Q(status="Waiting on client")),
        ("snoozed", "Snoozed", Q(status__in=OPEN_STATUSES, snoozed_until__gt=now)),
    ]


def with_extras(qs):
    """Adds computer_name (MSP360 computer behind a backup ticket) and unread_n (client replies since staff last wrote)."""
    from django.db.models import F, OuterRef, Subquery

    from apps.integrations.models import Msp360Plan

    from .models import TicketMessage
    last_staff = (TicketMessage.objects.filter(ticket=OuterRef("pk"), author__isnull=False).exclude(kind="event")
                  .order_by("-created_at").values("created_at")[:1])
    qs = qs.annotate(computer_name=Subquery(Msp360Plan.objects.filter(ticket=OuterRef("pk")).values("computer")[:1]),
                     last_staff_at=Subquery(last_staff))
    client_reply = Q(messages__kind="reply", messages__author__isnull=True, messages__portal_user__isnull=False) | Q(messages__kind="reply", messages__author__isnull=True, messages__via="email")
    return qs.annotate(unread_n=Count("messages", filter=client_reply & (Q(last_staff_at__isnull=True) | Q(messages__created_at__gt=F("last_staff_at"))), distinct=True))


def computers():
    from apps.integrations.models import Msp360Plan
    return sorted(set(Msp360Plan.objects.filter(ticket__isnull=False).exclude(computer="").values_list("computer", flat=True)))


def search(qs, q: str):
    q = (q or "").strip()[:200]
    if not q:
        return qs
    cond = Q(subject__icontains=q) | Q(number__icontains=q) | Q(contact_name__icontains=q) | Q(contact_email__icontains=q) | Q(client__name__icontains=q)
    return qs.filter(cond)


def priority_order():
    return Case(*[When(priority=p, then=Value(i)) for i, p in enumerate(PRIORITIES)], output_field=IntegerField())


def counts(base, named_filters) -> dict:
    """One query: {key: count} for every (key, label, Q)."""
    agg = {k: Count("id", filter=f) for k, _l, f in named_filters}
    return base.aggregate(**agg) if agg else {}


def base_qs():
    return Ticket.objects.select_related("client", "assigned_to", "queue", "created_by").filter(merged_into__isnull=True)
