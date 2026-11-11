"""Billing › Ready to bill: everything done but not invoiced yet, grouped by client, turned into draft invoices in one click.

What counts:
- ticket time: billable entries on billable tickets that aren't on an invoice yet, up to the "through" date
- billable mileage that isn't on an invoice yet
- parts from customer sign-offs (Work completed, not overridden) that aren't on an invoice yet

Rates: the client's hourly rate, else Settings › Billing › Default hourly rate; mileage at the mileage rate.
Managed clients are listed but left unticked — their time is usually covered by the contract; tick them to bill extra time.
"""
from collections import OrderedDict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.utils import timezone

from apps.core.models import Setting

CENT = Decimal("0.01")


def _dec(key, default="0"):
    try:
        return Decimal(Setting.get(key, default) or default)
    except Exception:  # noqa: BLE001
        return Decimal(default)


def collect(through=None, client_ids=None) -> list[dict]:
    from apps.helpdesk.models import TicketSignoff, TimeEntry
    from apps.helpdesk.signoff import is_breakfix
    from apps.tools.models import MileageTrip

    through = through or timezone.localdate()
    te = (TimeEntry.objects.filter(billable=True, invoice__isnull=True, ticket__billable=True, ticket__client__isnull=False, work_date__lte=through)
          .select_related("ticket", "ticket__client", "user").order_by("ticket__client__name", "ticket_id", "work_date"))
    mi = (MileageTrip.objects.filter(billable=True, invoice__isnull=True, client__isnull=False, archived_at__isnull=True, trip_date__lte=through)
          .select_related("client").order_by("trip_date"))
    so = (TicketSignoff.objects.filter(type="completion", overridden=False, invoice__isnull=True, parts_amount__gt=0, ticket__client__isnull=False,
                                       created_at__date__lte=through).select_related("ticket", "ticket__client"))
    if client_ids is not None:
        te, mi, so = te.filter(ticket__client_id__in=client_ids), mi.filter(client_id__in=client_ids), so.filter(ticket__client_id__in=client_ids)
    default_rate, mile_rate = _dec("billing.hourly_rate"), _dec("billing.mileage_rate")
    out: "OrderedDict[int, dict]" = OrderedDict()

    def group(c):
        if c.pk not in out:
            managed = (c.plan or "").startswith("Managed") and not is_breakfix(c)
            out[c.pk] = {"client": c, "rate": c.hourly_rate or default_rate, "managed": managed, "tickets": OrderedDict(), "time": [], "miles": [],
                         "parts": [], "minutes": 0, "mi": Decimal(0), "labor": Decimal(0), "mileage": Decimal(0), "parts_total": Decimal(0), "oldest": None}
        return out[c.pk]

    for e in te:
        g = group(e.ticket.client)
        g["time"].append(e)
        g["minutes"] += e.minutes
        t = g["tickets"].setdefault(e.ticket_id, {"ticket": e.ticket, "minutes": 0, "types": OrderedDict()})
        t["minutes"] += e.minutes
        t["types"][e.work_type] = t["types"].get(e.work_type, 0) + e.minutes
        g["oldest"] = min(filter(None, [g["oldest"], e.work_date]))
    for m in mi:
        g = group(m.client)
        g["miles"].append(m)
        g["mi"] += m.miles
        g["oldest"] = min(filter(None, [g["oldest"], m.trip_date]))
    for s in so:
        g = group(s.ticket.client)
        g["parts"].append(s)
        g["parts_total"] += s.parts_amount
    for g in out.values():
        g["labor"] = (Decimal(g["minutes"]) / 60 * g["rate"]).quantize(CENT, ROUND_HALF_UP)
        g["mileage"] = (g["mi"] * mile_rate).quantize(CENT, ROUND_HALF_UP)
        g["total"] = g["labor"] + g["mileage"] + g["parts_total"]
        g["hours"] = Decimal(g["minutes"]) / 60
        g["tickets"] = list(g["tickets"].values())
        g["preselect"] = not g["managed"] and g["total"] > 0
    return sorted(out.values(), key=lambda g: (g["managed"], g["client"].name.lower()))


def _hours(minutes) -> Decimal:
    return (Decimal(minutes) / 60).quantize(CENT, ROUND_HALF_UP)


def create_drafts(client_ids, through, user=None) -> list:
    """One draft invoice per client. Everything put on it is linked, so it can't be billed twice."""
    from apps.core.numbering import next_number
    from apps.helpdesk.models import TicketSignoff, TimeEntry
    from apps.tools.models import MileageTrip

    from .models import Invoice, InvoiceLine

    made = []
    labor_tax = Setting.get("billing.labor_taxable", "no") == "yes"
    tax = _dec("billing.default_tax_rate")
    mile_rate = _dec("billing.mileage_rate")
    today = timezone.localdate()
    with transaction.atomic():
        for g in collect(through, client_ids):
            # Lock what we're billing so two people clicking at once can't bill it twice.
            ids = [e.pk for e in g["time"]]
            locked = set(TimeEntry.objects.select_for_update().filter(pk__in=ids, invoice__isnull=True).values_list("pk", flat=True))
            if len(locked) != len(ids) or (not g["time"] and not g["miles"] and not g["parts"]):
                continue
            c = g["client"]
            first = g["oldest"] or today
            inv = Invoice.objects.create(number=next_number("invoice"), client=c, status="Draft", invoice_date=today,
                                         due_date=today + timedelta(days=c.net_terms or int(Setting.get("billing.net_terms", "30") or 30)),
                                         tax_rate=c.tax_rate if getattr(c, "tax_rate", None) is not None else tax,
                                         scope=f"Services {first:%b %-d} – {through:%b %-d, %Y}", created_by=user)
            n = 0
            for t in g["tickets"]:
                kinds = ", ".join(f"{k} {_hours(m).normalize():f} h" for k, m in t["types"].items())
                InvoiceLine.objects.create(invoice=inv, description=f"{t['ticket'].number} · {t['ticket'].subject}"[:440] + f" ({kinds})",
                                           qty=_hours(t["minutes"]), rate=g["rate"], taxable=labor_tax, sort_order=n)
                n += 1
            if g["miles"]:
                InvoiceLine.objects.create(invoice=inv, description=f"Mileage ({len(g['miles'])} trip{'s' if len(g['miles']) != 1 else ''})",
                                           qty=g["mi"], rate=mile_rate, taxable=False, sort_order=n)
                n += 1
            for s in g["parts"]:
                InvoiceLine.objects.create(invoice=inv, description=f"Parts — {s.parts_desc or 'parts'} ({s.ticket.number})"[:500], qty=1,
                                           rate=s.parts_amount, taxable=True, sort_order=n)
                n += 1
            inv.recalc()
            TimeEntry.objects.filter(pk__in=ids).update(invoice=inv)
            MileageTrip.objects.filter(pk__in=[m.pk for m in g["miles"]]).update(invoice=inv)
            TicketSignoff.objects.filter(pk__in=[s.pk for s in g["parts"]]).update(invoice=inv)
            made.append(inv)
    return made


def no_charge(client_id, through) -> int:
    """Mark a client's waiting time as not billable (e.g. covered by their contract) so it leaves the list."""
    from apps.helpdesk.models import TimeEntry
    from apps.tools.models import MileageTrip
    n = TimeEntry.objects.filter(ticket__client_id=client_id, billable=True, invoice__isnull=True, work_date__lte=through).update(billable=False)
    n += MileageTrip.objects.filter(client_id=client_id, billable=True, invoice__isnull=True, trip_date__lte=through).update(billable=False)
    return n
