"""Dashboard numbers — all live from the database. The page refreshes this part every 30 seconds."""
from datetime import datetime, time, timedelta

from django.db.models import Count, F, Max, Q, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from .permissions import can

PRIO_RANK = {"Critical": 0, "High": 1, "Medium": 2, "Low": 3}


def _ago(td) -> str:
    m = int(td.total_seconds() // 60)
    return f"{m} min" if m < 60 else f"{m // 60} h" if m < 1440 else f"{m // 1440} d"


def data(user) -> dict:
    from apps.helpdesk.models import OPEN_STATUSES, PAUSED_STATUSES, Ticket, TimeEntry
    now = timezone.now()
    today = timezone.localdate()
    week_start = today - timedelta(days=today.weekday())
    tz = timezone.get_current_timezone()
    ws = timezone.make_aware(datetime.combine(week_start, time.min), tz)
    out = {"now": now}

    if can(user, "tickets"):
        open_q = Ticket.objects.filter(status__in=OPEN_STATUSES, merged_into__isnull=True)
        late = Q(first_response_at__isnull=True, response_due_at__lt=now) | Q(resolve_due_at__lt=now)
        active = open_q.exclude(status__in=PAUSED_STATUSES)
        unassigned = open_q.filter(assigned_to__isnull=True)
        oldest = unassigned.order_by("created_at").values_list("created_at", flat=True).first()
        done = Q(status__in=["Resolved", "Closed"])
        closed_week = Ticket.objects.filter(done, Q(resolved_at__gte=ws) | Q(closed_at__gte=ws)).count()
        last_ws = ws - timedelta(days=7)
        same_point = now - timedelta(days=7)
        closed_last = Ticket.objects.filter(done).filter(Q(resolved_at__gte=last_ws, resolved_at__lt=same_point) | Q(closed_at__gte=last_ws, closed_at__lt=same_point)).count()
        mins = TimeEntry.objects.filter(work_date__gte=week_start).aggregate(t=Sum("minutes"), b=Sum("minutes", filter=Q(billable=True)))
        out["t"] = {
            "open": open_q.count(), "late": active.filter(late).count(), "mine": open_q.filter(assigned_to=user).count(),
            "unassigned": unassigned.count(), "oldest": _ago(now - oldest) if oldest else "",
            "closed_week": closed_week, "closed_delta": closed_week - closed_last,
            "hours": round((mins["t"] or 0) / 60, 1), "billable": round((mins["b"] or 0) / 60, 1),
        }
        # Needs attention: SLA over, critical/high, unassigned, client waiting on us
        rows = []
        for t in open_q.select_related("client", "assigned_to").annotate(
                last_client=Max("messages__created_at", filter=Q(messages__kind="reply", messages__author__isnull=True)),
                last_staff=Max("messages__created_at", filter=Q(messages__kind="reply", messages__author__isnull=False)))[:500]:
            reasons, score = [], 10
            due = t.response_due_at if not t.first_response_at else None
            if t.status not in PAUSED_STATUSES and ((due and due < now) or (t.resolve_due_at and t.resolve_due_at < now)):
                over = now - min(d for d in (due, t.resolve_due_at) if d and d < now)
                reasons.append(("SLA over " + _ago(over), "bad"))
                score = 0
            elif t.status not in PAUSED_STATUSES and due and due < now + timedelta(hours=1):
                reasons.append(("Respond in " + _ago(due - now), "warn"))
                score = min(score, 1)
            if t.last_client and (not t.last_staff or t.last_client > t.last_staff) and t.status not in ("New",):
                reasons.append(("Client replied " + _ago(now - t.last_client) + " ago", "info"))
                score = min(score, 2)
            if not t.assigned_to_id:
                reasons.append(("Unassigned", "muted"))
                score = min(score, 3)
            if t.priority in ("Critical", "High"):
                score = min(score, 4)
            if not reasons:
                reasons.append((f"{t.status} · {_ago(now - t.created_at)}", "muted"))
            rows.append((score, PRIO_RANK.get(t.priority, 9), t.created_at, t, reasons))
        rows.sort(key=lambda r: (r[0], r[1], r[2]))
        out["attention"] = [{"t": r[3], "reasons": r[4]} for r in rows[:8]]
        out["attention_more"] = max(0, len(rows) - 8)
        # Tickets opened per day, last 14 days
        start = today - timedelta(days=13)
        counts = dict(Ticket.objects.filter(created_at__date__gte=start).annotate(d=TruncDate("created_at", tzinfo=tz)).values("d").annotate(n=Count("id")).values_list("d", "n"))
        days = [start + timedelta(days=i) for i in range(14)]
        top = max([counts.get(d, 0) for d in days] + [1])
        out["chart"] = [{"d": d, "n": counts.get(d, 0), "pct": max(3, round(counts.get(d, 0) * 100 / top)), "today": d == today,
                         "weekend": d.weekday() >= 5} for d in days]
        out["chart_total"] = sum(c["n"] for c in out["chart"])

    if can(user, "billing"):
        from apps.billing.models import Invoice, Payment
        unpaid = Invoice.objects.filter(archived_at__isnull=True, status__in=["Sent", "Viewed", "Partial", "Overdue"])
        bal = F("total") - F("amount_paid")
        agg = unpaid.aggregate(a=Sum(bal), o=Sum(bal, filter=Q(due_date__lt=today)), n=Count("id"))
        paid = Payment.objects.filter(archived_at__isnull=True, status="Succeeded", paid_on__gte=today.replace(day=1)).aggregate(s=Sum("amount"))["s"] or 0
        out["b"] = {"unpaid": agg["a"] or 0, "overdue": agg["o"] or 0, "count": agg["n"] or 0, "collected_month": paid}
        out["payments"] = Payment.objects.filter(archived_at__isnull=True).select_related("client", "invoice").order_by("-paid_on", "-id")[:4]

    if can(user, "tools"):
        from apps.tools.models import CalendarEvent
        day_start = timezone.make_aware(datetime.combine(today, time.min), tz)
        out["events"] = CalendarEvent.objects.filter(archived_at__isnull=True, starts_at__gte=day_start, starts_at__lt=day_start + timedelta(days=1)).filter(
            Q(who=user) | Q(who__isnull=True)).select_related("client").order_by("starts_at")[:6]
    return out
