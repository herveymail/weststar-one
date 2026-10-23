from email.message import EmailMessage

import pytest

from apps.core import mail
from apps.core.models import Setting
from apps.crm.models import Client, Contact
from apps.files.models import Upload
from apps.helpdesk import inbound, services
from apps.helpdesk.models import InboundEmail, Ticket

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    Setting.put("email.imap_user", "support@weststarmsp.com")
    Setting.put("numbers.ticket_prefix", "ITDS-")


def raw(subject="Printer is down", frm="Maria Lopez <maria@franklin.test>", body="It won't print.", **headers):
    m = EmailMessage()
    m["From"], m["To"], m["Subject"] = frm, "support@weststarmsp.com", subject
    m["Message-ID"] = headers.pop("mid", f"<{abs(hash((subject, frm, body)))}@mail.test>")
    for k, v in headers.items():
        m[k.replace("_", "-")] = v
    m.set_content(body)
    return m


def test_new_email_makes_ticket_for_matched_client():
    acme = Client.objects.create(name="Franklin Title")
    Contact.objects.create(client=acme, name="Maria Lopez", email="maria@franklin.test")
    m = raw()
    m.add_attachment(b"%PDF-1.4 hello", maintype="application", subtype="pdf", filename="scan.pdf")
    row = inbound.process_message(m.as_bytes(), 1)
    t = row.ticket
    assert row.result == "ticket" and t.client == acme and t.source == "Email" and t.contact_email == "maria@franklin.test"
    assert t.number.startswith("ITDS-") and Upload.objects.filter(ticket=t).count() == 1
    assert inbound.process_message(m.as_bytes(), 1).pk == row.pk  # same email twice → one ticket
    assert Ticket.objects.count() == 1


def test_domain_match_adds_contact():
    acme = Client.objects.create(name="Franklin Title")
    Contact.objects.create(client=acme, name="Maria", email="maria@franklin.test")
    row = inbound.process_message(raw(frm="Bob <bob@franklin.test>").as_bytes())
    assert row.ticket.client == acme and Contact.objects.filter(email="bob@franklin.test", client=acme).exists()


def test_reply_by_subject_number_strips_quote_and_reopens():
    t = services.create_ticket(subject="VPN", details="x", contact_email="maria@franklin.test")
    Ticket.objects.filter(pk=t.pk).update(status="Resolved")
    body = "Still broken today.\n\nOn Mon, Oct 19, 2026 at 9:00 AM Weststar <support@weststarmsp.com> wrote:\n> old text"
    row = inbound.process_message(raw(subject=f"Re: [{t.number}] VPN", body=body).as_bytes())
    t.refresh_from_db()
    assert row.result == "reply" and row.ticket == t and t.status == "Open"
    m = t.messages.get(kind="reply")
    assert m.body == "Still broken today." and m.via == "email" and m.from_client


def test_reply_by_our_message_id_without_number():
    t = services.create_ticket(subject="Email", details="x")
    mid = mail.new_message_id(t.pk)
    row = inbound.process_message(raw(subject="Re: hello", In_Reply_To=mid, References=mid).as_bytes())
    assert row.ticket == t and row.result == "reply"


def test_old_system_numbers_without_brackets():
    t = services.create_ticket(subject="Old one", details="")
    row = inbound.process_message(raw(subject=f"RE: {t.number} – Old one").as_bytes())
    assert row.ticket == t


@pytest.mark.parametrize("hdrs,frm", [({"Auto_Submitted": "auto-replied"}, None), ({"Precedence": "bulk"}, None), ({}, "MAILER-DAEMON@x.test"),
                                      ({}, "support@weststarmsp.com"), ({"Subject_": "x"}, None)])
def test_skips_auto_and_own(hdrs, frm):
    subj = "Automatic reply: away" if "Subject_" in hdrs else "Hi"
    hdrs.pop("Subject_", None)
    row = inbound.process_message(raw(subject=subj, frm=frm or "a@b.test", **hdrs).as_bytes())
    assert row.result == "skipped" and not Ticket.objects.exists()


def test_alert_sender_makes_alert_ticket_even_if_automatic():
    Setting.put("tickets.alert_senders", "datto.com")
    row = inbound.process_message(raw(frm="alerts@datto.com", Auto_Submitted="auto-generated").as_bytes())
    assert row.result == "ticket" and row.ticket.source == "Alert"


def test_html_only_email():
    m = EmailMessage()
    m["From"], m["Subject"], m["Message-ID"] = "x@y.test", "Html", "<h1@y.test>"
    m.set_content("<p>Hello <b>there</b></p><style>p{}</style>", subtype="html")
    row = inbound.process_message(m.as_bytes())
    assert "Hello there" in row.ticket.details and "<" not in row.ticket.details


