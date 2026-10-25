"""Friendlier controls for settings: preset choices, time pickers, day chips,
colour swatches, tag lists and $ / % inputs.

Keyed by setting key so the catalog stays a plain list. Each entry is a dict:
  kind   — preset | time | days | tz | color | money | pct | tags | suggest | segment | cards | theme | state
  presets — [(value, label)] for preset / color / suggest
  unit   — shown after the input (preset/custom)
  sep    — "\\n" or ", " for tags
"""
import re
import zoneinfo

CUSTOM = "__custom__"
DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _mins(*vals):
    out = []
    for v in vals:
        if v < 60:
            out.append((str(v), f"{v} minutes"))
        elif v % 60 == 0:
            h = v // 60
            out.append((str(v), f"{h} hour{'s' if h != 1 else ''}"))
        else:
            out.append((str(v), f"{v // 60} h {v % 60} min"))
    return out


def _n(unit, *vals):
    single = unit[:-1] if unit.endswith("s") else unit
    return [(str(v), f"{v} {single if v == 1 else unit}") for v in vals]


US_STATES = ["Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut", "Delaware", "District of Columbia", "Florida", "Georgia",
             "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa", "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan", "Minnesota",
             "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire", "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota",
             "Ohio", "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota", "Tennessee", "Texas", "Utah", "Vermont", "Virginia",
             "Washington", "West Virginia", "Wisconsin", "Wyoming"]

COMMON_TZ = [
    ("America/Phoenix", "Arizona (no daylight saving)"),
    ("America/Denver", "Mountain time (Denver)"),
    ("America/Los_Angeles", "Pacific time (Los Angeles)"),
    ("America/Chicago", "Central time (Chicago)"),
    ("America/New_York", "Eastern time (New York)"),
    ("America/Anchorage", "Alaska"),
    ("Pacific/Honolulu", "Hawaii"),
    ("UTC", "UTC"),
]

BRAND_COLORS = [("#0A4B85", "Weststar blue"), ("#4F46E5", "Indigo"), ("#0E7490", "Teal"), ("#15803D", "Green"), ("#7C3AED", "Violet"),
                ("#BE123C", "Red"), ("#C2410C", "Orange"), ("#334155", "Slate"), ("#111827", "Black")]

PORTS_SMTP = [("587", "587 · STARTTLS (recommended)"), ("465", "465 · SSL"), ("25", "25 · plain"), ("2525", "2525 · alternate")]
PORTS_IMAP = [("993", "993 · SSL (recommended)"), ("143", "143 · STARTTLS")]

