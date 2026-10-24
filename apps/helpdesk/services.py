"""Ticket rules in one place, used by the staff screens, the client portal, the importer and the jobs."""
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.audit import audit
from apps.core.models import Setting

from .models import DEFAULT_RESPONSE_MINUTES, DONE_STATUSES, OPEN_STATUSES, Queue, Ticket, TicketMessage, TicketTimer, TimeEntry


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


def resolve_hours(priority: str, client) -> int:
    base = {"Critical": 4, "High": 8, "Medium": 24, "Low": 72}[priority]
    try:
        custom = int(Setting.get(f"tickets.resolve_{priority.lower()}_hours", "0") or 0)
        if custom > 0:
            base = custom
    except ValueError:
        pass
    if client is not None and client.sla_resolution_hours and priority in ("Critical", "High"):
        base = min(base, client.sla_resolution_hours)
    return base


def route_queue(subject: str, details: str = "") -> Queue | None:
    """Pick a queue from its trigger words (like the old app); otherwise the default queue."""
    text = f"{subject} {details}".lower()
    for q in Queue.objects.filter(active=True):
        for word in (w.strip().lower() for w in q.keywords.split(",")):
            if word and word in text:
                return q
    return Queue.objects.filter(active=True, is_default=True).first()


def event(ticket: Ticket, text: str, user=None) -> None:
    TicketMessage.objects.create(ticket=ticket, kind="event", body=text, author=user, author_name=user.name if user else "",
                                 via="system" if user is None else "web")


def portal_link(ticket: Ticket) -> str:
    return f"{settings.PORTAL_BASE}/tickets/{ticket.pk}/"


SUBJECT_DEFAULTS = {"new": "[{number}] {subject}", "reply": "Re: [{number}] {subject}", "closed": "[{number}] Resolved: {subject}"}


def email_subject(kind: str, t: Ticket) -> str:
    """Settings › Ticket emails subject lines. The ticket number must stay in it so replies find the ticket."""
    tpl = Setting.get(f"tickets.email_{kind}_subject", "") or SUBJECT_DEFAULTS[kind]
    out = tpl.replace("{number}", t.number).replace("{subject}", t.subject).replace("{company}", Setting.get("company.name") or "")
    return out if t.number in out else f"[{t.number}] {out}"


def thread_refs(t: Ticket) -> list[str]:
    """Message-IDs already in this ticket's email conversation, oldest first."""
    from .models import InboundEmail
    ids = list(InboundEmail.objects.filter(ticket=t).order_by("received_at").values_list("message_id", flat=True)[:5])
    ids += list(t.messages.exclude(email_message_id="").order_by("created_at").values_list("email_message_id", flat=True))
    return list(dict.fromkeys(ids))[-10:]


def after_hours(now=None) -> bool:
    """Outside Settings › Office hours (Opens/Closes/Open days)? False when the hours aren't set."""
    import datetime as dt
    now = timezone.localtime(now)
    try:
        tz = Setting.get("app.timezone", "")
        if tz:
            from zoneinfo import ZoneInfo
            now = now.astimezone(ZoneInfo(tz))
        opens = dt.time.fromisoformat(Setting.get("helpdesk.open", "") or "")
        closes = dt.time.fromisoformat(Setting.get("helpdesk.close", "") or "")
    except (ValueError, KeyError, ImportError):
        return False
    days = [d.strip()[:3].title() for d in (Setting.get("helpdesk.days", "") or "Mon,Tue,Wed,Thu,Fri").split(",") if d.strip()]
    return now.strftime("%a") not in days or not (opens <= now.time() < closes)


def send_ticket_email(t: Ticket, kind: str, template: str, ctx: dict, msg: TicketMessage | None = None) -> bool:
    from apps.core import mail
    if kind == "new" and Setting.get("tickets.afterhours_enabled", "") == "true" and after_hours():
        ctx = {**ctx, "after_hours": Setting.get("tickets.afterhours_message", "") or "Our office is closed right now. We'll pick this up when we open."}
    to, cc_list = _client_recipients(t)
    if not to:
        return False
    mid = mail.new_message_id(t.pk)
    ok = mail.send(to, email_subject(kind, t), template, {"t": t, "link": portal_link(t), **ctx}, cc=cc_list,
                   message_id=mid, references=thread_refs(t))
    if ok:
        if msg is not None:
            TicketMessage.objects.filter(pk=msg.pk).update(via="email", email_message_id=mid)
        else:
            TicketMessage.objects.create(ticket=t, kind="event", body=f"Emailed {', '.join(to + cc_list)}", via="system", email_message_id=mid)
    return ok


def _client_recipients(t: Ticket) -> tuple[list[str], list[str]]:
    to = [t.contact_email or (t.contact.email if t.contact_id else "")]
    cc = [a.strip() for a in (t.cc or "").replace(";", ",").split(",") if a.strip()]
    return [a for a in to if a], cc


