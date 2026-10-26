from django import template
from django.utils.html import format_html
from django.utils.safestring import mark_safe

from apps.core.ui import PRIORITY_CLASS, money, status_class, tone

register = template.Library()

ICONS = {
    "dashboard": "M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z",
    "tickets": "M3 6h18v4a2 2 0 0 0 0 4v4H3v-4a2 2 0 0 0 0-4z",
    "projects": "M3 4h7v16H3zM14 4h7v10h-7z",
    "clients": "M5.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.8c1.6.8 2.6 2.5 3 5.2",
    "leads": "M3 4h18l-7 8v6l-4 2v-8z",
    "marketing": "M3 10v4h4l6 4V6L7 10zM16 9a3 3 0 0 1 0 6M19 6a7 7 0 0 1 0 12",
    "invoices": "M6 3h12v18l-3-2-3 2-3-2-3 2zM9 8h6M9 12h6M9 16h3",
    "recurring": "M4 12a8 8 0 0 1 14-5.3M20 4v4h-4M20 12a8 8 0 0 1-14 5.3M4 20v-4h4",
    "banking": "M3 10l9-6 9 6M5 10v8M9.5 10v8M14.5 10v8M19 10v8M3 20h18",
    "quotes": "M6 3h8l5 5v13H6zM14 3v5h5M9 13h6M9 17h4",
    "contracts": "M6 3h8l5 5v13H6zM14 3v5h5M9 15l2 2 4-4",
    "policies": "M12 3l8 3v6c0 4.5-3.4 8.3-8 9-4.6-.7-8-4.5-8-9V6zM9 12l2 2 4-4",
    "training": "M2 9l10-5 10 5-10 5zM6 11v5c3 2 9 2 12 0v-5M22 9v6",
    "renewals": "M4 5h16v16H4zM4 9h16M8 3v4M16 3v4M9 15l2 2 4-4",
    "expenses": "M3 6h18v12H3zM9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
    "vendors": "M4 9l1-5h14l1 5M4 9v11h16V9M4 9h16M10 20v-6h4v6",
    "calendar": "M4 5h16v16H4zM4 9h16M8 3v4M16 3v4",
    "inventory": "M3 7l9-4 9 4v10l-9 4-9-4zM3 7l9 4 9-4M12 11v10",
    "mileage": "M5 16l1.5-6h11L19 16M4 16h16v3H4zM7 19v2M17 19v2",
    "messages": "M3 6h18v12H3zM3 7l9 6 9-6",
    "domains": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M3 12h18M12 3c3 3.5 3 14.5 0 18M12 3c-3 3.5-3 14.5 0 18",
    "backups": "M7 18a4 4 0 0 1-.5-8A6 6 0 0 1 18 9a4.5 4.5 0 0 1-.5 9zM9.5 13.5l2 2 3.5-3.5",
    "rmm": "M3 4h18v12H3zM8 20h8M12 16v4",
    "kb": "M4 4h6a2 2 0 0 1 2 2v14a2 2 0 0 0-2-2H4zM20 4h-6a2 2 0 0 0-2 2v14a2 2 0 0 1 2-2h6z",
    "workflows": "M13 2L4 14h7l-1 8 9-12h-7z",
    "my_hr": "M5 3h14v18H5zM9 11a3 3 0 1 0 6 0a3 3 0 1 0-6 0M8 18c.6-2 2.1-3 4-3s3.4 1 4 3",
    "hr": "M5.5 8a3.5 3.5 0 1 0 7 0a3.5 3.5 0 1 0-7 0M2.5 20c.8-3.6 3.4-5.5 6.5-5.5s5.7 1.9 6.5 5.5M16 4.5a3.5 3.5 0 0 1 0 7M18.5 14.8c1.6.8 2.6 2.5 3 5.2",
    "settings": "M9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1",
    "tools": "M14.7 6.3a4 4 0 0 0-5.4 5.4L3 18v3h3l6.3-6.3a4 4 0 0 0 5.4-5.4l-2.5 2.5-2.4-.6-.6-2.4z",
    "chevron": "M6 9l6 6 6-6", "edit": "M12 20h9M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4z", "download": "M12 3v12m0 0l-4-4m4 4l4-4M4 21h16", "print": "M6 9V3h12v6M6 18H4v-7h16v7h-2M8 14h8v7H8z", "send": "M22 2L11 13M22 2l-7 20-4-9-9-4z", "sparkle": "M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8zM19 15l.8 2.2L22 18l-2.2.8L19 21l-.8-2.2L16 18l2.2-.8z", "chevron-right": "M9 6l6 6-6 6", "search": "M4 11a7 7 0 1 0 14 0a7 7 0 1 0-14 0M20 20l-3.5-3.5", "back": "M15 18l-6-6 6-6",
    "close": "M6 6l12 12M18 6L6 18", "plus": "M12 5v14M5 12h14", "lock": "M6 11h12v10H6zM8 11V7a4 4 0 0 1 8 0v4",
    "eye": "M2 12s3.5-7 10-7 10 7 10 7-3.5 7-10 7S2 12 2 12zM9 12a3 3 0 1 0 6 0a3 3 0 1 0-6 0",
    "clock": "M3 12a9 9 0 1 0 18 0a9 9 0 1 0-18 0M12 7v5l3 2",
    "file": "M20 11.5l-8 8a5 5 0 0 1-7-7l8.5-8.5a3.3 3.3 0 0 1 4.7 4.7L9.7 17.2a1.7 1.7 0 0 1-2.4-2.4L15 7",
}