def test_fetch_off_by_default():
    assert inbound.fetch() == {"skipped": "email-to-ticket is off"}
    assert not InboundEmail.objects.exists()


def test_settings_page_and_test_buttons(client):
    from .helpers import make_user, signed_in
    Setting.put("security.require_mfa", "nobody")
    signed_in(client, make_user(role="admin"))
    r = client.get("/settings/email_in/")
    assert r.status_code == 200 and b"Test connection" in r.content and b"imap.gmail.com" in r.content
    assert b"Send test email" in client.get("/settings/email/").content
    r = client.post("/settings/email/test/", {"what": "send", "to": "me@x.test"}, follow=True)
    assert b"Fill in the SMTP" in r.content
    for page in ("ticket_emails", "sla", "afterhours", "portal", "queues", "portal_groups", "old_settings", "late_fees", "contract_defaults"):
        assert client.get(f"/settings/{page}/").status_code == 200, page


def test_after_hours(settings):
    import datetime as dt

    from django.utils import timezone
    Setting.put("helpdesk.open", "07:00")
    Setting.put("helpdesk.close", "16:30")
    Setting.put("helpdesk.days", "Mon,Tue,Wed,Thu,Fri")
    Setting.put("app.timezone", "America/Denver")
    from zoneinfo import ZoneInfo
    tz = ZoneInfo("America/Denver")
    assert services.after_hours(dt.datetime(2026, 10, 23, 10, 0, tzinfo=tz)) is False  # Friday 10am
    assert services.after_hours(dt.datetime(2026, 10, 23, 18, 0, tzinfo=tz)) is True
    assert services.after_hours(dt.datetime(2026, 10, 24, 10, 0, tzinfo=tz)) is True   # Saturday
    _ = timezone


def test_staff_reply_threads_email(monkeypatch):
    from .helpers import make_user
    sent = {}
    monkeypatch.setattr(mail, "send", lambda to, subject, tpl, ctx, **kw: sent.update(to=to, subject=subject, **kw) or True)
    t = services.create_ticket(subject="Printer", details="", contact_email="maria@franklin.test")
    inbound.process_message(raw(subject=f"Re: [{t.number}] Printer", mid="<abc@mail.test>").as_bytes())
    m = services.add_message(t, user=make_user(), kind="reply", body="Try again")
    m.refresh_from_db()
    assert sent["subject"] == f"Re: [{t.number}] Printer" and "<abc@mail.test>" in sent["references"]
    assert m.via == "email" and m.email_message_id == sent["message_id"] and f"ws1.t{t.pk}." in m.email_message_id


class FakeImap:
    def __init__(self, validity=b"777", uids=b"440 441", nxt=500):
        self.validity, self.uids, self.nxt, self.searched, self.stored = validity, uids, nxt, [], []

    def select(self, folder, readonly=False):
        return "OK", [b"1"]

    def response(self, code):
        return code, [self.validity]

    def status(self, folder, what):
        return "OK", [f"INBOX (UIDNEXT {self.nxt})".encode()]

    def uid(self, cmd, *args):
        if cmd == "search":
            self.searched.append(args[1])
            return "OK", [self.uids]
        if cmd == "fetch":
            return "OK", [(b"1", raw(subject=f"Mail {args[0]}", mid=f"<m{args[0]}@x.test>").as_bytes())]
        self.stored.append(args[0])
        return "OK", []

    def logout(self):
        pass


def _fetch_with(monkeypatch, imap):
    Setting.put("email.fetch_enabled", "true")
    Setting.put("email.imap_password", "app-pass", secret=True)
    monkeypatch.setattr(inbound, "_connect", lambda: imap)
    return inbound.fetch()


def test_fetch_continues_from_old_app(monkeypatch):
    Setting.put("email.imap_last_uid", "439")
    Setting.put("email.imap_uidvalidity", "777")
    r = _fetch_with(monkeypatch, FakeImap())
    assert r["ticket"] == 2 and Setting.get("email.imap_last_uid") == "441"


def test_fetch_after_import_with_other_numbering_uses_date(monkeypatch):
    Setting.put("email.imap_last_uid", "439")
    Setting.put("email.imap_uidvalidity", "1")
    Setting.put("email.imap_since", "2026-10-22")
    imap = FakeImap()
    _fetch_with(monkeypatch, imap)
    assert imap.searched[0] == "UID 2:* SINCE 22-Oct-2026"