@transaction.atomic
def create_ticket(*, user=None, subject, details="", client=None, contact=None, priority="Medium", source="Manual",
                  assigned_to=None, queue=None, category="", cc="", portal_user=None, contact_name="", contact_email="",
                  request=None) -> Ticket:
    from apps.core.numbering import next_number
    number = next_number("ticket")
    now = timezone.now()
    queue = queue or route_queue(subject, details)
    t = Ticket.objects.create(
        number=number, subject=subject, details=details, client=client, contact=contact,
        contact_name=contact_name or (contact.name if contact else (portal_user.name if portal_user else "")),
        contact_email=contact_email or (contact.email if contact else (portal_user.email if portal_user else "")),
        priority=priority, status="New", source=source, assigned_to=assigned_to, created_by=user, queue=queue,
        category=category, cc=cc,
        response_due_at=now + timedelta(minutes=response_minutes(priority, client)) if (queue is None or queue.sla_enabled) else None,
        resolve_due_at=now + timedelta(hours=resolve_hours(priority, client)) if (queue is None or queue.sla_enabled) else None,
    )
    who = user.name if user else (portal_user.name if portal_user else "someone")
    event(t, f"Created by {who}{' in the portal' if portal_user else ''}", user)
    audit(request, "create", "ticket", t.pk, f"Created ticket {number}: {subject}", area="tickets", user=user)
    from . import ai
    ai_will_answer = source in ("Email", "Portal") and ai.enabled("first_response")  # its reply includes the "we got it"
    if not ai_will_answer and (portal_user is not None or (source == "Email" and Setting.get("tickets.email_ack", "true") != "false")):
        transaction.on_commit(lambda: send_ticket_email(t, "new", "email/ticket_received", {}))
    return t


@transaction.atomic
def add_message(ticket: Ticket, *, user, kind: str, body: str, minutes: int = 0, work_type: str = "Remote",
                billable: bool = True, status_after: str = "", cc: str = "", request=None) -> TicketMessage:
    """A staff reply (emailed to the client and shown in the portal), private note, or work log."""
    t = Ticket.objects.select_for_update().get(pk=ticket.pk)
    msg = TicketMessage.objects.create(ticket=t, kind=kind, body=body, author=user, author_name=user.name, via="web", cc=cc)
    if kind == "reply":
        if not t.first_response_at:
            t.first_response_at = timezone.now()
        if t.status == "New":
            t.status = "Open"
        if cc.strip():
            t.cc = ", ".join(dict.fromkeys(a.strip() for a in f"{t.cc},{cc}".split(",") if a.strip()))
    if not t.assigned_to_id:
        t.assigned_to = user
        event(t, f"Assigned to {user.name}", user)
    t.save()
    if minutes:
        TimeEntry.objects.create(ticket=t, user=user, minutes=minutes, work_type=work_type, billable=billable,
                                 description=body[:500], work_date=timezone.localdate())
    if status_after and status_after in dict(Ticket._meta.get_field("status").choices) and status_after != t.status:
        update_ticket(t, user=user, request=request, status=status_after)
    audit(request, kind, "ticket", t.pk, f"{ {'reply': 'Replied on', 'note': 'Added note to', 'work': 'Logged work on'}.get(kind, 'Updated') } {t.number}", area="tickets")
    if kind == "reply":
        send_ticket_email(t, "reply", "email/ticket_reply", {"m": msg}, msg)
    return msg


@transaction.atomic
def client_reply(ticket: Ticket, *, portal_user=None, body: str, name: str = "", via: str = "portal", email_message_id: str = "") -> TicketMessage:
    """A reply from the client (portal or email). Reopens a recently closed ticket and wakes a snoozed one."""
    t = Ticket.objects.select_for_update().get(pk=ticket.pk)
    msg = TicketMessage.objects.create(ticket=t, kind="reply", body=body, author=None, author_name=name or (portal_user.name if portal_user else ""),
                                       portal_user=portal_user, via=via, email_message_id=email_message_id[:255])
    if t.status in ("Waiting on client",) or t.status in DONE_STATUSES:
        old = t.status
        t.status, t.closed_at, t.resolved_at = "Open", None, None
        event(t, f"{'Reopened' if old in DONE_STATUSES else 'Status Waiting on client → Open'} by the client's reply")
    t.snoozed_until = None
    t.save()
    return msg


