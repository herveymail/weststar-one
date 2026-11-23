"""Builds the wording of a client agreement from what was picked in the contract builder.

Two kinds:
- MSA: the Master Services Agreement on its own (the general terms; signed once per client).
- Managed: a Managed Services schedule — services covered, support hours, prices, term — either with the MSA terms
  attached (one signature covers both) or under an MSA the client already signed.

The result is saved into the contract's `scope` (the schedule) and `terms` (the MSA), which is what the client reads
and signs; the signature keeps a fingerprint of exactly that text.
"""
import re
from decimal import Decimal

from apps.core import legal
from apps.core.models import Setting

from . import contract_texts as T

ZERO = Decimal("0")


def _money(v) -> str:
    v = Decimal(v or 0)
    return f"${v:,.2f}".replace(".00", "")


def _dur(minutes: int) -> str:
    if minutes % 1440 == 0:
        d = minutes // 1440
        return f"{d} day{'s' if d != 1 else ''}"
    if minutes % 60 == 0:
        h = minutes // 60
        return f"{h} hour{'s' if h != 1 else ''}"
    return f"{minutes} minutes"


def _months(n) -> str:
    if not n:
        return "month to month"
    if n % 12 == 0:
        y = n // 12
        return f"{y} year{'s' if y != 1 else ''} ({n} months)"
    return f"{n} months"


def price_lines(c) -> list[tuple[str, Decimal]]:
    """The recurring price, line by line: (label, monthly amount)."""
    out = []
    for qty, rate, one, many in ((c.users, c.user_rate, "user", "users"), (c.workstations, c.workstation_rate, "computer", "computers"),
                                 (c.servers, c.server_rate, "server", "servers")):
        if qty and rate:
            out.append((f"{qty} {one if qty == 1 else many} × {_money(rate)} per {one} per month", Decimal(qty) * rate))
    if c.flat_fee:
        out.append(("Base monthly fee", c.flat_fee))
    return out


def monthly_total(c) -> Decimal:
    lines = price_lines(c)
    return sum((a for _l, a in lines), ZERO) if lines else (c.monthly_rate or ZERO)


def _fill(text: str, values: dict) -> str:
    return re.sub(r"\{([a-z_]+)\}", lambda m: str(values.get(m.group(1), m.group(0))), text)


def base_values(c) -> dict:
    v = legal.values(c.client, "msa")
    net = c.client.net_terms if c.client_id and c.client.net_terms is not None else int(Setting.get("billing.net_terms", "30") or 30)
    start = c.start_date
    v.update({
        "client": c.client.name, "company_short": v["company"], "notice_days": c.notice_days or 30,
        "effective_date": f"{start:%B %-d, %Y}" if start else "the date it is signed by both parties",
        "net_terms_text": f"within {net} days of the invoice date" if net else "when you receive them",
        "liability_months": Setting.get("legal.liability_months", "") or "12",
        "late_policy": v.get("late_policy") or "Balances not paid by the due date may be charged a late fee.",
    })
    return v


def msa_text(c) -> str:
    return _fill(legal.text("msa"), base_values(c)).strip()


