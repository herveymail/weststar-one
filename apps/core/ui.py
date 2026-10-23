"""Small display helpers shared by views and templates."""
import re
from decimal import Decimal

from django.db import models
from django.utils import timezone
from django.utils.formats import date_format

from .models import EncryptedField

PRIORITY_CLASS = {"Critical": "crit", "High": "high", "Medium": "med", "Low": ""}


def tone(value) -> str:
    x = str(value or "").lower()
    if re.search(r"overdue|failed|critical|offline|expired|breach|terminated|denied|lost|void", x):
        return "bad"
    if re.fullmatch(r"paid|active|valid|ok|success|accepted|signed|complete|approved|matched|current|won|renewed|portal", x):
        return "good"
    if re.search(r"pending|draft|sent|viewed|expiring|planning|in progress|paused|review|unmatched|not started|proposal|negotiation|waiting|warning|on hold|partial|upcoming|onboarding|submitted|scheduled|unread", x):
        return "warn"
    if re.fullmatch(r"new|open|contacted|qualified|running", x):
        return "info"
    return ""


def status_class(status: str) -> str:
    return {"New": "med", "Open": "accent", "Scheduled": "med"}.get(status, "high" if "Waiting" in status else "")


def field_label(model, name: str) -> str:
    f = model._meta.get_field(name)
    return str(f.verbose_name)[:1].upper() + str(f.verbose_name)[1:]


def cell(obj, name: str) -> dict:
    """{'text', 'kind'} for one list cell. kind: pill | money | num | muted | link | secret | text"""
    f = obj._meta.get_field(name)
    v = getattr(obj, name)
    if isinstance(f, EncryptedField):
        return {"text": "●●●●" if v else "—", "kind": "muted"}
    if v is None or v == "":
        return {"text": "—", "kind": "muted"}
    if f.choices and (name in ("status", "stage", "match_status", "last_result", "visibility", "ssl_status")):
        return {"text": v, "kind": "pill", "tone": tone(v)}
    if isinstance(f, models.DecimalField):
        if "rate" in name or name in ("total", "amount", "cost", "price", "value", "monthly_rate", "subtotal", "tax_amount", "amount_paid", "hourly_rate", "overage_rate"):
            return {"text": money(v), "kind": "num"}
        return {"text": f"{Decimal(v).normalize():,f}", "kind": "num"}
    if isinstance(f, (models.IntegerField, models.PositiveIntegerField, models.BigIntegerField)):
        return {"text": f"{v:,}", "kind": "num"}
    if isinstance(f, models.DateTimeField):
        return {"text": date_format(timezone.localtime(v), "M j, Y g:i A"), "kind": "text"}
    if isinstance(f, models.DateField):
        return {"text": date_format(v, "M j, Y"), "kind": "text"}
    if isinstance(f, models.BooleanField):
        return {"text": "Yes" if v else "No", "kind": "text"}
    if isinstance(f, models.URLField):
        return {"text": re.sub(r"^https?://", "", v), "kind": "url", "href": v}
    return {"text": str(v), "kind": "text"}


def money(v) -> str:
    if v is None or v == "":
        return "—"
    d = Decimal(v)
    return f"-${abs(d):,.2f}" if d < 0 else f"${d:,.2f}"