@transaction.atomic
def update_ticket(ticket: Ticket, *, user, request=None, **changes) -> Ticket:
    t = Ticket.objects.select_for_update().get(pk=ticket.pk)
    notes = []
    if "priority" in changes and changes["priority"] != t.priority:
        notes.append(f"Priority {t.priority} → {changes['priority']}")
        t.priority = changes["priority"]
        if not t.first_response_at and t.response_due_at:
            t.response_due_at = t.created_at + timedelta(minutes=response_minutes(t.priority, t.client))
        if t.resolve_due_at:
            t.resolve_due_at = t.created_at + timedelta(hours=resolve_hours(t.priority, t.client))
    if "assigned_to" in changes and changes["assigned_to"] != t.assigned_to:
        a = changes["assigned_to"]
        notes.append(f"Assigned to {a.name}" if a else "Unassigned")
        t.assigned_to = a
    if "queue" in changes and changes["queue"] != t.queue:
        q = changes["queue"]
        notes.append(f"Moved to {q.name}" if q else "Removed from queue")
        t.queue = q
    if "category" in changes and changes["category"] != t.category:
        notes.append(f"Category: {changes['category'] or 'none'}")
        t.category = changes["category"]
    if "billable" in changes and changes["billable"] != t.billable:
        notes.append("Billable" if changes["billable"] else "Not billable")
        t.billable = changes["billable"]
    if "resolution" in changes:
        t.resolution = changes["resolution"]
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
        if new in DONE_STATUSES:
            t.snoozed_until = None
    was_done = "status" in changes and Ticket.objects.filter(pk=t.pk, status__in=DONE_STATUSES).exists()
    t.save()
    for n in notes:
        event(t, f"{n} by {user.name}", user)
    if notes:
        audit(request, "update", "ticket", t.pk, f"{t.number}: {'; '.join(notes)}", area="tickets")
    if "status" in changes and t.status in DONE_STATUSES and not was_done and Setting.get("tickets.email_on_close", "true") != "false":
        transaction.on_commit(lambda: send_ticket_email(t, "closed", "email/ticket_closed", {
            "footer": Setting.get("tickets.closed_footer", "") or "If this isn't fully fixed, just reply to this email and the ticket will reopen."}))
    return t


@transaction.atomic
def log_time(ticket: Ticket, *, user, minutes: int, work_type="Remote", billable=True, description="", request=None) -> TimeEntry:
    e = TimeEntry.objects.create(ticket=ticket, user=user, minutes=minutes, work_type=work_type, billable=billable,
                                 description=description, work_date=timezone.localdate())
    event(ticket, f"{user.name} logged {minutes} min{' · billable' if billable else ''}", user)
    Ticket.objects.filter(pk=ticket.pk).update(updated_at=timezone.now())
    audit(request, "time", "ticket", ticket.pk, f"Logged {minutes} min on {ticket.number}", area="tickets")
    return e


def start_timer(ticket: Ticket, user) -> TicketTimer:
    timer, _ = TicketTimer.objects.get_or_create(ticket=ticket, user=user)
    return timer


def stop_timer(ticket: Ticket, user, *, save=True, request=None) -> int:
    timer = TicketTimer.objects.filter(ticket=ticket, user=user).first()
    if not timer:
        return 0
    minutes = max(1, round((timezone.now() - timer.started_at).total_seconds() / 60))
    timer.delete()
    if save:
        log_time(ticket, user=user, minutes=minutes, description="Timer", request=request)
    return minutes


@transaction.atomic
def snooze(ticket: Ticket, *, user, until, request=None) -> None:
    Ticket.objects.filter(pk=ticket.pk).update(snoozed_until=until)
    event(ticket, f"Snoozed until {timezone.localtime(until):%b %d, %I:%M %p} by {user.name}" if until else f"Woken up by {user.name}", user)
    audit(request, "snooze", "ticket", ticket.pk, f"{'Snoozed' if until else 'Woke'} {ticket.number}", area="tickets")


@transaction.atomic
def merge(source: Ticket, target: Ticket, *, user, request=None) -> Ticket:
    """Moves the conversation, time and files from `source` into `target` and closes `source`."""
    if source.pk == target.pk:
        raise ValueError("A ticket can't be merged into itself.")
    TicketMessage.objects.filter(ticket=source).update(ticket=target)
    TimeEntry.objects.filter(ticket=source).update(ticket=target)
    source.uploads.update(ticket=target)
    if source.details.strip():
        TicketMessage.objects.create(ticket=target, kind="reply", body=source.details, author_name=source.contact_name or "Request",
                                     via="merge", created_at=source.created_at)
    if source.cc:
        target.cc = ", ".join(dict.fromkeys(a.strip() for a in f"{target.cc},{source.cc}".split(",") if a.strip()))
        target.save(update_fields=["cc", "updated_at"])
    Ticket.objects.filter(pk=source.pk).update(merged_into=target, status="Closed", closed_at=timezone.now())
    event(target, f"{source.number} ({source.subject}) merged in by {user.name}", user)
    audit(request, "merge", "ticket", source.pk, f"Merged {source.number} into {target.number}", area="tickets")
    return target


def wake_snoozed() -> int:
    """Background job: snoozes that ran out."""
    n = 0
    for t in Ticket.objects.filter(snoozed_until__isnull=False, snoozed_until__lte=timezone.now()):
        Ticket.objects.filter(pk=t.pk).update(snoozed_until=None)
        event(t, "Snooze ended")
        n += 1
    return n
