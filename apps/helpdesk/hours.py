"""Business hours: our office hours (Settings › Office hours) and each client's own hours.

Our hours drive the after-hours note and — when Settings › Office hours › "Due times count office hours only" is on — the
response and resolution deadlines: a 4-hour ticket opened at 4 PM Friday is due Monday morning, not Friday night.
A client's hours are on the client record and are shown on its tickets so a tech knows when they can call or go onsite.
"""
import datetime as dt
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.core.models import Setting

DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _days(raw: str, default="Mon,Tue,Wed,Thu,Fri") -> set[int]:
    out = set()
    for d in (raw or default).replace(";", ",").replace(" ", ",").split(","):
        d = d.strip()[:3].title()
        if d in DAYS:
            out.add(DAYS.index(d))
    return out


def _time(v):
    if isinstance(v, dt.time):
        return v
    try:
        return dt.time.fromisoformat((v or "").strip())
    except ValueError:
        return None


def _zone(name=""):
    try:
        return ZoneInfo(name or Setting.get("app.timezone", "") or timezone.get_current_timezone_name())
    except Exception:  # noqa: BLE001 — a mistyped zone name falls back to the server's
        return timezone.get_current_timezone()


class Hours:
    def __init__(self, opens, closes, days, tz):
        self.opens, self.closes, self.days, self.tz = opens, closes, days, tz

    @property
    def ok(self):
        return bool(self.opens and self.closes and self.opens < self.closes and self.days)

    def is_open(self, now=None) -> bool:
        now = timezone.localtime(now).astimezone(self.tz)
        return self.ok and now.weekday() in self.days and self.opens <= now.time() < self.closes

    def label(self) -> str:
        if not self.ok:
            return ""
        ds, runs, i = sorted(self.days), [], 0
        while i < len(ds):
            j = i
            while j + 1 < len(ds) and ds[j + 1] == ds[j] + 1:
                j += 1
            runs.append(DAYS[ds[i]] if i == j else f"{DAYS[ds[i]]}–{DAYS[ds[j]]}" if j - i > 1 else f"{DAYS[ds[i]]}, {DAYS[ds[j]]}")
            i = j + 1
        fmt = lambda t: t.strftime("%-I:%M %p").replace(":00", "")  # noqa: E731
        return f"{', '.join(runs)} · {fmt(self.opens)} – {fmt(self.closes)}"

    def add(self, start, minutes: int):
        """`minutes` of open time after `start`. The clock only runs while we're open."""
        if not self.ok or minutes <= 0:
            return start + dt.timedelta(minutes=max(0, minutes))
        cur, left = start.astimezone(self.tz), float(minutes)
        for _ in range(800):  # days; far more than any deadline needs
            day_open = cur.replace(hour=self.opens.hour, minute=self.opens.minute, second=0, microsecond=0)
            day_close = cur.replace(hour=self.closes.hour, minute=self.closes.minute, second=0, microsecond=0)
            if cur.weekday() in self.days and cur < day_close:
                cur = max(cur, day_open)
                room = (day_close - cur).total_seconds() / 60
                if left <= room:
                    return (cur + dt.timedelta(minutes=left)).astimezone(dt.timezone.utc)
                left -= room
            nxt = (cur + dt.timedelta(days=1)).date()
            cur = dt.datetime.combine(nxt, self.opens, tzinfo=self.tz)
        return start + dt.timedelta(minutes=minutes)


def office() -> Hours:
    return Hours(_time(Setting.get("helpdesk.open", "")), _time(Setting.get("helpdesk.close", "")), _days(Setting.get("helpdesk.days", "")), _zone())


def office_label() -> str:
    """What clients are told. The hours in Settings › Office hours, else the free-text line in Company profile."""
    return office().label() or Setting.get("company.hours", "")


def due(start, minutes: int, priority: str = ""):
    """A deadline `minutes` after `start`: in office hours when that's switched on, around the clock otherwise."""
    h = office()
    from django.conf import settings
    on = Setting.get("tickets.sla_business_hours", "true" if getattr(settings, "SLA_BUSINESS_HOURS", True) else "false")
    around_the_clock = (on == "false" or not h.ok
                        or (priority == "Critical" and Setting.get("tickets.sla_critical_247", "true") != "false"))
    return start + dt.timedelta(minutes=minutes) if around_the_clock else h.add(start, minutes)


def client_hours(client) -> Hours | None:
    if client is None or not (client.hours_open and client.hours_close):
        return None
    h = Hours(client.hours_open, client.hours_close, _days(client.hours_days), _zone(client.hours_timezone))
    return h if h.ok else None


def client_line(client) -> dict | None:
    """For tickets: {'label': 'Mon–Fri · 8 AM – 5 PM', 'open': True, 'note': '…'} or None when the client has no hours saved."""
    h = client_hours(client)
    note = (getattr(client, "hours_note", "") or "").strip() if client else ""
    if h is None:
        return {"label": "", "open": None, "note": note} if note else None
    tz = "" if h.tz.key == _zone().key else {"America/Phoenix": "Arizona time", "America/Denver": "Mountain time", "America/Chicago": "Central time",
                                             "America/Los_Angeles": "Pacific time", "America/New_York": "Eastern time"}.get(h.tz.key, h.tz.key)
    return {"label": h.label() + (f" ({tz})" if tz else ""), "open": h.is_open(), "note": note}


def client_text(client) -> str:
    """The client's saved hours as one line, to put on a new service call."""
    line = client_line(client)
    if not line:
        return ""
    return " — ".join(x for x in (line["label"], line["note"]) if x)[:255]


def required() -> bool:
    from django.conf import settings
    return Setting.get("tickets.require_hours", "true" if getattr(settings, "REQUIRE_TICKET_HOURS", True) else "false") != "false"


def remember(client, text: str) -> None:
    """First time a client tells us their hours on a call, keep them on the client so the next call starts filled in."""
    if client is not None and text and not client_text(client):
        type(client).objects.filter(pk=client.pk).update(hours_note=text[:255])
