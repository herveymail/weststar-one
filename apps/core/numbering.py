"""Record numbers (tickets, invoices, quotes, contracts, projects): prefix + zero-padded counter,
both editable in Settings › Numbers. Imported records keep their old numbers."""
from .models import Counter, Setting

DEFAULTS = {"ticket": ("T-", 10001), "invoice": ("INV-", 1001), "quote": ("QT-", 1001), "contract": ("CT-", 1001), "project": ("PRJ-", 1001)}
COUNTER = {"ticket": "ticket", "invoice": "invoices", "quote": "quotes", "contract": "contracts", "project": "projects"}


def prefix(kind: str) -> str:
    return Setting.get(f"numbers.{kind}_prefix", "") or DEFAULTS[kind][0]


def next_number(kind: str) -> str:
    try:
        pad = max(0, min(int(Setting.get(f"numbers.{kind}_padding", "") or 0), 12))
    except ValueError:
        pad = 0
    n = Counter.next(COUNTER[kind], DEFAULTS[kind][1])
    return f"{prefix(kind)}{str(n).zfill(pad)}"
