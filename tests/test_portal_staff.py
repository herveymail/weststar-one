import pytest

from apps.core.models import Setting, get_secret, set_secret
from apps.crm.models import Client, Contact
from apps.helpdesk.models import Queue
from apps.portal.models import PortalGroup, PortalUser
from apps.tools.models import SecureMessage

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(client):
    Setting.put("security.require_mfa", "nobody")
    return signed_in(client, make_user(role="admin"))


def test_client_portal_tab_add_and_manage(admin):
    acme = Client.objects.create(name="Acme")
    ct = Contact.objects.create(client=acme, name="Pat", email="pat@acme.test")
    r = admin.get(f"/clients/{acme.pk}/portal/")
    assert r.status_code == 200 and b"Give someone portal access" in r.content and b"/client-portal/" in r.content
    assert PortalGroup.objects.count() == 5
    g = PortalGroup.objects.get(name="Billing & Admin")
    admin.post(f"/clients/{acme.pk}/portal/", {"action": "add", "contact": ct.pk, "group": g.pk, "invite": "on"})
    u = PortalUser.objects.get()
    assert u.email == "pat@acme.test" and u.group == g and u.contact == ct and u.can("billing")
    admin.post(f"/clients/{acme.pk}/portal/", {"action": "save", "user": u.pk, "name": "Pat Lee", "group": "", "can_kb": "on"})
    u.refresh_from_db()
    assert u.group is None and u.can("kb") and not u.can("billing")
    admin.post(f"/clients/{acme.pk}/portal/", {"action": "toggle", "user": u.pk})
    u.refresh_from_db()
    assert not u.is_active
    assert b"Loading" in admin.get(f"/clients/{acme.pk}/?tab=Portal").content


def test_groups_and_queues_settings(admin):
    admin.get("/settings/portal_groups/")
    g = PortalGroup.objects.get(name="View Only")
    admin.post("/settings/portal_groups/", {"id": g.pk, "name": "View Only", "can_assets": "on"})
    g.refresh_from_db()
    assert g.can_assets and not g.can_kb
    admin.post("/settings/queues/", {"name": "Level 1", "portal_label": "Something's broken", "keywords": "printer, wifi", "is_default": "on", "sla_enabled": "on", "active": "on", "color": "#ff0000"})
    q = Queue.objects.get()
    assert q.is_default and q.portal_label and q.color == "#ff0000"
    assert b"Level 1" in admin.get("/settings/queues/").content


def test_staff_secure_message_thread(admin):
    acme = Client.objects.create(name="Acme")
    pu = PortalUser.objects.create(client=acme, name="Pat", email="pat@acme.test", can_messages=True)
    root = SecureMessage(client=acme, subject="Wifi", direction="Inbound", status="Unread", portal_user=pu)
    set_secret(root, "body", "what's the password")
    root.save()
    r = admin.get("/m/messages/")
    assert f"/messages/{root.pk}/".encode() in r.content
    r = admin.get(f"/messages/{root.pk}/")
    assert b"what&#x27;s the password" in r.content
    admin.post(f"/messages/{root.pk}/", {"body": "It's hunter2"})
    rep = root.replies.get()
    assert rep.direction == "Outbound" and rep.portal_user == pu and get_secret(rep, "body") == "It's hunter2"


def test_old_portal_address_redirects(client):
    r = client.get("/portal/tickets/")
    assert r.status_code == 301 and r["Location"] == "/client-portal/tickets/"
    assert client.get("/portal")["Location"] == "/client-portal/"
