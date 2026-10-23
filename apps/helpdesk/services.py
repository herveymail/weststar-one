"""Ticket rules in one place, used by the screens, the importer and the background jobs."""
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.core.audit import audit
from apps.core.models import Setting

from .models import DEFAULT_RESPONSE_MINUTES, OPEN_STATUSES, Ticket, TicketMessage, TimeEntry


def response_minutes(priority: str, client) -> int:
    minutes = DEFAULT_RESPONSE_MINUTES[priority]
    try:
        custom = int(Setting.get(f"tickets.sla_{priority.lower()}_min", "0"))
        if custom > 0:
            minutes = custom
    except ValueError:
        pass
    # A client's own SLA can only tighten Critical/High.
    if client is not None and client.sla_response_hours and priority in ("Critical", "High"):
        minutes = min(minutes, client.sla_response_hours * 60)
    return minutes


def event(ticket: Ticket, text: str, user=None) -> None:
    TicketMessage.objects.create(ticket=ticket, kind="event", body=text, author=user, author_name=user.name if user else "", via="system" if user is None else "web")


@transaction.atomic
def create_ticket(*, user, subject, details="", client=None, contact=None, priority="Medium", source="Manual", assigned_to=None, request=None) -> Ticket:
    from apps.core.numbering import next_number
    number = next_number("ticket")
    t = Ticket.objects.create(
        number=number, subject=subject, details=details, client=client, contact=contact,
        contact_name=contact.name if contact else "", contact_email=contact.email if contact else "",
        priority=priority, status="New", source=source, assigned_to=assigned_to, created_by=user,
        response_due_at=timezone.now() + timedelta(minutes=response_minutes(priority, client)),
    )
    if details.strip():
        TicketMessage.objects.create(ticket=t, kind="reply", body=details, author_name=contact.name if contact else user.name, via="web")
    event(t, f"Created by {user.name}", user)
    audit(request, "create", "ticket", t.pk, f"Created ticket {number}: {subject}", area="tickets", user=user)
    return t


@transaction.atomic
def add_message(ticket: Ticket, *, user, kind: str, body: str, minutes: int = 0, request=None) -> TicketMessage:
    t = Ticket.objects.select_for_update().get(pk=ticket.pk)
    msg = TicketMessage.objects.create(ticket=t, kind=kind, body=body, author=user, author_name=user.name, via="web")
    if kind == "reply":
        if not t.first_response_at:
            t.first_response_at = timezone.now()
        if t.status == "New":
            t.status = "Open"
    if not t.assigned_to_id:
        t.assigned_to = user
        event(t, f"Assigned to {user.name}", user)
    t.save()
    if minutes:
        TimeEntry.objects.create(ticket=t, user=user, minutes=minutes, description=body[:500], work_date=timezone.localdate())
    audit(request, kind, "ticket", t.pk, f"{'Replied on' if kind == 'reply' else 'Added note to'} {t.number}", area="tickets")
    return msg


@transaction.atomic
def update_ticket(ticket: Ticket, *, user, request=None, **changes) -> Ticket:
    t = Ticket.objects.select_for_update().get(pk=ticket.pk)
    notes = []
    if "priority" in changes and changes["priority"] != t.priority:
        notes.append(f"Priority {t.priority} → {changes['priority']}")
        t.priority = changes["priority"]
        if not t.first_response_at:
            t.response_due_at = t.created_at + timedelta(minutes=response_minutes(t.priority, t.client))
    if "assigned_to" in changes and changes["assigned_to"] != t.assigned_to:
        a = changes["assigned_to"]
        notes.append(f"Assigned to {a.name}" if a else "Unassigned")
        t.assigned_to = a
    if "status" in changes and changes["status"] != t.status:
        new = changes["status"]
        notes.append(f"Status {t.status} → {new}")
        t.status = new
        if new == "Resolved":
            t.resolved_at = timezone.now()
        if new == "Closed":
            t.closed_at = timezone.now()
            t.resolved_at = t.resolved_at or timezone.now()
        if new in OPEN_STATUSES:
            t.closed_at = t.resolved_at = None
    t.save()
    for n in notes:
        event(t, f"{n} by {user.name}", user)
    if notes:
        audit(request, "update", "ticket", t.pk, f"{t.number}: {'; '.join(notes)}", area="tickets")
    return t


@transaction.atomic
def log_time(ticket: Ticket, *, user, minutes: int, work_type="Remote", billable=True, description="", request=None) -> TimeEntry:
    e = TimeEntry.objects.create(ticket=ticket, user=user, minutes=minutes, work_type=work_type, billable=billable, description=description, work_date=timezone.localdate())
    event(ticket, f"{user.name} logged {minutes} min{' · billable' if billable else ''}", user)
    Ticket.objects.filter(pk=ticket.pk).update(updated_at=timezone.now())
    audit(request, "time", "ticket", ticket.pk, f"Logged {minutes} min on {ticket.number}", area="tickets")
    return e
