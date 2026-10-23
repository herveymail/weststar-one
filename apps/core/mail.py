"""Sending email with the settings in Settings › Email: Google Workspace / Gmail SMTP (or any SMTP), or
SMTP2GO over HTTPS — for servers whose hosting company blocks outgoing email ports (DigitalOcean does).

Nothing here raises: if email isn't set up, or the mail server refuses, the problem is logged and
the caller carries on (a ticket reply is still saved even when its email can't be sent).
"""
import json
import logging
import secrets
import smtplib
import socket
import urllib.error
import urllib.request
from email.utils import formataddr

from django.core.mail import EmailMultiAlternatives
from django.core.mail.backends.smtp import EmailBackend
from django.template.loader import render_to_string

from .models import Setting

log = logging.getLogger("weststar.mail")


GMAIL_API = "Google Workspace (Gmail API)"


def provider() -> str:
    p = Setting.get("email.provider", "")
    if p == GMAIL_API:
        return "gmail"
    return "smtp2go" if p == "SMTP2GO (HTTPS)" else "smtp"


def test(to: str) -> str:
    """Sends a test email. Returns '' when it worked, otherwise the problem in plain words."""
    if not configured():
        return {"smtp2go": "Paste the SMTP2GO API key first.", "gmail": "Click “Connect Google mailbox” first."}.get(
            provider(), "Fill in the SMTP host, username and password first.")
    msg = EmailMultiAlternatives(subject="Test email from Weststar ONE", body="Sending email from Weststar ONE works.", from_email=from_address(), to=[to])
    try:
        _deliver(msg)
        return ""
    except Exception as e:  # noqa: BLE001
        return explain(e)


def explain(e: Exception) -> str:
    text = str(e)
    if provider() == "gmail":
        return text[:400]
    if provider() == "smtp2go":
        return f"SMTP2GO said: {text[:300]}"
    if "535" in text or "Username and Password not accepted" in text:
        return "Google didn't accept the username or app password. Make a new app password for this mailbox and paste it in."
    if isinstance(e, (OSError, socket.timeout)) and not isinstance(e, socket.gaierror):
        port = Setting.get("email.smtp_port", "587") or "587"
        if not port_open(Setting.get("email.smtp_host") or "smtp.gmail.com", int(port)) and port_open("gmail.googleapis.com", 443):
            return (f"This server can't open a connection to {Setting.get('email.smtp_host') or 'smtp.gmail.com'} on port {port}, but web (HTTPS) "
                    "connections work. Click “Check this server's connections” below to see exactly what's open. Fix: “Connect Google "
                    "mailbox” (sends through Google over HTTPS) or SMTP2GO.")
    return f"The mail server said: {text[:300]}"


def port_open(host: str, port: int, timeout=6) -> bool:
    """Can this server open a connection to host:port over IPv4?"""
    try:
        for *_x, sa in socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM):
            with socket.create_connection(sa[:2], timeout=timeout):
                return True
    except OSError:
        return False
    return False


def configured() -> bool:
    if provider() == "gmail":
        from . import gmail
        return gmail.connected()
    if provider() == "smtp2go":
        return bool(Setting.get("email.smtp2go_api_key") and (Setting.get("email.from_address") or Setting.get("email.smtp_user")))
    return bool(Setting.get("email.smtp_host") and Setting.get("email.smtp_user") and Setting.get("email.smtp_password"))


