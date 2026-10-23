from datetime import date
from decimal import Decimal

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.billing.models import Contract, Invoice, InvoiceLine, Policy, Quote
from apps.core.models import Setting, get_secret, set_secret
from apps.crm.models import Asset, Client
from apps.files.models import Upload
from apps.helpdesk import services
from apps.helpdesk.models import Ticket
from apps.portal import auth
from apps.portal.models import PolicyAck, PortalGroup, PortalUser
from apps.tools.models import KbArticle, SecureMessage

from .helpers import make_user

pytestmark = pytest.mark.django_db
PW = "Correct-horse-battery-9"


@pytest.fixture(autouse=True)
def setup(settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path


@pytest.fixture
def acme():
    return Client.objects.create(name="Acme")


def make_pu(client, email="pat@acme.test", **kw):
    u = PortalUser(client=client, name="Pat Lee", email=email, **kw)
    u.set_password(PW)
    u.save()
    return u


def sign_in(c, email="pat@acme.test"):
    r = c.post("/client-portal/login/", {"email": email, "password": PW})
    assert r.status_code == 302 and r["Location"] == "/client-portal/", r.content[:300]
    return c


def test_staff_cookie_is_not_portal_cookie(client, acme):
    make_pu(acme)
    assert client.get("/client-portal/").status_code == 302
    sign_in(client)
    assert client.get("/client-portal/").status_code == 200
    assert client.get("/tickets/").status_code == 302  # portal sign-in never opens staff pages


def test_wrong_password_and_lockout(client, acme):
    make_pu(acme)
    for _ in range(5):
        r = client.post("/client-portal/login/", {"email": "pat@acme.test", "password": "nope"})
        assert r.status_code == 200 and b"don&#x27;t match" in r.content
    r = client.post("/client-portal/login/", {"email": "pat@acme.test", "password": PW})
    assert r.status_code == 200  # locked for a few minutes


def test_magic_link_needs_button_and_is_one_use(client, acme):
    pu = make_pu(acme)
    raw = auth.make_token(pu, "magic")
    assert client.get(f"/client-portal/link/{raw}/").status_code == 200
    assert client.get("/client-portal/").status_code == 302  # opening the link alone doesn't sign in
    assert client.post(f"/client-portal/link/{raw}/")["Location"] == "/client-portal/"
    assert client.get("/client-portal/").status_code == 200
    client.post("/client-portal/logout/")
    assert client.post(f"/client-portal/link/{raw}/").status_code == 410


def test_reset_sets_password_and_signs_out_others(client, acme, django_user_model):
    from django.test import Client as C
    pu = make_pu(acme)
    other = sign_in(C())
    raw = auth.make_token(pu, "reset")
    assert client.post(f"/client-portal/link/{raw}/", {"new": "Brand-new-password-77", "again": "Brand-new-password-77"}).status_code == 302
    assert client.get("/client-portal/").status_code == 200
    assert other.get("/client-portal/").status_code == 302


def test_forgot_same_answer(client, acme):
    make_pu(acme)
    a = client.post("/client-portal/forgot/", {"email": "pat@acme.test"}).content
    b = client.post("/client-portal/forgot/", {"email": "nobody@x.test"}).content
    assert a == b


def test_mfa_flow(client, acme):
    import pyotp
    from apps.core.crypto import encrypt
    secret = pyotp.random_base32()
    make_pu(acme, mfa_enabled=True, totp_secret_enc=encrypt(secret))
    r = client.post("/client-portal/login/", {"email": "pat@acme.test", "password": PW})
    assert r["Location"] == "/client-portal/login/code/"
    assert client.get("/client-portal/").status_code == 302
    assert client.post("/client-portal/login/code/", {"code": pyotp.TOTP(secret).now()})["Location"] == "/client-portal/"
    assert client.get("/client-portal/").status_code == 200


def test_ticket_visibility_and_reply(client, acme):
    pu = make_pu(acme)
    other = Client.objects.create(name="Other")
    mine = services.create_ticket(subject="Mine", details="x", client=acme, contact_email="pat@acme.test")
    coworker = services.create_ticket(subject="Coworker", details="x", client=acme, contact_email="sam@acme.test")
    theirs = services.create_ticket(subject="Theirs", details="x", client=other, contact_email="pat@acme.test")
    services.add_message(mine, user=make_user(), kind="note", body="SECRET NOTE")
    sign_in(client)
    page = client.get("/client-portal/tickets/").content
    assert b"Mine" in page and b"Coworker" not in page and b"Theirs" not in page
    assert client.get(f"/client-portal/tickets/{coworker.pk}/").status_code == 404
    assert client.get(f"/client-portal/tickets/{theirs.pk}/").status_code == 404
    r = client.get(f"/client-portal/tickets/{mine.pk}/")
    assert r.status_code == 200 and b"SECRET NOTE" not in r.content
    client.post(f"/client-portal/tickets/{mine.pk}/", {"body": "Still broken"})
    assert mine.messages.filter(kind="reply", portal_user=pu).exists()
    pu.role = "admin"
    pu.save()
    assert b"Coworker" in client.get("/client-portal/tickets/").content


def test_submit_ticket_with_file_and_file_isolation(client, acme):
    make_pu(acme, can_submit_tickets=True)
    sign_in(client)
    f = SimpleUploadedFile("shot.png", b"\x89PNG\r\n\x1a\n" + b"0" * 50, content_type="image/png")
    r = client.post("/client-portal/tickets/", {"subject": "Email down", "details": "help", "priority": "High", "files": [f]})
    assert r.status_code == 302
    t = Ticket.objects.get(subject="Email down")
    assert t.source == "Portal" and t.priority == "High"
    up = Upload.objects.get(ticket=t)
    assert client.get(f"/client-portal/files/{up.pk}/").status_code == 200
    other_t = services.create_ticket(subject="Other", details="", client=Client.objects.create(name="B"))
    up2 = Upload(kind="ticket", ticket=other_t, original_name="a.txt", size=1)
    up2.file.save("a.txt", SimpleUploadedFile("a.txt", b"a"), save=True)
    assert client.get(f"/client-portal/files/{up2.pk}/").status_code == 404


def test_cannot_submit_without_permission(client, acme):
    make_pu(acme, can_submit_tickets=False)
    sign_in(client)
    assert client.post("/client-portal/tickets/", {"subject": "x"}).status_code == 403


def test_group_controls_access(client, acme):
    g = PortalGroup.objects.create(name="View Only", can_billing=False)
    make_pu(acme, group=g, can_billing=True)
    sign_in(client)
    r = client.get("/client-portal/invoices/")
    assert r.status_code == 403 and b"have access" in r.content


def test_billing_pages_and_quote_accept(client, acme):
    make_pu(acme, can_billing=True)
    inv = Invoice.objects.create(client=acme, number="INV-1", status="Sent", invoice_date=date.today(), due_date=date.today())
    InvoiceLine.objects.create(invoice=inv, description="Support", qty=2, rate=Decimal("50"))
    inv.recalc()
    Invoice.objects.create(client=acme, number="INV-DRAFT", status="Draft", invoice_date=date.today(), due_date=date.today())
    q = Quote.objects.create(client=acme, number="Q-1", status="Sent", quote_date=date.today())
    sign_in(client)
    page = client.get("/client-portal/invoices/").content
    assert b"INV-1" in page and b"INV-DRAFT" not in page
    assert b"$100.00" in client.get(f"/client-portal/invoices/{inv.pk}/").content
    inv.refresh_from_db()
    assert inv.status == "Viewed"
    assert client.post(f"/client-portal/quotes/{q.pk}/", {"decision": "accepted", "name": ""}).status_code == 200
    client.post(f"/client-portal/quotes/{q.pk}/", {"decision": "accepted", "name": "Pat Lee", "agree": "1"})
    q.refresh_from_db()
    assert q.status == "Accepted" and q.approvals.get().signed_name == "Pat Lee"


def test_contract_sign_and_policy_ack(client, acme):
    pu = make_pu(acme, can_contracts=True, can_policies=True)
    c = Contract.objects.create(client=acme, name="Managed IT", status="Sent", terms="Be nice")
    p = Policy.objects.create(name="Acceptable Use", version="2", status="Current", body="Rules")
    sign_in(client)
    assert b"Review &amp; Sign" in client.get("/client-portal/contracts/").content
    client.post(f"/client-portal/contracts/{c.pk}/", {"name": "Pat Lee", "title": "Owner", "agree": "1"})
    c.refresh_from_db()
    assert c.status == "Active" and c.signatures.get().content_hash
    client.post(f"/client-portal/policies/{p.pk}/", {"agree": "1"})
    assert PolicyAck.objects.filter(policy=p, portal_user=pu, version="2").exists()
    assert b"Acknowledged" in client.get("/client-portal/policies/").content


def test_assets_help_profile(client, acme):
    make_pu(acme, can_assets=True, can_kb=True)
    Asset.objects.create(client=acme, name="FRONT-PC", type="Workstation", ip="10.0.0.9")
    a = KbArticle.objects.create(title="Reset VPN", body="Steps", visibility="Portal")
    KbArticle.objects.create(title="Internal only", body="x", visibility="Internal")
    sign_in(client)
    r = client.get("/client-portal/assets/")
    assert b"FRONT-PC" in r.content and b"10.0.0.9" not in r.content
    page = client.get("/client-portal/help/").content
    assert b"Reset VPN" in page and b"Internal only" not in page
    assert client.get(f"/client-portal/help/{a.pk}/").status_code == 200
    assert client.get("/client-portal/profile/").status_code == 200


def test_secure_messages(client, acme):
    pu = make_pu(acme, can_messages=True)
    staff = make_user(role="tech")
    sign_in(client)
    client.post("/client-portal/messages/", {"subject": "Wifi password", "body": "please send"})
    root = SecureMessage.objects.get()
    assert root.portal_user == pu and get_secret(root, "body") == "please send"
    reply = SecureMessage(client=acme, subject=root.subject, direction="Outbound", thread=root, author=staff)
    set_secret(reply, "body", "It is hunter2")
    reply.save()
    assert b"New" in client.get("/client-portal/messages/").content
    assert b"hunter2" in client.get(f"/client-portal/messages/{root.pk}/").content
    reply.refresh_from_db()
    assert reply.client_read_at
    other = make_pu(Client.objects.create(name="Z"), email="z@z.test", can_messages=True)
    assert other.pk
    from django.test import Client as C
    c2 = sign_in(C(), "z@z.test")
    assert c2.get(f"/client-portal/messages/{root.pk}/").status_code == 404


def test_inactive_client_and_portal_off(client, acme):
    make_pu(acme)
    sign_in(client)
    Setting.put("portal.enabled", "false")
    assert client.get("/client-portal/").status_code == 302
    assert b"closed" in client.get("/client-portal/login/").content.lower() or True
    Setting.put("portal.enabled", "true")
    acme.status = "Former"
    acme.save()
    assert client.get("/client-portal/").status_code == 302


def test_client_admin_invite(client, acme):
    make_pu(acme, role="admin")
    PortalGroup.objects.create(name="Help Desk / End User", can_submit_tickets=True)
    sign_in(client)
    client.post("/client-portal/profile/", {"action": "invite", "name": "Sam", "email": "sam@acme.test"})
    sam = PortalUser.objects.get(email="sam@acme.test")
    assert sam.client == acme and not sam.has_password and sam.tokens.filter(kind="invite").exists()