@register.simple_tag
def icon(name, size=18):
    d = ICONS.get(name, ICONS["dashboard"])
    return format_html('<svg width="{0}" height="{0}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" '
                       'stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" class="ic"><path d="{1}"/></svg>', size, d)


@register.filter
def pill_tone(value):
    return tone(value)


@register.filter
def prio_class(value):
    return PRIORITY_CLASS.get(value, "")


@register.filter
def status_cls(value):
    return status_class(value)


@register.filter
def dollars(value):
    return money(value)


@register.filter
def minutes_text(m):
    m = int(m or 0)
    if not m:
        return "None yet"
    h, r = divmod(m, 60)
    return " ".join(p for p in [f"{h}h" if h else "", f"{r}m" if r else ""] if p)


@register.filter
def sla_text(t):
    from django.utils import timezone
    if t.sla == "done":
        return t.status
    if t.sla == "paused":
        return "Paused"
    if t.first_response_at or not t.response_due_at:
        return ago(t.updated_at)
    secs = (t.response_due_at - timezone.now()).total_seconds()
    late = secs < 0
    m = int(abs(secs) // 60)
    txt = f"{m}m" if m < 60 else f"{m // 60}h {m % 60}m" if m < 1440 else f"{m // 1440}d"
    return f"Late {txt}" if late else txt


@register.filter
def ago(when):
    """Short 'how long ago': 'just now', '4m ago', '3h ago', '2d ago', or a date."""
    from django.utils import timezone
    from django.utils.formats import date_format
    if not when:
        return ""
    secs = (timezone.now() - when).total_seconds()
    if secs < 60:
        return "just now"
    m = int(secs // 60)
    if m < 60:
        return f"{m}m ago"
    if m < 1440:
        return f"{m // 60}h ago"
    if m < 1440 * 30:
        return f"{m // 1440}d ago"
    return date_format(timezone.localtime(when), "M j, Y")


@register.filter
def when(dt_):
    """'Oct 22, 2:34 PM' this year, 'Oct 22, 2025, 2:34 PM' otherwise."""
    from django.utils import timezone
    from django.utils.formats import date_format
    if not dt_:
        return ""
    local = timezone.localtime(dt_)
    return date_format(local, "M j, g:i A" if local.year == timezone.localtime().year else "M j, Y, g:i A")


@register.filter
def get_item(d, key):
    return d.get(key) if hasattr(d, "get") else None


@register.simple_tag(takes_context=True)
def qs_replace(context, **kwargs):
    """Current query string with some values replaced: {% qs_replace page=2 %}"""
    q = context["request"].GET.copy()
    for k, v in kwargs.items():
        if v in (None, ""):
            q.pop(k, None)
        else:
            q[k] = v
    return mark_safe("?" + q.urlencode()) if q else "?"


@register.filter
def initials(name):
    parts = [p for p in str(name or "").replace(".", " ").split() if p[:1].isalnum()]
    return ("".join(p[0] for p in parts[:2]) or "?").upper()


@register.filter
def upto(value, delimiter=","):
    """'3 hours, 12 minutes' -> '3 hours' (shorter timesince)."""
    return str(value).split(delimiter)[0]


@register.filter
def st_class(status):
    """Old Weststar One status pill colors."""
    return {"New": "st-new", "Open": "st-open", "In progress": "st-open", "Resolved": "st-res", "Closed": "st-closed"}.get(status, "st-pend")


@register.filter
def p_class(priority):
    return {"Critical": "p-crit", "High": "p-high", "Medium": "p-med"}.get(priority, "p-low")


@register.filter
def short_pri(priority):
    return {"Critical": "Crit", "Medium": "Med"}.get(priority, priority)


@register.filter
def avatar_color(pk):
    colors = ["#2c5cc5", "#12805c", "#a35b00", "#5a3fc0", "#0b6e8f", "#b83a8a", "#c2410c", "#0f766e"]
    try:
        return colors[int(pk or 0) % len(colors)]
    except (TypeError, ValueError):
        return colors[0]


@register.filter
def grid_status(status):
    """Grid tab a status belongs to: Open / In progress / Pending / Closed."""
    if status in ("New", "Open"):
        return "Open"
    if status in ("Resolved", "Closed"):
        return "Closed"
    return "In progress" if status == "In progress" else "Pending"


@register.filter
def hours(minutes):
    m = int(minutes or 0)
    return f"{m / 60:.2f}".rstrip("0").rstrip(".") + "h"


@register.filter
def split_pairs(value):
    """"a:A,b:B" → [("a", "A"), ("b", "B")] for small fixed option lists in templates."""
    return [tuple(p.split(":", 1)) for p in str(value).split(",") if ":" in p]


@register.filter
def can_flag(obj, perm):
    """{{ group|can_flag:"billing" }} → group.can_billing"""
    return bool(getattr(obj, f"can_{perm}", False)) if obj else False


@register.filter
def parse_iso(value):
    """'2026-10-24T21:00:00+00:00' (as stored in settings) → datetime, for |timesince."""
    from datetime import datetime
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


@register.filter
def tkg_st(status):
    """Old grid status dot class: open / prog / pend / closed."""
    return {"New": "open", "Open": "open", "In progress": "prog", "Resolved": "closed", "Closed": "closed"}.get(status, "pend")


@register.filter
def tkg_pri(priority):
    return {"Critical": "crit", "High": "high", "Medium": "med"}.get(priority, "low")


@register.filter
def first_name(name):
    return (str(name or "").split() or [""])[0]
