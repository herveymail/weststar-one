"""Tech app — the phone version of Weststar ONE at /tech/ (add it to the iPhone home screen: Share › Add to Home Screen).

Five tabs: Today (dashboard tiles + my jobs), Tickets, Schedule, Time, Me. A ticket screen has tap-to-call, directions,
status, timer, notes/replies with time, camera photos and the customer signature.

Security: same sign-in, two-factor and permissions as the website. Pages are never cached on the phone (the service
worker only keeps the app's own icons, styles and an offline notice). "Stay signed in" on the phone is a setting
(Settings › Security › Tech app); signing out ends it right away.
"""
import os
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import Case, IntegerField, Q, Sum, Value, When
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.templatetags.static import static
from django.utils import timezone

from apps.core.audit import audit
from apps.core.models import Setting
from apps.core.permissions import can

from . import services
from .models import OPEN_STATUSES, STATUSES, WORK_TYPES, Ticket, TicketTimer, TimeEntry
from .signoff import SignoffRequired, is_breakfix

PRI_ORDER = Case(When(priority="Critical", then=Value(0)), When(priority="High", then=Value(1)), When(priority="Medium", then=Value(2)),
                 default=Value(3), output_field=IntegerField())


def stay_days() -> int:
    try:
        return max(0, min(int(Setting.get("tech.stay_days", "7") or 0), 30))
    except ValueError:
        return 7


def _tech(view):
    """login + ticket permission, and mark the session as the phone app so it can stay signed in (see middleware)."""
    @login_required
    def wrapped(request, *a, **kw):
        if not can(request.user, "tickets", "view"):
            raise PermissionDenied
        ua = request.META.get("HTTP_USER_AGENT", "")
        if not request.session.get("tech_app") and stay_days() and any(k in ua for k in ("iPhone", "iPad", "Android", "Mobile")):
            request.session["tech_app"] = True
            request.session.set_expiry(stay_days() * 86400)
        return view(request, *a, **kw)
    wrapped.__name__ = view.__name__
    return wrapped


def _clock(user):
    from apps.hr.models import TimeclockEntry
    return TimeclockEntry.objects.filter(user=user, status="Open", clock_out__isnull=True, archived_at__isnull=True).order_by("-clock_in").first()


def _mine(user):
    return (Ticket.objects.filter(assigned_to=user, status__in=OPEN_STATUSES, merged_into__isnull=True)
            .select_related("client").annotate(pri=PRI_ORDER).order_by("pri", "due_date", "-updated_at"))


def _ctx(request, tab, **kw):
    return {"tab": tab, "company": Setting.get("company.name", "") or "Weststar MSP", "clock": _clock(request.user),
            "timer": TicketTimer.objects.filter(user=request.user).select_related("ticket", "ticket__client").first(), **kw}


