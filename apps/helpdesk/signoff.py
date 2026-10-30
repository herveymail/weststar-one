"""Customer sign-off on tickets — same rules as the old app (includes/ticket_signoff.php).

completion: break/fix clients confirm the work is done, their systems are working, and agree to the charges shown.
            A break/fix ticket can't be resolved or closed until there is one (Settings › Ticket settings).
dropoff:    the customer confirms they received the equipment listed.
The tech can override instead (customer not there, refused, remote job) by giving a reason; that's recorded too.
Each record keeps the exact statement agreed to, the figures, a SHA-256 of both, the drawn signature, who and when.
"""
import base64
import hashlib
import json
import struct
from decimal import ROUND_HALF_UP, Decimal

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from apps.core.models import Setting

from .models import DONE_STATUSES, Ticket, TicketMessage, TicketSignoff, TimeEntry, TicketTimer

CENT = Decimal("0.01")


class SignoffRequired(Exception):
    def __init__(self, ticket):
        super().__init__(f"{ticket.number} is a break/fix ticket: the customer has to sign off before it can be closed.")
        self.ticket = ticket


def is_breakfix(client) -> bool:
    if client is None:
        return False
    active = client.contracts.filter(status="Active", archived_at__isnull=True)
    if active.filter(type="Managed").exists() or (client.plan or "").startswith("Managed"):
        return False  # an active managed contract always wins
    return client.plan == "Break/fix" or active.filter(type="Break/fix").exists()


def has_completion(ticket) -> bool:
    return ticket.signoffs.filter(type="completion").exists()


def completion_required(ticket) -> bool:
    if Setting.get("tickets.signoff_breakfix_required", "true") == "false":
        return False
    return bool(ticket.client_id) and is_breakfix(ticket.client) and not has_completion(ticket)


def check_close(ticket, new_status: str) -> None:
    """Raise SignoffRequired if this change would close a break/fix ticket without a customer sign-off."""
    if new_status in DONE_STATUSES and ticket.status not in DONE_STATUSES and completion_required(ticket):
        raise SignoffRequired(ticket)


def _money(v) -> Decimal:
    return Decimal(str(v or 0)).quantize(CENT, ROUND_HALF_UP)


def charges(ticket) -> dict:
    minutes = ticket.time_entries.filter(billable=True).aggregate(m=Sum("minutes"))["m"] or 0
    for tm in TicketTimer.objects.filter(ticket=ticket):
        minutes += int((timezone.now() - tm.started_at).total_seconds() // 60)
    rate = ticket.client.hourly_rate if ticket.client_id and ticket.client.hourly_rate else None
    if not rate:
        try:
            rate = Decimal(Setting.get("billing.hourly_rate", "0") or "0")
        except ArithmeticError:
            rate = Decimal(0)
    tax = ticket.client.tax_rate if ticket.client_id and ticket.client.tax_rate is not None else None
    if tax is None:
        try:
            tax = Decimal(Setting.get("billing.default_tax_rate", "0") or "0")
        except ArithmeticError:
            tax = Decimal(0)
    return {"hours": (Decimal(minutes) / 60).quantize(CENT, ROUND_HALF_UP), "rate": _money(rate), "tax_rate": Decimal(str(tax)).quantize(Decimal("0.001"))}


def total(hours, rate, parts, tax_rate) -> Decimal:
    """In whole cents, the same way the sign-off page works it out on screen."""
    sub_c = int((Decimal(hours) * Decimal(rate) * 100).quantize(Decimal(1), ROUND_HALF_UP)) + int((Decimal(parts) * 100).quantize(Decimal(1), ROUND_HALF_UP))
    tax_c = int((Decimal(sub_c) * (Decimal(tax_rate) * 100).quantize(Decimal(1), ROUND_HALF_UP) / 10000).quantize(Decimal(1), ROUND_HALF_UP))
    return (Decimal(sub_c + tax_c) / 100).quantize(CENT)


def _trim(n) -> str:
    s = f"{Decimal(n):.2f}".rstrip("0").rstrip(".")
    return s or "0"


def statement(kind: str, fig: dict) -> str:
    co = Setting.get("company.name", "") or "Weststar MSP"
    if kind == "dropoff":
        return f"I confirm that I received the items listed above from {co} in good condition."
    h = Decimal(fig["hours"])
    charges_txt = (f"${fig['total']:,.2f} ({_trim(h)} hour{'' if h == 1 else 's'} at ${fig['rate']:,.2f}/hour"
                   + (f", plus ${fig['parts_amount']:,.2f} for {fig['parts_desc'] or 'parts/materials'}" if fig["parts_amount"] > 0 else "")
                   + (f", plus {_trim(fig['tax_rate'])}% tax" if fig["tax_rate"] > 0 else "") + ")")
    return ("I confirm that the work described above has been completed, that my computers, systems and equipment are working "
            f"the same as before or better, and I agree to the charges of {charges_txt}.")


def signature_ok(data_url: str) -> bool:
    """A real PNG drawing of sensible size: data:image/png;base64,… only."""
    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix) or len(data_url) > 700_000:
        return False
    try:
        raw = base64.b64decode(data_url[len(prefix):], validate=True)
    except ValueError:
        return False
    if len(raw) < 100 or raw[:8] != b"\x89PNG\r\n\x1a\n" or raw[12:16] != b"IHDR":
        return False
    w, h = struct.unpack(">II", raw[16:24])
    return 20 <= w <= 4000 and 20 <= h <= 2000