WIDGETS = {
    # General
    "app.timezone": {"kind": "tz"},
    "brand.color": {"kind": "color", "presets": BRAND_COLORS},
    "app.default_look": {"kind": "theme"},
    "numbers.ticket_padding": {"kind": "preset", "presets": [("0", "No padding (T-917)"), ("4", "4 digits (T-0917)"), ("5", "5 digits (T-00917)"), ("6", "6 digits (T-000917)")]},
    "numbers.invoice_padding": {"kind": "preset", "presets": [("0", "No padding"), ("4", "4 digits (0042)"), ("5", "5 digits (00042)"), ("6", "6 digits (000042)")]},
    "numbers.quote_padding": {"kind": "preset", "presets": [("0", "No padding"), ("4", "4 digits (0042)"), ("5", "5 digits (00042)"), ("6", "6 digits (000042)")]},
    "billing.default_tax_rate": {"kind": "pct"},
    "billing.hourly_rate": {"kind": "money", "unit": "/ hour"},
    "billing.mileage_rate": {"kind": "money", "unit": "/ mile"},
    "billing.net_terms": {"kind": "preset", "presets": [("0", "Due on receipt"), ("7", "Net 7"), ("10", "Net 10"), ("15", "Net 15"), ("30", "Net 30"), ("45", "Net 45"), ("60", "Net 60")], "unit": "days"},
    # Helpdesk
    "tickets.categories": {"kind": "tags", "sep": "\n", "placeholder": "Add a category"},
    "tickets.work_types": {"kind": "tags", "sep": "\n", "placeholder": "Add a work type"},
    "tickets.alert_senders": {"kind": "tags", "sep": "\n", "placeholder": "alerts@datto.com or datto.com"},
    "tickets.email_priority": {"kind": "segment"},
    "tickets.auto_close_days": {"kind": "preset", "presets": [("0", "Never")] + _n("days", 1, 2, 3, 5, 7, 14, 30), "unit": "days"},
    "tickets.sla_critical_min": {"kind": "preset", "presets": _mins(15, 30, 60, 120), "unit": "minutes"},
    "tickets.sla_high_min": {"kind": "preset", "presets": _mins(30, 60, 120, 240), "unit": "minutes"},
    "tickets.sla_medium_min": {"kind": "preset", "presets": _mins(60, 120, 240, 480), "unit": "minutes"},
    "tickets.sla_low_min": {"kind": "preset", "presets": _mins(240, 480, 1440, 2880), "unit": "minutes"},
    "tickets.resolve_critical_hours": {"kind": "preset", "presets": _n("hours", 2, 4, 8, 24), "unit": "hours"},
    "tickets.resolve_high_hours": {"kind": "preset", "presets": _n("hours", 4, 8, 24, 48), "unit": "hours"},
    "tickets.resolve_medium_hours": {"kind": "preset", "presets": _n("hours", 24, 48, 72, 120), "unit": "hours"},
    "tickets.resolve_low_hours": {"kind": "preset", "presets": _n("hours", 48, 72, 120, 240), "unit": "hours"},
    "helpdesk.open": {"kind": "time"},
    "helpdesk.close": {"kind": "time"},
    "helpdesk.days": {"kind": "days"},
    "portal.reopen_hours": {"kind": "preset", "presets": [("0", "Never")] + _n("hours", 24, 48, 72) + [("168", "1 week")], "unit": "hours"},
    "email.imap_host": {"kind": "suggest", "presets": [("imap.gmail.com", "Google Workspace / Gmail"), ("outlook.office365.com", "Microsoft 365")]},
    "email.imap_port": {"kind": "preset", "presets": PORTS_IMAP},
    "email.imap_folder": {"kind": "suggest", "presets": [("INBOX", "Inbox"), ("[Gmail]/All Mail", "All Mail")]},
    # Email
    "email.smtp_host": {"kind": "suggest", "presets": [("smtp.gmail.com", "Google Workspace / Gmail"), ("smtp-relay.gmail.com", "Google SMTP relay"), ("smtp.office365.com", "Microsoft 365"), ("mail.smtp2go.com", "SMTP2GO")]},
    "email.smtp_port": {"kind": "preset", "presets": PORTS_SMTP},
    # Billing
    "billing.currency_symbol": {"kind": "preset", "presets": [("$", "$ · US dollar"), ("C$", "C$ · Canadian dollar"), ("€", "€ · Euro"), ("£", "£ · Pound")]},
    "billing.tax_label": {"kind": "preset", "presets": [("Tax", "Tax"), ("Sales tax", "Sales tax"), ("TPT", "TPT (Arizona)"), ("GST", "GST"), ("VAT", "VAT")]},
    "billing.reminder_days": {"kind": "preset", "presets": [("0", "Don't send")] + _n("days", 3, 7, 14, 30), "unit": "days after due"},
    "billing.afterhours_rate": {"kind": "money", "unit": "/ hour"},
    "billing.afterhours_minimum": {"kind": "money"},
    "billing.late_fee_type": {"kind": "cards"},
    "billing.late_fee_flat": {"kind": "money"},
    "billing.late_fee_pct": {"kind": "pct", "unit": "% / month"},
    "billing.late_fee_grace_days": {"kind": "preset", "presets": [("0", "Any day past due")] + [(str(v), f"{v} days past due") for v in (5, 10, 15, 30)], "unit": "days past due"},
    "billing.quote_valid_days": {"kind": "preset", "presets": _n("days", 7, 14, 30, 60, 90), "unit": "days"},
    "billing.quote_deposit_pct": {"kind": "preset", "presets": [("0", "No deposit"), ("25", "25%"), ("50", "50%"), ("100", "100% up front")], "unit": "%"},
    "billing.contract_months": {"kind": "preset", "presets": [("1", "Month to month"), ("12", "12 months"), ("24", "24 months"), ("36", "36 months")], "unit": "months"},
    "billing.contract_notice_days": {"kind": "preset", "presets": _n("days", 30, 60, 90), "unit": "days"},
    "billing.contract_early_term_pct": {"kind": "preset", "presets": [("0", "None"), ("25", "25%"), ("50", "50%"), ("75", "75%"), ("100", "100%")], "unit": "%"},
    "billing.contract_state": {"kind": "state"},
    "billing.policy_review_months": {"kind": "preset", "presets": [("6", "Every 6 months"), ("12", "Every year"), ("24", "Every 2 years")], "unit": "months"},
    "autopay.retry_days": {"kind": "preset", "presets": _n("days", 1, 2, 3, 5, 7), "unit": "days"},
    "autopay.max_attempts": {"kind": "preset", "presets": [("1", "Once (no retries)")] + [(str(v), f"{v} tries") for v in (2, 3, 4, 5)], "unit": "tries"},
    # People
    "google.domains": {"kind": "tags", "sep": ", ", "placeholder": "weststarmsp.com"},
    "security.idle_minutes": {"kind": "preset", "presets": _mins(15, 30, 60, 120, 240, 480), "unit": "minutes"},
    # MSP360
    "msp360.ticket_priority": {"kind": "segment"},
    "msp360.queue": {"kind": "queue"},
    "msp360.overdue_hours": {"kind": "preset", "presets": _n("hours", 24, 36, 48, 72), "unit": "hours"},
    "msp360.base_url": {"kind": "suggest", "presets": [("https://api.mspbackups.com", "MSP360 (standard)")]},
    # AI
    "ai.provider": {"kind": "cards"},
    "ai.first_response_skip": {"kind": "tags", "sep": ", ", "placeholder": "Add a word"},
    "backup.s3_endpoint": {"kind": "suggest", "presets": [("https://s3.us-west-1.wasabisys.com", "Wasabi us-west-1"), ("https://s3.us-east-1.wasabisys.com", "Wasabi us-east-1"), ("https://s3.us-central-1.wasabisys.com", "Wasabi us-central-1")]},
}