@_tech
def today(request):
    from apps.tools.models import CalendarEvent
    now = timezone.localtime()
    day = now.date()
    mine = list(_mine(request.user)[:60])
    minutes = TimeEntry.objects.filter(user=request.user, work_date=day).aggregate(m=Sum("minutes"))["m"] or 0
    bf = {}
    need_sig = []
    for t in mine:
        if t.client_id not in bf:
            bf[t.client_id] = is_breakfix(t.client)
        if bf[t.client_id] and t.status in ("In progress", "Scheduled", "Open") and not t.signoffs.filter(type="completion").exists():
            need_sig.append(t)
    events = list(CalendarEvent.objects.filter(Q(who=request.user) | Q(who__isnull=True), archived_at__isnull=True,
                                               starts_at__date=day).select_related("client").order_by("starts_at")[:20])
    due_today = [t for t in mine if t.due_date and t.due_date <= day]
    tiles = [
        {"n": len(events) + len(due_today), "label": "Jobs today", "color": "#2563eb", "href": "/tech/schedule/"},
        {"n": sum(1 for t in mine if t.priority == "Critical"), "label": "Urgent", "color": "#dc2626", "href": "/tech/tickets/?f=urgent"},
        {"n": f"{minutes / 60:.1f}".rstrip("0").rstrip(".") + "h", "label": "Logged today", "color": "#16a34a", "href": "/tech/time/"},
        {"n": len(need_sig), "label": "Need signature", "color": "#ea580c", "href": "/tech/tickets/?f=sign"},
    ]
    clock = _clock(request.user)
    on_for = ""
    if clock:
        mins = int((timezone.now() - clock.clock_in).total_seconds() // 60)
        on_for = f"{mins // 60}h {mins % 60}m"
    return render(request, "tech/today.html", _ctx(request, "today", tiles=tiles, mine=mine[:15], events=events, now=now, on_for=on_for,
                                                  first=(request.user.name or "").split(" ")[0]))


@_tech
def tickets(request):
    f = request.GET.get("f", "mine")
    q = request.GET.get("q", "").strip()[:100]
    qs = Ticket.objects.filter(merged_into__isnull=True).select_related("client", "assigned_to").annotate(pri=PRI_ORDER)
    if q:
        qs = qs.filter(Q(number__icontains=q) | Q(subject__icontains=q) | Q(client__name__icontains=q) | Q(contact_name__icontains=q) | Q(device__icontains=q))
        if f != "closed":
            qs = qs.order_by("-updated_at")
    if f == "unassigned":
        qs = qs.filter(assigned_to__isnull=True, status__in=OPEN_STATUSES)
    elif f == "open":
        qs = qs.filter(status__in=OPEN_STATUSES)
    elif f == "urgent":
        qs = qs.filter(assigned_to=request.user, status__in=OPEN_STATUSES, priority="Critical")
    elif f == "sign":
        ids = [t.pk for t in _mine(request.user) if is_breakfix(t.client) and not t.signoffs.filter(type="completion").exists()]
        qs = qs.filter(pk__in=ids)
    elif f == "closed":
        qs = qs.filter(assigned_to=request.user, status__in=["Resolved", "Closed"]).order_by("-updated_at")
    elif not q:
        f = "mine"
        qs = qs.filter(assigned_to=request.user, status__in=OPEN_STATUSES)
    if f != "closed" and not q:
        qs = qs.order_by("pri", "due_date", "-updated_at")
    counts = {"mine": _mine(request.user).count(), "unassigned": Ticket.objects.filter(assigned_to__isnull=True, status__in=OPEN_STATUSES, merged_into__isnull=True).count()}
    return render(request, "tech/tickets.html", _ctx(request, "tickets", rows=qs[:80], f=f, q=q, counts=counts))


def _phone(t):
    for p in ((t.contact.phone if t.contact else ""), getattr(t.client, "phone", "") if t.client else ""):
        if p:
            return p, "".join(ch for ch in p if ch.isdigit() or ch == "+")
    return "", ""


def _address(t):
    c = t.client
    if not c:
        return ""
    return ", ".join(x for x in [c.address, c.city, " ".join(x for x in [c.state, c.zip] if x)] if x)


@_tech
def ticket(request, pk):
    from urllib.parse import quote
    t = get_object_or_404(Ticket.objects.select_related("client", "contact", "assigned_to"), pk=pk)
    edit = can(request.user, "tickets", "edit")
    if request.method == "POST":
        if not edit:
            raise PermissionDenied
        return _act(request, t)
    phone, tel = _phone(t)
    addr = _address(t)
    timer = TicketTimer.objects.filter(ticket=t, user=request.user).first()
    msgs = list(t.messages.select_related("author").prefetch_related("uploads").order_by("-created_at")[:40])
    photos = list(t.uploads.filter(content_type__startswith="image/").order_by("-created_at")[:12])
    logged = t.time_entries.aggregate(m=Sum("minutes"))["m"] or 0
    return render(request, "tech/ticket.html", _ctx(request, "tickets", t=t, edit=edit, phone=phone, tel=tel, addr=addr,
                  maps=f"https://maps.apple.com/?daddr={quote(addr)}" if addr else "", timer_here=timer, msgs=msgs, photos=photos,
                  statuses=STATUSES, work_types=WORK_TYPES, hours=["0.25", "0.5", "0.75", "1", "1.5", "2", "3", "4", "6", "8"], logged=f"{logged / 60:.2f}".rstrip("0").rstrip("."),
                  breakfix=is_breakfix(t.client), signed=t.signoffs.filter(type="completion").first()))


def _act(request, t):
    a = request.POST.get("action")
    back = f"/tech/t/{t.pk}/"
    if a == "timer":
        if TicketTimer.objects.filter(ticket=t, user=request.user).exists():
            n = services.stop_timer(t, request.user, save=request.POST.get("discard") != "1", request=request)
            messages.success(request, f"Logged {n} min." if n else "Timer stopped.")
        else:
            services.start_timer(t, request.user)
            if t.status in ("New", "Open", "Scheduled"):
                try:
                    services.update_ticket(t, user=request.user, request=request, status="In progress")
                except SignoffRequired:
                    pass
            messages.success(request, "Timer started.")
    elif a == "status":
        st = request.POST.get("status")
        if st in STATUSES and st != t.status:
            try:
                services.update_ticket(t, user=request.user, request=request, status=st)
                messages.success(request, f"Status: {st}.")
            except SignoffRequired:
                messages.error(request, "This is a break/fix client — get the customer's signature before closing.")
                return redirect(f"/tickets/{t.pk}/signoff/?type=completion&back=tech")
    elif a == "take":
        services.update_ticket(t, user=request.user, request=request, assigned_to=request.user)
        messages.success(request, "Assigned to you.")
    elif a in ("note", "photo"):
        files = [f for f in request.FILES.getlist("files") if f]
        body = request.POST.get("body", "").strip()[:20000]
        if not body and files:
            body = f"Added {len(files)} photo{'s' if len(files) != 1 else ''} from the tech app"
        if not body:
            messages.error(request, "Write a note or add a photo first.")
            return redirect(back)
        kind = request.POST.get("kind") if request.POST.get("kind") in ("reply", "note", "work") else "note"
        try:
            minutes = max(0, min(round(float(request.POST.get("hours") or 0) * 60), 1440))
        except ValueError:
            minutes = 0
        wt = request.POST.get("work_type") if request.POST.get("work_type") in WORK_TYPES else "On-site"
        msg = services.add_message(t, user=request.user, kind=kind, body=body, minutes=minutes, work_type=wt,
                                   billable=request.POST.get("billable", "1") in ("1", "on"), request=request)
        if files:
            from apps.files.services import save_uploads
            try:
                save_uploads(request, files, kind="ticket", ticket=t, message=msg)
            except ValidationError as e:
                messages.error(request, " ".join(e.messages))
        messages.success(request, "Reply sent to the client." if kind == "reply" else "Saved.")
    return redirect(back)


@_tech
def schedule(request):
    from apps.tools.models import CalendarEvent
    day = timezone.localdate()
    try:
        pick = timezone.datetime.fromisoformat(request.GET.get("d", "")).date()
    except ValueError:
        pick = day
    week = [pick - timedelta(days=pick.weekday()) + timedelta(days=i) for i in range(7)]
    events = CalendarEvent.objects.filter(Q(who=request.user) | Q(who__isnull=True), archived_at__isnull=True,
                                          starts_at__date=pick).select_related("client").order_by("starts_at")
    due = _mine(request.user).filter(due_date=pick) if pick != day else _mine(request.user).filter(due_date__lte=pick)
    return render(request, "tech/schedule.html", _ctx(request, "schedule", week=week, pick=pick, today=day, events=events, due=due,
                                                     prev=(pick - timedelta(days=7)).isoformat(), next=(pick + timedelta(days=7)).isoformat()))


@_tech
def time_tab(request):
    from apps.hr.models import TimeclockEntry
    from apps.tools.models import MileageTrip
    day = timezone.localdate()
    if request.method == "POST":
        a = request.POST.get("action")
        if a == "clock":
            e = _clock(request.user)
            if e:
                e.clock_out, e.status = timezone.now(), "Submitted"
                e.save()
                audit(request, "clock_out", "timeclock", e.pk, "Clocked out (tech app)", area="hr")
                messages.success(request, "Clocked out.")
            else:
                e = TimeclockEntry.objects.create(user=request.user, clock_in=timezone.now(), status="Open", created_by=request.user)
                audit(request, "clock_in", "timeclock", e.pk, "Clocked in (tech app)", area="hr")
                messages.success(request, "Clocked in.")
            return redirect(request.POST.get("next") if (request.POST.get("next") or "").startswith("/tech/") else "/tech/time/")
        if a == "mileage":
            try:
                miles = round(float(request.POST.get("miles") or 0), 1)
            except ValueError:
                miles = 0
            trip = request.POST.get("trip", "").strip()[:255]
            if miles <= 0 or miles > 2000 or not trip:
                messages.error(request, "Enter where you drove and the miles.")
            else:
                from apps.crm.models import Client
                cl = Client.objects.filter(pk=request.POST.get("client") or 0).first() if (request.POST.get("client") or "").isdigit() else None
                m = MileageTrip.objects.create(user=request.user, trip_date=day, trip=trip, miles=miles, client=cl,
                                               billable=bool(cl) and request.POST.get("billable") == "1", created_by=request.user)
                audit(request, "create", "mileage", m.pk, f"Logged {miles} mi (tech app)", area="tools")
                messages.success(request, f"Logged {miles} miles.")
            return redirect("/tech/time/")
    start = day - timedelta(days=day.weekday())
    entries = TimeEntry.objects.filter(user=request.user, work_date__gte=start).select_related("ticket", "ticket__client").order_by("-work_date", "-created_at")
    week_min = sum(e.minutes for e in entries)
    today_min = sum(e.minutes for e in entries if e.work_date == day)
    shifts = TimeclockEntry.objects.filter(user=request.user, clock_in__date__gte=start, archived_at__isnull=True).order_by("-clock_in")[:14]
    from apps.crm.models import Client
    recent_clients = Client.objects.filter(tickets__assigned_to=request.user, archived_at__isnull=True).distinct().order_by("name")[:60]
    return render(request, "tech/time.html", _ctx(request, "time", entries=entries[:30], week_h=f"{week_min / 60:.1f}", today_h=f"{today_min / 60:.1f}",
                                                 shifts=shifts, clients=recent_clients,
                                                 trips=MileageTrip.objects.filter(user=request.user, trip_date__gte=start, archived_at__isnull=True).order_by("-trip_date", "-id")[:10]))


@_tech
def me(request):
    return render(request, "tech/me.html", _ctx(request, "me", stay=stay_days()))


# ── Home-screen app plumbing ──
def manifest(request):
    name = Setting.get("company.name", "") or "Weststar"
    return JsonResponse({
        "name": "Weststar ONE Tech", "short_name": "WS Tech",
        "description": f"{name} tech app", "start_url": "/tech/", "scope": "/tech/", "display": "standalone",
        "background_color": "#f1f5f9", "theme_color": "#1e4f8f", "orientation": "portrait",
        "icons": [{"src": static("tech/icon-192.png"), "sizes": "192x192", "type": "image/png"},
                  {"src": static("tech/icon-512.png"), "sizes": "512x512", "type": "image/png"},
                  {"src": static("tech/icon-512.png"), "sizes": "512x512", "type": "image/png", "purpose": "maskable"}],
    }, content_type="application/manifest+json")


SW_VERSION = "1"


def service_worker(request):
    """Served from /tech/ so it can control the app. Caches only the app shell's static files — never ticket pages."""
    path = os.path.join(os.path.dirname(__file__), "static", "tech", "sw.js")
    with open(path) as f:
        js = f.read()
    assets = [static("tech/tech.css"), static("tech/tech.js"), static("tech/icon-192.png"), static("core/bi/bootstrap-icons.min.css")]
    js = js.replace("__ASSETS__", ",".join(f'"{a}"' for a in assets)).replace("__VERSION__", f"{SW_VERSION}-{settings.APP_VERSION}")
    r = HttpResponse(js, content_type="application/javascript")
    r["Cache-Control"] = "no-cache"
    r["Service-Worker-Allowed"] = "/tech/"
    return r


def offline(request):
    return render(request, "tech/offline.html")