def _deliver(msg: EmailMultiAlternatives) -> None:
    if provider() == "gmail":
        from . import gmail
        gmail.send_raw(msg.message().as_bytes())
        return
    if provider() != "smtp2go":
        msg.connection = _connection()
        msg.send()
        return
    html = next((c for c, mime in getattr(msg, "alternatives", []) if mime == "text/html"), None)
    headers = [{"header": k, "value": v} for k, v in msg.extra_headers.items()]
    if msg.reply_to:
        headers.append({"header": "Reply-To", "value": ", ".join(msg.reply_to)})
    body = {"sender": msg.from_email, "to": msg.to, "cc": msg.cc or None, "subject": msg.subject, "text_body": msg.body,
            "html_body": html, "custom_headers": headers or None}
    req = urllib.request.Request("https://api.smtp2go.com/v3/email/send", data=json.dumps({k: v for k, v in body.items() if v}).encode(),
                                 headers={"Content-Type": "application/json", "X-Smtp2go-Api-Key": Setting.get("email.smtp2go_api_key"),
                                          "Accept": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:  # noqa: S310 — fixed https URL
            data = json.loads(r.read() or b"{}").get("data", {})
    except urllib.error.HTTPError as e:
        try:
            data = json.loads(e.read() or b"{}").get("data", {})
        except ValueError:
            data = {}
        raise RuntimeError(data.get("error") or f"HTTP {e.code}") from e
    if not data.get("succeeded"):
        raise RuntimeError(data.get("error") or (data.get("failures") or ["not accepted"])[0])


def _ipv4_first(host, port, timeout):
    """Connect over IPv4 first (Docker networks often have no IPv6 route: "Network is unreachable"), then IPv6."""
    last = None
    infos = socket.getaddrinfo(host, port, 0, socket.SOCK_STREAM)
    for _f, _t, _p, _c, sa in sorted(infos, key=lambda i: i[0] != socket.AF_INET):
        try:
            return socket.create_connection(sa[:2], timeout)
        except OSError as e:
            last = e
    raise last or OSError("no address for " + host)


class _SMTP(smtplib.SMTP):
    def _get_socket(self, host, port, timeout):
        return _ipv4_first(host, port, timeout)


class _SMTPSSL(smtplib.SMTP_SSL):
    def _get_socket(self, host, port, timeout):
        sock = _ipv4_first(host, port, timeout)
        return self.context.wrap_socket(sock, server_hostname=self._host)


class _Backend(EmailBackend):
    @property
    def connection_class(self):
        return _SMTPSSL if self.use_ssl else _SMTP


def diagnose() -> list[tuple[str, str, bool, str]]:
    """Settings › Email sending › Check this server's connections: plain facts instead of guesses."""
    checks = [("Gmail SMTP", "smtp.gmail.com", 587), ("Gmail SMTP (SSL)", "smtp.gmail.com", 465), ("Office 365 SMTP", "smtp.office365.com", 587),
              ("Gmail IMAP (email to ticket)", "imap.gmail.com", 993), ("Google API (HTTPS)", "gmail.googleapis.com", 443),
              ("SMTP2GO API (HTTPS)", "api.smtp2go.com", 443), ("SMTP2GO SMTP alt port", "mail.smtp2go.com", 2525)]
    out = []
    for label, host, port in checks:
        for fam, name in ((socket.AF_INET, "IPv4"), (socket.AF_INET6, "IPv6")):
            try:
                sa = socket.getaddrinfo(host, port, fam, socket.SOCK_STREAM)[0][4]
            except OSError:
                out.append((label, f"{host}:{port} {name}", False, "no address"))
                continue
            t0 = __import__("time").monotonic()
            try:
                with socket.create_connection(sa[:2], timeout=6):
                    out.append((label, f"{host}:{port} {name}", True, f"open ({int((__import__('time').monotonic() - t0) * 1000)} ms)"))
            except TimeoutError:
                out.append((label, f"{host}:{port} {name}", False, "timed out — blocked by a firewall"))
            except OSError as e:
                out.append((label, f"{host}:{port} {name}", False, e.strerror or str(e)))
    return out


def _connection():
    try:
        port = int(Setting.get("email.smtp_port", "587") or 587)
    except ValueError:
        port = 587
    return _Backend(
        host=Setting.get("email.smtp_host"), port=port, username=Setting.get("email.smtp_user"),
        password=Setting.get("email.smtp_password"), use_tls=port == 587, use_ssl=port == 465, timeout=15,
    )


def from_address() -> str:
    addr = Setting.get("email.from_address") or Setting.get("email.smtp_user") or Setting.get("email.gmail_address")
    name = Setting.get("email.from_name") or Setting.get("company.name") or Setting.get("brand.app_name", "Weststar ONE")
    return formataddr((name, addr))


def own_addresses() -> set[str]:
    """Our own mailbox addresses (mail from these is never turned into a ticket)."""
    keys = ("email.from_address", "email.smtp_user", "email.support_address", "email.imap_user", "email.gmail_address")
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
                                 reply_to=[reply_to or support] if (reply_to or support) else None)
    if message_id:
        msg.extra_headers["Message-ID"] = message_id
    refs = [r for r in (references or []) if r]
    if refs:
        msg.extra_headers["In-Reply-To"] = refs[-1]
        msg.extra_headers["References"] = " ".join(refs[-10:])
    if html:
        msg.attach_alternative(html, "text/html")
    try:
        _deliver(msg)
        return True
    except Exception as e:  # noqa: BLE001
        log.error("Email to %s failed: %s", to, e)
        return False