def schedule_text(c) -> str:
    from apps.helpdesk import hours as H
    from apps.helpdesk import services as hd
    v = base_values(c)
    picked = [k for k in (c.services or [])]
    names = dict((k, (n, d)) for k, n, d in T.SERVICES)
    svc = [f"- {names[k][0]}: {names[k][1]}" for k, _n, _d in T.SERVICES if k in picked]
    svc += [f"- {ln.strip().lstrip('-').strip()}" for ln in (c.service_notes or "").splitlines() if ln.strip()]
    # support
    office = H.office_label()
    sup = [f"- Support hours: {office}, excluding public holidays." if office else "- Support hours: our normal business hours, excluding public holidays.",
           "- How to ask for help: the client portal, email " + (v.get("support_email") or "our support address") + (f", or phone {v['company_phone']}" if v.get("company_phone") else "") + "."]
    targets = ", ".join(f"{p} — {_dur(hd.response_minutes(p, None))}" for p in ("Critical", "High", "Medium", "Low"))
    sup.append(f"- Response targets, counted during support hours{' (Critical around the clock)' if Setting.get('tickets.sla_critical_247', 'true') != 'false' else ''}: {targets}.")
    sup.append("- Critical means your business cannot operate; High means a person or key system cannot work; Medium and Low are everything else.")
    if "after_hours" in picked:
        sup.append("- Emergency support outside support hours is included for issues that stop your business from operating.")
    elif c.after_hours_rate:
        sup.append("- Support outside support hours is available at the after-hours rate in Section 4.")
    # pricing
    lines, total = price_lines(c), monthly_total(c)
    pr = [f"- {label}: {_money(amt)} per month." for label, amt in lines] if len(lines) > 1 else []
    pr.append(f"- Monthly fee: {_money(total)}, billed in advance each month.")
    if c.setup_fee:
        pr.append(f"- One-time onboarding fee: {_money(c.setup_fee)}, due when this Schedule is signed.")
    if c.included_hours:
        pr.append(f"- The monthly fee includes up to {c.included_hours.normalize():f} hours of Covered Services per month. Unused hours do not carry over.")
    else:
        pr.append("- Covered Services are not metered: there is no hourly charge for them.")
    if c.overage_rate:
        pr.append(f"- Work that is not covered{' or beyond the included hours' if c.included_hours else ''}: {_money(c.overage_rate)} per hour during support hours.")
    if c.after_hours_rate:
        pr.append(f"- After-hours rate: {_money(c.after_hours_rate)} per hour outside support hours.")
    if c.trip_fee:
        pr.append(f"- Onsite trip charge: {_money(c.trip_fee)} per visit" + ("" if "onsite" in picked else " (onsite visits are not part of the Covered Services)") + ".")
    elif "onsite" not in picked:
        pr.append("- Onsite visits are not part of the Covered Services and are billed at the hourly rate.")
    # exclusions
    ex = [f"- {x}" for x in T.EXCLUSIONS] + [f"- {ln.strip().lstrip('-').strip()}" for ln in (c.exclusions or "").splitlines() if ln.strip()]
    # term
    if c.include_msa:
        msa_line = 'It is part of the Master Services Agreement between the parties that follows this Schedule (the "Agreement"); one signature covers both.'
    elif c.msa_id:
        sig = c.msa.signatures.order_by("created_at").first()
        when = f" signed {sig.created_at:%B %-d, %Y}" if sig else ""
        msa_line = f'It is a Schedule under the Master Services Agreement between the parties{when}{" (" + c.msa.number + ")" if c.msa.number else ""} (the "Agreement").'
    else:
        msa_line = f'It is governed by {v["company"]}\'s standard terms of service (the "Agreement").'
    renew = c.renewal_months or c.term_months or 12
    v.update({
        "msa_line": msa_line, "services": "\n".join(svc) or "- (no services picked yet)", "support": "\n".join(sup), "pricing": "\n".join(pr), "exclusions": "\n".join(ex),
        "start_text": f"{c.start_date:%B %-d, %Y}" if c.start_date else "the date this Schedule is signed",
        "term_text": _months(c.term_months),
        "renewal_text": (f"this Schedule renews automatically for successive terms of {_months(renew).split(' (')[0]}." if c.auto_renew and c.term_months
                         else "this Schedule continues month to month until either party ends it." if not c.term_months
                         else "this Schedule ends at the end of the initial term unless both parties agree in writing to renew it."),
        "increase_line": f"- At each renewal the monthly fee increases by {c.increase_pct.normalize():f}%." if c.increase_pct else "",
        "early_line": ("If you end this Schedule early without cause, the monthly fees for the rest of the current term become due." if c.term_months
                       else "Because this Schedule runs month to month, there is no early-termination charge."),
    })
    return re.sub(r"\n{3,}", "\n\n", _fill(T.MSP_SCHEDULE, v)).strip()


def build(c, save=True):
    """Write the agreement's wording (and the monthly total) from the builder fields."""
    from datetime import date
    if c.type == "MSA":
        c.scope, c.terms = "", msa_text(c)
        c.monthly_rate = None
    else:
        c.monthly_rate = monthly_total(c) or None
        c.scope = schedule_text(c)
        c.terms = msa_text(c) if c.include_msa else ""
        if c.start_date and c.term_months and not c.end_date:
            y, m = divmod(c.start_date.month - 1 + c.term_months, 12)
            try:
                c.end_date = date(c.start_date.year + y, m + 1, c.start_date.day) - __import__("datetime").timedelta(days=1)
            except ValueError:  # e.g. the 31st of a shorter month
                c.end_date = date(c.start_date.year + y, m + 1, 28)
    c.built = True
    if save:
        c.save()
    return c
