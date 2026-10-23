"""Email → tickets. Reads the support mailbox (Google Workspace over IMAP with an app password, like the
old app) and turns each new email into a ticket, or adds it to the ticket it answers.

How a reply finds its ticket, in order:
  1. In-Reply-To / References point at an email we sent (our Message-IDs carry the ticket id),
     or at an email already filed on a ticket.
  2. The ticket number is in the subject (e.g. "Re: [ITDS-00918] Printer" or "ITDS-00918 – Printer").
Otherwise it's a new ticket, matched to a client by the sender's email (contact) or email domain.

Never turned into tickets: our own mailbox's mail, auto-replies / out-of-office, bounces and bulk mail.
"""
import email
import html
import imaplib
import logging
import re
import socket
from email import policy
from email.utils import getaddresses, parseaddr

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from apps.core.models import Setting

from .models import InboundEmail, Ticket

log = logging.getLogger("weststar.inbound")
MAX_PER_RUN = 50
OUR_ID = re.compile(r"<ws1\.t(\d+)\.[0-9a-f]+@", re.I)
SKIP_SENDERS = re.compile(r"^(mailer-daemon|postmaster|no-?reply|donotreply|do-not-reply)@", re.I)
QUOTE_STARTS = [
    re.compile(r"^\s*On .{5,200}wrote:\s*$", re.I | re.M),
    re.compile(r"^\s*-{2,}\s*Original Message\s*-{2,}", re.I | re.M),
    re.compile(r"^\s*From:\s.+\n\s*(Sent|Date):\s", re.I | re.M),
    re.compile(r"^\s*_{10,}\s*$", re.M),
    re.compile(r"^\s*Sent from my (iPhone|iPad|Android|Samsung)", re.I | re.M),
]


def enabled() -> bool:
    return Setting.get("email.fetch_enabled", "false") == "true" and bool(Setting.get("email.imap_user") and Setting.get("email.imap_password"))


def _connect():
    host = Setting.get("email.imap_host") or "imap.gmail.com"
    port = int(Setting.get("email.imap_port") or 993)
    conn = imaplib.IMAP4_SSL(host, port, timeout=30)
    conn.login(Setting.get("email.imap_user"), Setting.get("email.imap_password"))
    return conn


def test_connection() -> str:
    """'' when it works, otherwise the problem in plain words."""
    if not (Setting.get("email.imap_user") and Setting.get("email.imap_password")):
        return "Fill in the mailbox username and app password first."
    try:
        conn = _connect()
        typ, data = conn.select(f'"{Setting.get("email.imap_folder") or "INBOX"}"', readonly=True)
        conn.logout()
        if typ != "OK":
            return f"Signed in, but couldn't open the folder “{Setting.get('email.imap_folder') or 'INBOX'}”."
        return ""
    except imaplib.IMAP4.error as e:
        text = str(e)
        if "AUTHENTICATIONFAILED" in text or "Invalid credentials" in text:
            return ("Google didn't accept the username or app password. Check that IMAP is on for this mailbox "
                    "and make a new app password.")
        return f"The mail server said: {text[:300]}"
    except (OSError, socket.timeout) as e:
        return f"Couldn't reach the mail server: {e}"


# ── reading an email ──
def _text(msg) -> str:
    part = msg.get_body(preferencelist=("plain", "html"))
    if part is None:
        return ""
    try:
        body = part.get_content()
    except Exception:  # noqa: BLE001 — odd charset
        body = (part.get_payload(decode=True) or b"").decode("utf-8", "replace")
    if part.get_content_type() == "text/html":
        body = re.sub(r"(?is)<(script|style|head).*?</\1>", "", body)
        body = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>|</li>", "\n", body)
        body = html.unescape(strip_tags(body))
    body = body.replace("\r\n", "\n").replace("\xa0", " ")
    return re.sub(r"\n{3,}", "\n\n", body).strip()


def strip_quoted(body: str) -> str:
    """Keep only the new part of a reply (cuts "On … wrote:", Outlook headers and > quoted lines)."""
    cut = len(body)
    for rx in QUOTE_STARTS:
        m = rx.search(body)
        if m and m.start() > 0:
            cut = min(cut, m.start())
    kept = "\n".join(ln for ln in body[:cut].splitlines() if not ln.lstrip().startswith(">"))
    return kept.strip() or body.strip()


def _attachments(msg):
    for part in msg.iter_attachments():
        name = part.get_filename()
        if not name:
            continue
        data = part.get_payload(decode=True) or b""
        if part.get_content_disposition() == "inline" and part.get_content_maintype() == "image" and len(data) < 15000:
            continue  # small signature logos
        yield name, part.get_content_type(), data