# Friendly names for select values that are stored as codes.
LABELS = {
    "flat": "Flat amount", "percent": "Percent of balance",
    "none": "Off", "gemini": "Google Gemini", "anthropic": "Anthropic Claude", "openai": "OpenAI", "ollama": "Ollama (self-hosted)",
    "immediate": "Right away", "due_date": "On the due date", "always": "Always", "after_hours": "Only after hours",
    "everyone": "Everyone", "admins": "Admins only", "privileged": "Admins & managers", "nobody": "Nobody", "yes": "Yes", "no": "No",
}

HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
NUM = re.compile(r"^\d+(\.\d{1,4})?$")


def tz_groups():
    common = [v for v, _ in COMMON_TZ]
    rest = sorted(z for z in zoneinfo.available_timezones() if "/" in z and not z.startswith(("Etc/", "SystemV/", "posix/", "right/")) and z not in common)
    return [("Common", COMMON_TZ), ("All time zones", [(z, z.replace("_", " ")) for z in rest])]


def decorate(f: dict) -> dict:
    """Add display info (choices, widget) to a field spec that already has a value."""
    w = WIDGETS.get(f["key"], {})
    kind = w.get("kind", "")
    value = f.get("value", "")
    f["w"] = kind
    if kind and kind not in ("money", "pct", "suggest"):
        # The control itself now shows the format, so drop "(e.g. 07:00)", "(one per line)", "(days)"…
        f["label"] = re.sub(r"\s*\((e\.g\.|one |comma|days|minutes|hours|24-hour)[^)]*\)", "", f["label"]).strip()
    f["unit"] = w.get("unit", "")
    if f["type"] == "select":
        f["choices"] = [(o, LABELS.get(o, o)) for o in f["options"]]
    if kind in ("preset", "color", "suggest"):
        presets = list(w["presets"])
        f["choices"] = presets
        f["is_custom"] = bool(value) and value not in [p for p, _ in presets]
        f["unit"] = w.get("unit", "")
    elif kind == "tags":
        sep = w.get("sep", "\n")
        parts = value.replace(",", "\n").splitlines() if sep != "\n" else value.splitlines()
        f["tags"] = [p.strip() for p in parts if p.strip()]
        f["placeholder"] = w.get("placeholder", "")
    elif kind == "days":
        on = {d.strip()[:3].title() for d in (value or "Mon,Tue,Wed,Thu,Fri").split(",") if d.strip()}
        f["days"] = [(d, d in on) for d in DAYS]
    elif kind == "tz":
        f["groups"] = tz_groups()
    elif kind == "state":
        f["choices"] = [(s, s) for s in US_STATES]
    elif kind == "queue":
        from apps.helpdesk.models import Queue
        f["choices"] = [("", "Use queue routing rules")] + [(str(q.pk), q.name) for q in Queue.objects.all()]
    elif kind == "theme":
        from .themes import THEMES
        f["themes"] = THEMES
    return f


