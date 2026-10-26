import base64
import struct
import zlib
from decimal import Decimal

import pytest

from apps.core.models import Setting
from apps.crm.models import Client
from apps.helpdesk import services
from apps.helpdesk.models import Ticket, TicketApproval, TimeEntry
from apps.helpdesk.signoff import SignoffRequired, signature_ok

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


def png(w=300, h=100):
    def chunk(t, d):
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\xff\xff\xff" * w for _ in range(h))
    data = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    return "data:image/png;base64," + base64.b64encode(data).decode()


@pytest.fixture
def setup(client):
    Setting.put("security.require_mfa", "nobody")
    Setting.put("billing.default_tax_rate", "0")
    admin = make_user(role="admin")
    c = Client.objects.create(name="Corner Store", plan="Break/fix", hourly_rate=Decimal("100"), tax_rate=Decimal("8"))
    t = services.create_ticket(subject="PC slow", client=c, contact_email="owner@corner.test")
    TimeEntry.objects.create(ticket=t, user=admin, minutes=90, work_date="2026-10-26")
    return signed_in(client, admin), admin, t


def test_breakfix_ticket_cannot_close_until_signed(setup):
    web, admin, t = setup
    with pytest.raises(SignoffRequired):
        services.update_ticket(t, user=admin, status="Closed")
    r = web.post(f"/tickets/{t.pk}/update/", {"status": "Resolved", "ctx": "panel"})
    assert b"customer signs off" in r.content
    t.refresh_from_db()
    assert t.status != "Resolved"
    assert b"Get signature" in web.get(f"/tickets/{t.pk}/?classic=1").content
    # managed clients are never blocked
    m = Client.objects.create(name="Managed Co", plan="Managed")
    t2 = services.create_ticket(subject="x", client=m)
    services.update_ticket(t2, user=admin, status="Closed")


def test_customer_signs_and_ticket_resolves(setup):
    web, admin, t = setup
    page = web.get(f"/tickets/{t.pk}/signoff/?type=completion").content.decode()
    assert 'data-rate="100.00"' in page and 'value="1.50"' in page
    r = web.post(f"/tickets/{t.pk}/signoff/?type=completion", {
        "type": "completion", "summary": "Cleaned up startup", "hours": "2", "parts_desc": "SSD", "parts_amount": "50",
        "signer_name": "Pat Owner", "signer_email": "pat@corner.test", "signature": png(), "close": "1"})
    assert r.status_code == 302
    t.refresh_from_db()
    so = t.signoffs.get()
    assert so.total == Decimal("270.00")  # 2h × $100 + $50 parts + 8% tax
    assert "$270.00" in so.statement and "plus $50.00 for SSD" in so.statement and len(so.hash) == 64
    assert t.status == "Resolved"
    assert TimeEntry.objects.filter(ticket=t).aggregate(m=__import__("django.db.models", fromlist=["Sum"]).Sum("minutes"))["m"] == 120  # billed what was signed
    assert t.messages.filter(kind="note", body__contains="signed by Pat Owner").exists()


def test_bad_signature_and_override(setup):
    web, admin, t = setup
    r = web.post(f"/tickets/{t.pk}/signoff/", {"type": "completion", "signer_name": "Pat", "signature": "data:image/png;base64,AAAA"})
    assert r.status_code == 422 and b"couldn" in r.content.lower()
    assert not signature_ok("data:image/svg+xml;base64," + base64.b64encode(b"<svg/>").decode())
    r = web.post(f"/tickets/{t.pk}/signoff/", {"type": "completion", "override": "1", "override_reason": "short"})
    assert r.status_code == 422
    r = web.post(f"/tickets/{t.pk}/signoff/", {"type": "completion", "override": "1", "override_reason": "Customer not on site, remote job"})
    assert r.status_code == 302
    services.update_ticket(Ticket.objects.get(pk=t.pk), user=admin, status="Closed")  # now allowed


def test_dropoff_needs_items(setup):
    web, admin, t = setup
    assert web.post(f"/tickets/{t.pk}/signoff/?type=dropoff", {"type": "dropoff", "signer_name": "Pat", "signature": png()}).status_code == 422
    assert web.post(f"/tickets/{t.pk}/signoff/?type=dropoff", {"type": "dropoff", "items": "Dell laptop + charger", "signer_name": "Pat", "signature": png()}).status_code == 302
    assert t.signoffs.get().type == "dropoff"


def test_approvals_and_delete(setup):
    web, admin, t = setup
    web.post(f"/tickets/{t.pk}/approval/", {"description": "Replace failing drive, up to $200", "approved_by": "Pat", "via": "phone"})
    a = TicketApproval.objects.get(ticket=t)
    assert a.via == "phone" and "Replace failing drive" in web.get(f"/tickets/{t.pk}/?classic=1").content.decode()
    web.post(f"/tickets/{t.pk}/approval/", {"delete": str(a.pk)})
    assert not TicketApproval.objects.exists()
    web.post(f"/tickets/{t.pk}/delete/", {"confirm": "wrong"})
    assert Ticket.objects.filter(pk=t.pk).exists()
    web.post(f"/tickets/{t.pk}/delete/", {"confirm": t.number})
    assert not Ticket.objects.filter(pk=t.pk).exists()


def test_only_admins_delete(client):
    Setting.put("security.require_mfa", "nobody")
    tech = signed_in(client, make_user(role="tech"))
    t = services.create_ticket(subject="x")
    assert tech.post(f"/tickets/{t.pk}/delete/", {"confirm": t.number}).status_code == 403