def _is_auto(msg, sender: str) -> str:
    if SKIP_SENDERS.match(sender):
        return "automatic sender"
    if (msg.get("Auto-Submitted") or "no").lower() != "no":
        return "auto-reply"
    if (msg.get("Precedence") or "").lower() in ("bulk", "junk", "list", "auto_reply"):
        return "bulk or list mail"
    if msg.get("X-Autoreply") or msg.get("X-Autorespond") or msg.get("X-Auto-Response-Suppress", "").lower() == "all":
        return "auto-reply"
    subj = (msg.get("Subject") or "").lower()
    if subj.startswith(("automatic reply", "out of office", "auto:", "autoreply", "undeliverable", "delivery status notification")):
        return "auto-reply"
    return ""


def _number_regex():
    from apps.core.numbering import prefix
    return re.compile(rf"\[?({re.escape(prefix('ticket'))}\d+)\]?", re.I)


def find_ticket(msg) -> Ticket | None:
    refs = " ".join(filter(None, [msg.get("In-Reply-To", ""), msg.get("References", "")]))
    for tid in reversed(OUR_ID.findall(refs)):
        t = Ticket.objects.filter(pk=int(tid)).first()
        if t:
            return t.merged_into or t
    from .models import TicketMessage
    for mid in reversed(re.findall(r"<[^<>\s]+>", refs)):
        hit = InboundEmail.objects.filter(message_id=mid, ticket__isnull=False).select_related("ticket").first()
        t = hit.ticket if hit else getattr(TicketMessage.objects.filter(email_message_id=mid).select_related("ticket").first(), "ticket", None)
        if t:
            return t.merged_into or t
    m = _number_regex().search(msg.get("Subject") or "")
    if m:
        t = Ticket.objects.filter(number__iexact=m.group(1)).first()
        if t:
            return t.merged_into or t
    return None


def match_client(sender: str):
    """(client, contact) for a sender: a contact with that email, else a client whose contacts/website use that domain."""
    from apps.crm.models import Client, Contact
    c = Contact.objects.select_related("client").filter(email__iexact=sender, archived_at__isnull=True).first()
    if c:
        return c.client, c
    domain = sender.rsplit("@", 1)[-1].lower()
    public = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "live.com", "msn.com", "comcast.net", "att.net", "me.com"}
    if domain in public:
        return None, None
    ids = set(Contact.objects.filter(email__iendswith=f"@{domain}", archived_at__isnull=True).values_list("client_id", flat=True)[:3])
    if len(ids) == 1:
        return Client.objects.filter(pk=ids.pop()).first(), None
    cl = Client.objects.filter(archived_at__isnull=True, website__icontains=domain).first()
    return cl, None


def _alert_sender(sender: str) -> bool:
    lines = [ln.strip().lower() for ln in Setting.get("tickets.alert_senders", "").splitlines() if ln.strip()]
    return any(sender == ln or sender.endswith("@" + ln.lstrip("@")) for ln in lines)


def _save_files(msg, ticket, message=None) -> int:
    from apps.files.models import Upload
    from apps.files.services import check
    n = 0
    for name, ctype, data in list(_attachments(msg))[:20]:
        f = ContentFile(data, name=name)
        if check(f):
            continue
        u = Upload(kind="ticket", ticket=ticket, message=message, original_name=name[:255], content_type=ctype[:100], size=len(data),
                   uploaded_by_name="Email")
        u.file.save(name, f, save=True)
        n += 1
    return n