def test_first_fetch_without_history_starts_now(monkeypatch):
    r = _fetch_with(monkeypatch, FakeImap())
    assert "watching" in r["started"] and Setting.get("email.imap_last_uid") == "499" and not Ticket.objects.exists()


def test_smtp2go_https_sending(monkeypatch):
    import json as _json
    sent = {}

    class R:
        def __init__(self, body):
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return self.body

    def fake_urlopen(req, timeout=0):
        sent["url"], sent["key"], sent["body"] = req.full_url, req.headers.get("X-smtp2go-api-key"), _json.loads(req.data)
        return R(b'{"data": {"succeeded": 1, "failed": 0}}')
    monkeypatch.setattr(mail.urllib.request, "urlopen", fake_urlopen)
    Setting.put("email.provider", "SMTP2GO (HTTPS)")
    Setting.put("email.smtp2go_api_key", "api-123", secret=True)
    Setting.put("email.from_address", "support@weststarmsp.com")
    assert mail.configured() and mail.test("me@x.test") == ""
    assert sent["url"] == "https://api.smtp2go.com/v3/email/send" and sent["key"] == "api-123" and sent["body"]["to"] == ["me@x.test"]
    t = services.create_ticket(subject="Printer", details="", contact_email="maria@franklin.test")
    assert services.send_ticket_email(t, "new", "email/ticket_received", {})
    assert any(h["header"] == "Message-ID" for h in sent["body"]["custom_headers"])


def test_blocked_port_message(monkeypatch):
    Setting.put("email.smtp_host", "smtp.gmail.com")
    Setting.put("email.smtp_user", "support@weststarmsp.com")
    Setting.put("email.smtp_password", "x", secret=True)
    monkeypatch.setattr(mail, "port_open", lambda host, port, timeout=6: port == 443)

    def boom(msg):
        raise OSError(101, "Network is unreachable")
    monkeypatch.setattr(mail, "_deliver", boom)
    assert "can't open a connection to smtp.gmail.com on port 587" in mail.test("me@x.test")


def test_ipv4_tried_before_ipv6(monkeypatch):
    import socket as s
    tried = []
    monkeypatch.setattr(mail.socket, "getaddrinfo", lambda h, p, *a: [(s.AF_INET6, 1, 6, "", ("::1", p, 0, 0)), (s.AF_INET, 1, 6, "", ("1.2.3.4", p))])

    def conn(sa, timeout):
        tried.append(sa[0])
        if ":" in sa[0]:
            raise OSError(101, "Network is unreachable")
        return "sock"
    monkeypatch.setattr(mail.socket, "create_connection", conn)
    assert mail._ipv4_first("smtp.gmail.com", 587, 5) == "sock" and tried == ["1.2.3.4"]


def test_google_mailbox_connect_and_send(client, monkeypatch):
    import base64
    import json as _json

    from apps.core import gmail

    from .helpers import make_user, signed_in
    Setting.put("security.require_mfa", "nobody")
    Setting.put("google.client_id", "cid")
    Setting.put("google.client_secret", "sec", secret=True)
    signed_in(client, make_user(role="admin"))
    r = client.post("/settings/email/google/")
    assert r.status_code == 302 and "mail.google.com" in r["Location"] and "access_type=offline" in r["Location"]
    state = client.session["gmail_oauth"]["state"]
    idt = "x." + base64.urlsafe_b64encode(_json.dumps({"email": "support@weststarmsp.com"}).encode()).decode().rstrip("=") + ".y"
    monkeypatch.setattr(gmail, "_token", lambda url, data: {"access_token": "at", "refresh_token": "rt", "expires_in": 3600,
                                                             "scope": "openid email https://mail.google.com/", "id_token": idt})
    r = client.get("/settings/email/google/callback/", {"state": state, "code": "c"}, follow=True)
    assert b"Connected support@weststarmsp.com" in r.content and mail.provider() == "gmail" and mail.configured()
    sent = {}

    class R:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"id": "m1"}'
    monkeypatch.setattr(gmail.urllib.request, "urlopen", lambda req, timeout=0: sent.update(auth=req.headers["Authorization"], body=_json.loads(req.data)) or R())
    assert mail.test("me@x.test") == ""
    raw = base64.urlsafe_b64decode(sent["body"]["raw"]).decode()
    assert sent["auth"] == "Bearer at" and "To: me@x.test" in raw and "support@weststarmsp.com" in raw
    Setting.put("email.fetch_enabled", "true")
    assert inbound.enabled()  # reads the inbox through the connected mailbox, no app password
    r = client.post("/settings/email/test/", {"what": "diagnose"})
    assert r.status_code == 302
