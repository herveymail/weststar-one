""""To do today" on the dashboard, the morning summary email, and renewal heads-ups.

Everything here is a short list of things a person should act on, each with a link straight to where it gets done.
"""
from datetime import timedelta

from django.conf import settings
from django.db.models import F, Q
from django.utils import timezone

from . import mail
from .models import Setting
from .permissions import can


def notice_days() -> int:
    try:
        return max(1, min(int(Setting.get("renewals.notice_days", "30") or 30), 180))
    except ValueError:
        return 30


def todo(user) -> list[dict]:
    """[{icon, text, href, tone}] — tone: bad / warn / info."""
    today = timezone.localdate()
    out = []
    if can(user, "tickets"):
        from apps.helpdesk.models import OPEN_STATUSES, RecurringTicket, Ticket
        late = Ticket.objects.filter(assigned_to=user, status__in=OPEN_STATUSES, due_date__lt=today, merged_into__isnull=True).count()
        if late:
            out.append({"icon": "bi-alarm", "text": f"{late} of your tickets {'is' if late == 1 else 'are'} past the due date", "href": "/tickets/?view=mine", "tone": "bad"})
        due = Ticket.objects.filter(assigned_to=user, status__in=OPEN_STATUSES, due_date=today, merged_into__isnull=True).count()
        if due:
            out.append({"icon": "bi-calendar-check", "text": f"{due} of your tickets {'is' if due == 1 else 'are'} due today", "href": "/tickets/?view=mine", "tone": "warn"})
        rec = RecurringTicket.objects.filter(status="Active", archived_at__isnull=True, next_run=today).count()
        if rec:
            out.append({"icon": "bi-arrow-repeat", "text": f"{rec} recurring ticket schedule{'s' if rec != 1 else ''} open{'s' if rec == 1 else ''} today", "href": "/m/recurring_tickets/", "tone": "info"})
    if can(user, "billing"):
        from apps.billing.models import Contract, Invoice, Quote, Renewal
        from apps.billing.ready import collect
        groups = [g for g in collect(today) if not g["managed"]]
        if groups:
            total = sum(g["total"] for g in groups)
            out.append({"icon": "bi-hourglass-split", "text": f"${total:,.2f} of work is ready to bill ({len(groups)} client{'s' if len(groups) != 1 else ''})", "href": "/billing/ready/", "tone": "info"})
        overdue = Invoice.objects.filter(archived_at__isnull=True, status__in=["Sent", "Viewed", "Partial", "Overdue"], due_date__lt=today, total__gt=F("amount_paid")).count()
        if overdue:
            out.append({"icon": "bi-exclamation-circle", "text": f"{overdue} invoice{'s are' if overdue != 1 else ' is'} past due", "href": "/billing/ar/", "tone": "bad"})
        drafts = Invoice.objects.filter(archived_at__isnull=True, status="Draft").count()
        if drafts:
            out.append({"icon": "bi-file-earmark", "text": f"{drafts} draft invoice{'s' if drafts != 1 else ''} not sent yet", "href": "/m/invoices/?status=Draft", "tone": "info"})
        q = Quote.objects.filter(archived_at__isnull=True, status="Sent")
        waiting, expired = q.filter(Q(expires_on__isnull=True) | Q(expires_on__gte=today)).count(), q.filter(expires_on__lt=today).count()
        if waiting:
            out.append({"icon": "bi-file-earmark-text", "text": f"{waiting} quote{'s' if waiting != 1 else ''} waiting for the client", "href": "/m/quotes/?status=Sent", "tone": "info"})
        if expired:
            out.append({"icon": "bi-file-earmark-x", "text": f"{expired} sent quote{'s have' if expired != 1 else ' has'} expired — follow up or resend", "href": "/m/quotes/?status=Sent", "tone": "warn"})
        unsigned = Contract.objects.filter(archived_at__isnull=True, status="Sent").count()
        if unsigned:
            out.append({"icon": "bi-pen", "text": f"{unsigned} contract{'s' if unsigned != 1 else ''} waiting for a signature", "href": "/m/contracts/?status=Sent", "tone": "info"})
        soon = today + timedelta(days=notice_days())
        ren = Renewal.objects.filter(archived_at__isnull=True, status="Upcoming", renews_on__lte=soon).count()
        if ren:
            out.append({"icon": "bi-calendar-event", "text": f"{ren} renewal{'s' if ren != 1 else ''} in the next {notice_days()} days", "href": "/m/renewals/", "tone": "warn"})
    if can(user, "tools"):
        from apps.tools.models import Domain
        soon = today + timedelta(days=notice_days())
        d = Domain.objects.filter(archived_at__isnull=True).filter(Q(expires_on__lte=soon) | Q(ssl_expires_on__lte=soon)).count()
        if d:
            out.append({"icon": "bi-globe", "text": f"{d} domain{'s' if d != 1 else ''} or SSL certificate{'s' if d != 1 else ''} expiring within {notice_days()} days", "href": "/m/domains/", "tone": "warn"})
    return out