def process_message(raw: bytes, uid: int | None = None) -> InboundEmail:
    """Files one email. Safe to call twice with the same email (the Message-ID is remembered)."""
    from apps.helpdesk import services
    msg = email.message_from_bytes(raw, policy=policy.default)
    mid = (msg.get("Message-ID") or "").strip()[:255] or f"<no-id-{uid}-{hash(raw) & 0xffffffff:x}@local>"
    seen = InboundEmail.objects.filter(message_id=mid).first()
    if seen:
        return seen
    name, sender = parseaddr(str(msg.get("Reply-To") or msg.get("From") or ""))
    from_name, from_addr = parseaddr(str(msg.get("From") or ""))
    sender = (sender or from_addr or "").strip().lower()
    subject = re.sub(r"\s+", " ", str(msg.get("Subject") or "(no subject)")).strip()[:255]
    row = InboundEmail(message_id=mid, uid=uid, from_address=sender[:254], from_name=(from_name or name)[:200], subject=subject)
    from apps.core.mail import own_addresses
    if not sender or "@" not in sender:
        row.result, row.note = "skipped", "no sender address"
    elif sender in own_addresses() or OUR_ID.search(mid):
        row.result, row.note = "skipped", "sent by us"
    elif (why := _is_auto(msg, sender)) and not _alert_sender(sender):
        row.result, row.note = "skipped", why
    if row.result:
        row.save()
        return row
    body = _text(msg)
    with transaction.atomic():
        t = find_ticket(msg)
        if t is not None:
            text = strip_quoted(body)[:20000] or "(empty email)"
            m = services.client_reply(t, body=text, name=from_name or sender, via="email", email_message_id=mid)
            files = _save_files(msg, t, m)
            row.result, row.ticket, row.note = "reply", t, f"{files} file(s)" if files else ""
        else:
            client, contact = match_client(sender)
            to_cc = [a.lower() for _n, a in getaddresses(msg.get_all("Cc", [])) if a]
            cc = ", ".join(a for a in to_cc if a not in own_addresses() and a != sender)[:2000]
            alert = _alert_sender(sender)
            prio = Setting.get("tickets.email_priority", "") or "Medium"
            t = services.create_ticket(subject=subject, details=body[:20000], client=client, contact=contact, source="Alert" if alert else "Email",
                                       priority=prio if prio in ("Low", "Medium", "High", "Critical") else "Medium", cc=cc,
                                       contact_name=(contact.name if contact else from_name)[:200], contact_email=sender)
            files = _save_files(msg, t)
            row.result, row.ticket = "ticket", t
            row.note = ("matched to " + client.name if client else "no client matched — pick one on the ticket") + (f"; {files} file(s)" if files else "")
            if contact is None and client is not None and Setting.get("tickets.auto_add_contacts", "true") != "false":
                from apps.crm.models import Contact
                c = Contact.objects.create(client=client, name=(from_name or sender.split("@")[0])[:200], email=sender)
                Ticket.objects.filter(pk=t.pk).update(contact=c)
        row.save()
    _notify(row)
    return row


def _notify(row: InboundEmail):
    try:
        from apps.core import notify
        notify.ticket_email(row)
    except Exception:  # noqa: BLE001 — notifications are best-effort
        log.exception("notify failed")


def fetch() -> dict:
    """The scheduled job: read new mail since the last run (by IMAP UID) and file it."""
    if not enabled():
        return {"skipped": "email-to-ticket is off"}
    conn = _connect()
    try:
        folder = Setting.get("email.imap_folder") or "INBOX"
        typ, _ = conn.select(f'"{folder}"')
        if typ != "OK":
            raise RuntimeError(f"can't open folder {folder}")
        _t, data = conn.response("UIDVALIDITY")
        validity = (data[0].decode() if data and data[0] else "")
        last = int(Setting.get("email.imap_last_uid", "0") or 0)
        if Setting.get("email.imap_uidvalidity", "") not in ("", validity):
            last = 0  # the mailbox was rebuilt; Message-IDs stop duplicates
        if last == 0:
            # First run: start from now instead of turning the whole mailbox into tickets.
            _t, nxt = conn.status(f'"{folder}"', "(UIDNEXT)")
            m = re.search(rb"UIDNEXT (\d+)", nxt[0] or b"")
            last = int(m.group(1)) - 1 if m else 0
            Setting.put("email.imap_last_uid", str(last))
            Setting.put("email.imap_uidvalidity", validity)
            return {"started": f"watching for new mail after #{last}"}
        _t, found = conn.uid("search", None, f"UID {last + 1}:*")
        uids = sorted(int(u) for u in (found[0] or b"").split() if int(u) > last)[:MAX_PER_RUN]
        counts = {"ticket": 0, "reply": 0, "skipped": 0, "error": 0}
        for uid in uids:
            _t, parts = conn.uid("fetch", str(uid), "(BODY.PEEK[])")
            raw = next((p[1] for p in parts if isinstance(p, tuple)), None)
            if raw is None:
                continue
            try:
                row = process_message(raw, uid)
                counts[row.result] += 1
                conn.uid("store", str(uid), "+FLAGS", r"(\Seen)")
            except Exception as e:  # noqa: BLE001 — log it and keep going so one bad email can't block the rest
                log.exception("email %s failed", uid)
                counts["error"] += 1
                InboundEmail.objects.get_or_create(message_id=f"<error-uid-{uid}-{validity}@local>",
                                                   defaults={"uid": uid, "result": "error", "note": str(e)[:500]})
            Setting.put("email.imap_last_uid", str(uid))
        Setting.put("email.imap_uidvalidity", validity)
        Setting.put("email.last_fetch", timezone.now().isoformat(timespec="seconds"))
        return counts
    finally:
        try:
            conn.logout()
        except Exception:  # noqa: BLE001
            pass