def read(f: dict, post) -> tuple[str | None, str]:
    """Pull a value for a widget field from the form. Returns (value, error).
    value None means 'not a widget field — use the normal path'."""
    w = WIDGETS.get(f["key"], {})
    kind = w.get("kind", "")
    key = f["key"]
    if kind == "tags":
        items = [x.strip() for x in post.getlist(key) if x.strip()]
        for line in post.get(key + "__add", "").replace(",", "\n").splitlines():
            if line.strip():
                items.append(line.strip())
        seen, out = set(), []
        for x in items:
            if x.lower() not in seen:
                seen.add(x.lower())
                out.append(x)
        return w.get("sep", "\n").join(out), ""
    if kind == "days":
        picked = [d for d in DAYS if d in post.getlist(key)]
        return ",".join(picked), ""
    if kind == "queue":
        raw = post.get(key, "").strip()
        return (raw if raw.isdigit() or raw == "" else None), ("" if raw.isdigit() or raw == "" else f"{f['label']}: pick a queue.")
    if kind not in ("preset", "color", "time", "tz", "money", "pct", "state", "suggest"):
        return None, ""
    raw = post.get(key, "").strip()
    if raw == CUSTOM:
        raw = post.get(key + "__custom", "").strip()
    if not raw:
        return "", ""
    label = f["label"]
    if kind == "color" and not HEX.match(raw):
        return None, f"{label}: use a colour like #0A4B85."
    if kind == "time" and not re.match(r"^([01]\d|2[0-3]):[0-5]\d$", raw):
        return None, f"{label}: pick a time."
    if kind == "tz":
        try:
            zoneinfo.ZoneInfo(raw)
        except (zoneinfo.ZoneInfoNotFoundError, ValueError):
            return None, f"{label}: pick a time zone from the list."
    if kind in ("money", "pct"):
        raw = raw.lstrip("$").rstrip("%").replace(",", "").strip()
        if not NUM.match(raw):
            return None, f"{label} must be a number."
    if kind == "preset" and f["type"] == "int" and not raw.isdigit():
        return None, f"{label} must be a whole number."
    if kind == "state" and raw not in US_STATES:
        return None, f"{label}: pick a state."
    return raw, ""