def record(ticket: Ticket, data: dict, user, ip: str = "") -> tuple[TicketSignoff | None, str]:
    """Save a sign-off (signed or overridden). Returns (signoff, '') or (None, error)."""
    kind = "dropoff" if data.get("type") == "dropoff" else "completion"
    override = bool(data.get("override"))
    reason = (data.get("override_reason") or "").strip()[:1000]
    name = (data.get("signer_name") or "").strip()[:200]
    title = (data.get("signer_title") or "").strip()[:100]
    email = (data.get("signer_email") or "").strip().lower()[:200]
    sig = data.get("signature") or ""
    summary = (data.get("summary") or "").strip()[:4000]
    items = (data.get("items") or "").strip()[:4000]
    if kind == "dropoff" and not items:
        return None, "List what was dropped off."
    if override:
        if len(reason) < 8:
            return None, "Give a reason for the override (at least a few words)."
    else:
        if not name:
            return None, "The customer needs to type their name."
        if not signature_ok(sig):
            return None, "The signature couldn't be read. Ask the customer to sign again."
        from django.core.validators import validate_email
        try:
            validate_email(email) if email else None
        except Exception:  # noqa: BLE001
            email = ""
    ch = charges(ticket)
    try:
        hours = max(Decimal(0), _money(data.get("hours"))) if str(data.get("hours") or "").strip() else ch["hours"]
        parts = max(Decimal(0), _money(data.get("parts_amount")))
    except ArithmeticError:
        return None, "Hours and parts must be numbers."
    parts_desc = (data.get("parts_desc") or "").strip()[:255]
    fig = {"hours": hours, "rate": ch["rate"], "parts_amount": parts, "parts_desc": parts_desc, "tax_rate": ch["tax_rate"]}
    fig["total"] = total(hours, ch["rate"], parts, ch["tax_rate"])
    stmt = "" if override else statement(kind, fig)
    digest = hashlib.sha256(json.dumps([ticket.pk, kind, summary, items, {k: str(v) for k, v in fig.items()}, stmt, name, sig]).encode()).hexdigest()
    done = kind == "completion"
    with transaction.atomic():
        so = TicketSignoff.objects.create(
            ticket=ticket, type=kind, signer_name="" if override else name, signer_title="" if override else title,
            signer_email="" if override else email, signature="" if override else sig, summary=summary, items=items,
            hours=hours if done else None, rate=ch["rate"] if done else None, parts_desc=parts_desc if done else "",
            parts_amount=parts if done else None, tax_rate=ch["tax_rate"] if done else None, total=fig["total"] if done else None,
            statement=stmt, hash=digest, overridden=override, override_reason=reason if override else "", user=user, ip=ip[:45])
        if done and not override:
            _bill_signed_hours(ticket, hours, user)
        label = "Completion sign-off" if done else "Drop-off sign-off"
        if override:
            note = f"✍️ {label} OVERRIDDEN by {user.name} — reason: {reason}" + (f"\nItems: {items}" if items else "")
        else:
            note = (f"✍️ {label} signed by {name}" + (f" ({title})" if title else "") + f" on {timezone.localtime():%b %-d, %Y %-I:%M %p}"
                    + (f" — agreed to ${fig['total']:,.2f} ({_trim(hours)} h)" if done else "") + (f"\nItems: {items}" if items else "") + f'\n"{stmt}"')
        TicketMessage.objects.create(ticket=ticket, kind="note", body=note, author=user, author_name=user.name, via="web")
    if not override and (email or ticket.contact_email):
        transaction.on_commit(lambda: _email_copy(email or ticket.contact_email, ticket, so))
    return so, ""


def _bill_signed_hours(ticket, hours: Decimal, user):
    """Billing follows what the customer agreed to: a running timer is folded in, and extra signed time is logged."""
    for tm in TicketTimer.objects.filter(ticket=ticket):
        tm.delete()  # its time is already counted in the signed hours
    logged = ticket.time_entries.filter(billable=True).aggregate(m=Sum("minutes"))["m"] or 0
    signed = int((hours * 60).quantize(Decimal(1), ROUND_HALF_UP))
    if signed > logged:
        TimeEntry.objects.create(ticket=ticket, user=user, minutes=signed - logged, work_type="On-site", billable=True,
                                 description="Time agreed on the customer sign-off", work_date=timezone.localdate())
    elif signed < logged:
        TicketMessage.objects.create(ticket=ticket, kind="note", author=user, author_name=user.name, via="web",
                                     body=f"Heads-up: the customer signed for {_trim(hours)} h but {_trim(Decimal(logged) / 60)} h is logged. Adjust the time before invoicing.")


def _email_copy(to, ticket, so):
    from apps.core import mail
    mail.send(to, f"Your signed copy — {ticket.number}", "email/signoff_copy", {"t": ticket, "so": so}, background=True)
