"""Sending email with the settings in Settings › Email (Google Workspace / Gmail SMTP, or any SMTP).

Nothing here raises: if email isn't set up, or the mail server refuses, the problem is logged and
the caller carries on (a ticket reply is still saved even when its email can't be sent).
"""
import logging
import secrets
from email.utils import formataddr

from django.core.mail import EmailMultiAlternatives, get_connection
from django.template.loader import render_to_string

from .models import Setting

log = logging.getLogger("weststar.mail")


def test(to: str) -> str:
    """Sends a test email. Returns '' when it worked, otherwise the problem in plain words."""
    if not configured():
        return "Fill in the SMTP host, username and password first."
    msg = EmailMultiAlternatives(subject="Test email from Weststar ONE", body="Sending email from Weststar ONE works.", from_email=from_address(),
                                 to=[to], connection=_connection())
    try:
        msg.send()
        return ""
    except Exception as e:  # noqa: BLE001
        text = str(e)
        if "535" in text or "Username and Password not accepted" in text:
            return "Google didn't accept the username or app password. Make a new app password for this mailbox and paste it in."
        return f"The mail server said: {text[:300]}"


def configured() -> bool:
    return bool(Setting.get("email.smtp_host") and Setting.get("email.smtp_user") and Setting.get("email.smtp_password"))


def _connection():
    try:
        port = int(Setting.get("email.smtp_port", "587") or 587)
    except ValueError:
        port = 587
    return get_connection(
        "django.core.mail.backends.smtp.EmailBackend",
        host=Setting.get("email.smtp_host"), port=port, username=Setting.get("email.smtp_user"),
        password=Setting.get("email.smtp_password"), use_tls=port == 587, use_ssl=port == 465, timeout=15,
    )


def from_address() -> str:
    addr = Setting.get("email.from_address") or Setting.get("email.smtp_user")
    name = Setting.get("email.from_name") or Setting.get("company.name") or Setting.get("brand.app_name", "Weststar ONE")
    return formataddr((name, addr))


def own_addresses() -> set[str]:
    """Our own mailbox addresses (mail from these is never turned into a ticket)."""
    keys = ("email.from_address", "email.smtp_user", "email.support_address", "email.imap_user")
    return {Setting.get(k, "").strip().lower() for k in keys if Setting.get(k, "").strip()}


def new_message_id(ticket_pk: int | None = None) -> str:
    """Our Message-ID. Replies to it carry it back in In-Reply-To/References, which finds the ticket."""
    domain = (Setting.get("email.from_address") or Setting.get("email.smtp_user") or "weststar.local").rsplit("@", 1)[-1]
    tag = f"ws1.t{ticket_pk}." if ticket_pk else "ws1."
    return f"<{tag}{secrets.token_hex(8)}@{domain}>"


def send(to, subject: str, template: str, context: dict, cc=None, reply_to=None, message_id=None, references=None) -> bool:
    """Renders templates/<template>.txt (and .html if present) and sends it. Returns True if sent."""
    to = [a for a in ([to] if isinstance(to, str) else list(to or [])) if a and "@" in a]
    cc = [a for a in (cc or []) if a and "@" in a and a not in to]
    if not to:
        return False
    if not configured():
        log.warning("Email not set up (Settings › Email); not sending %r to %s", subject, to)
        return False
    ctx = {"company": Setting.get("company.name") or "Weststar MSP", **context}
    text = render_to_string(f"{template}.txt", ctx)
    try:
        html = render_to_string(f"{template}.html", ctx)
    except Exception:  # noqa: BLE001 — a text-only email is fine
        html = None
    support = Setting.get("email.support_address")
    msg = EmailMultiAlternatives(subject=subject.replace("\n", " ")[:200], body=text, from_email=from_address(), to=to, cc=cc,
                                 reply_to=[reply_to or support] if (reply_to or support) else None, connection=_connection())
    if message_id:
        msg.extra_headers["Message-ID"] = message_id
    refs = [r for r in (references or []) if r]
    if refs:
        msg.extra_headers["In-Reply-To"] = refs[-1]
        msg.extra_headers["References"] = " ".join(refs[-10:])
    if html:
        msg.attach_alternative(html, "text/html")
    try:
        msg.send()
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Email to %s failed: %s", to, e)
        return False