def morning_summary(now=None, force=False) -> dict:
    """Weekdays from 7 AM office time: one email per person who turned it on in Profile. Once a day."""
    from apps.accounts.models import User
    from apps.helpdesk.models import OPEN_STATUSES, Ticket
    from apps.tools.models import CalendarEvent
    now = timezone.localtime(now or timezone.now())
    if not force and (now.weekday() >= 5 or now.hour < 7):
        return {"sent": 0}
    today = now.date()
    sent = 0
    for u in User.objects.filter(is_active=True, morning_summary=True):
        key = f"digest.morning.{u.pk}"
        if Setting.get(key, "") == today.isoformat():
            continue
        tickets = list(Ticket.objects.filter(assigned_to=u, status__in=OPEN_STATUSES, merged_into__isnull=True).select_related("client")
                       .order_by("due_date", "-priority")[:15]) if can(u, "tickets") else []
        events = list(CalendarEvent.objects.filter(Q(who=u) | Q(who__isnull=True), archived_at__isnull=True, starts_at__date=today)
                      .select_related("client").order_by("starts_at")[:10]) if can(u, "tools") else []
        items = todo(u)
        Setting.put(key, today.isoformat())
        if not (tickets or events or items):
            continue
        if mail.send([u.email], f"Your day — {today:%A, %B %-d}", "email/morning_summary",
                     {"u": u, "tickets": tickets, "events": events, "items": items, "today": today, "link": settings.APP_URL + "/",
                      "app_url": settings.APP_URL, "meta": "Morning summary"}, background=True):
            sent += 1
    return {"sent": sent}


def renewal_notices(now=None) -> dict:
    """Once per item: renewals, domains and SSL certificates coming up within the notice window → one email to the team."""
    from apps.billing.models import Renewal
    from apps.tools.models import Domain
    today = timezone.localdate(now) if now else timezone.localdate()
    soon = today + timedelta(days=notice_days())
    to = [a.strip() for a in (Setting.get("renewals.notify_to", "") or Setting.get("email.support_address", "")).split(",") if "@" in a]
    ren = list(Renewal.objects.filter(archived_at__isnull=True, status="Upcoming", renews_on__lte=soon, renews_on__gte=today - timedelta(days=7))
               .filter(Q(notified_on__isnull=True) | ~Q(notified_on=F("renews_on"))).select_related("client"))
    doms = []
    for d in Domain.objects.filter(archived_at__isnull=True).filter(Q(expires_on__lte=soon, expires_on__gte=today) | Q(ssl_expires_on__lte=soon, ssl_expires_on__gte=today)).select_related("client"):
        first = min(x for x in (d.expires_on, d.ssl_expires_on) if x and today <= x <= soon)
        if d.notified_on != first:
            d.first = first
            doms.append(d)
    if not (ren or doms) or not to:
        return {"renewals": len(ren), "domains": len(doms), "sent": False}
    ok = mail.send(to, f"Coming up for renewal: {len(ren) + len(doms)} item{'s' if len(ren) + len(doms) != 1 else ''}", "email/renewals",
                   {"renewals": ren, "domains": doms, "days": notice_days(), "link": settings.APP_URL + "/m/renewals/", "app_url": settings.APP_URL,
                    "meta": "Renewals"}, background=True)
    if ok:
        for r in ren:
            Renewal.objects.filter(pk=r.pk).update(notified_on=r.renews_on)
        for d in doms:
            Domain.objects.filter(pk=d.pk).update(notified_on=d.first)
    return {"renewals": len(ren), "domains": len(doms), "sent": bool(ok)}


def renewal_quote(renewal, user=None):
    """A draft quote for a renewal (cost plus Settings › Renewals markup), linked to it so it isn't made twice."""
    from decimal import Decimal

    from apps.billing.models import Quote, QuoteLine
    from apps.core.numbering import next_number
    if renewal.quote_id:
        return renewal.quote
    if renewal.client is None:
        return None
    try:
        markup = Decimal(Setting.get("renewals.markup_pct", "0") or 0)
    except Exception:  # noqa: BLE001
        markup = Decimal(0)
    price = ((renewal.cost or Decimal(0)) * (1 + markup / 100)).quantize(Decimal("0.01"))
    today = timezone.localdate()
    try:
        valid = int(Setting.get("billing.quote_valid_days", "30") or 30)
    except ValueError:
        valid = 30
    q = Quote.objects.create(number=next_number("quote"), client=renewal.client, status="Draft", quote_date=today,
                             expires_on=min(today + timedelta(days=valid), renewal.renews_on) if renewal.renews_on > today else today + timedelta(days=valid),
                             scope=f"Renewal of {renewal.item}" + (f" ({renewal.type.lower()})" if renewal.type else "") + f", due {renewal.renews_on:%B %-d, %Y}.",
                             tax_rate=renewal.client.tax_rate, created_by=user)
    QuoteLine.objects.create(quote=q, description=f"{renewal.item} — renewal"[:500], qty=1, rate=price, taxable=renewal.type in ("License", "Subscription", "Warranty"))
    q.recalc()
    q.save()
    type(renewal).objects.filter(pk=renewal.pk).update(quote=q)
    return q
