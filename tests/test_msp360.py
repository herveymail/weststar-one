import pytest

from apps.core.models import Setting
from apps.crm.models import Client
from apps.helpdesk.models import Ticket
from apps.integrations import msp360
from apps.integrations.models import Msp360Company, Msp360Computer, Msp360Plan

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


class Fake:
    def __init__(self):
        self.status, self.last = 2, "2026-10-24T05:00:00Z"
        self.logins = 0

    def __call__(self, method, url, body=None, token=""):
        path = url.split("api.mspbackups.com", 1)[1]
        if path == "/api/Provider/Login":
            self.logins += 1
            ok = body == {"UserName": "apiuser", "Password": "apipass"}
            return (200, {"access_token": "tok"}) if ok else (400, {"error_description": "invalid credentials"})
        assert token == "tok"
        if path == "/api/Companies":
            return 200, [{"Id": "c1", "Name": "Acme Dental LLC"}, {"Id": "c2", "Name": "Nobody Inc"}]
        if path == "/api/Users":
            return 200, [{"ID": "u1", "Email": "agent@acme.test", "Company": "Acme Dental LLC"}]
        if path == "/api/Users/u1/Computers":
            return 200, [{"ComputerName": "SERVER01", "ComputerHID": "h1", "Online": True}]
        if path == "/api/Monitoring":
            return 200, [{"PlanId": "p1", "PlanName": "Image backup", "PlanType": 2, "ComputerName": "SERVER01", "CompanyName": "Acme Dental LLC",
                          "Status": self.status, "LastStart": self.last, "NextStart": "2026-10-25T05:00:00Z",
                          "ErrorMessage": "Disk full" if self.status == 2 else ""}]
        return 404, {"Message": "not found"}


@pytest.fixture
def fake(monkeypatch):
    f = Fake()
    monkeypatch.setattr(msp360, "_http", f)
    for k, v in {"msp360.login": "apiuser", "msp360.enabled": "true"}.items():
        Setting.put(k, v)
    Setting.put("msp360.password", "apipass", secret=True)
    return f


def test_sync_opens_notes_and_resolves_ticket(fake):
    acme = Client.objects.create(name="Acme Dental")
    r = msp360.sync()
    assert r["ok"] and r["companies"] == 2 and r["plans"] == 1 and r["failed"] == 1 and r["tickets_opened"] == 1
    assert Msp360Company.objects.get(pk="c1").client == acme and Msp360Company.objects.get(pk="c2").client is None
    assert Msp360Computer.objects.filter(name="SERVER01").count() == 1
    t = Ticket.objects.get(source="MSP360")
    assert t.client == acme and t.priority == "High" and "Disk full" in t.details and t.category == "Backup"

    assert msp360.sync()["tickets_opened"] == 0          # same failed run: nothing new
    fake.last = "2026-10-25T05:00:00Z"
    r = msp360.sync()
    assert r["tickets_opened"] == 0 and r["tickets_noted"] == 1
    assert t.messages.filter(kind="note", body__contains="still Error").count() == 1

    fake.status, fake.last = 0, "2026-10-26T05:00:00Z"
    assert msp360.sync()["tickets_resolved"] == 1
    t.refresh_from_db()
    assert t.status == "Resolved" and Msp360Plan.objects.get(pk="p1").ticket is None
    assert fake.logins == 1                               # token reused


def test_existing_open_ticket_is_not_duplicated(fake):
    from apps.helpdesk import services
    old = services.create_ticket(subject="Backup error (from old app)", source="MSP360")
    Msp360Plan.objects.create(plan_id="p1", name="Image backup", status=2, ticket=old)
    msp360.sync()
    assert Ticket.objects.filter(source="MSP360").count() == 1


def test_bad_login_is_explained(fake):
    Setting.put("msp360.login", "wrong")
    r = msp360.sync()
    assert not r["ok"] and "API login and password" in r["error"]
    assert Setting.get("msp360.last_error").startswith("Sign-in failed")
    assert not msp360.test()["ok"]


def test_pages_and_buttons(fake, client):
    Setting.put("security.require_mfa", "nobody")
    admin = signed_in(client, make_user(role="admin"))
    assert b"MSP360 isn" not in admin.get("/backups/").content
    r = admin.post("/backups/sync/", {"next": "/backups/"})
    assert r.status_code == 302 and Msp360Plan.objects.count() == 1
    page = admin.get("/backups/").content.decode()
    assert "SERVER01" in page and "Disk full" in page
    acme = Client.objects.create(name="Totally Different")
    admin.post("/backups/companies/", {"client_c2": str(acme.pk), "client_c1": ""})
    assert Msp360Company.objects.get(pk="c2").client == acme and Msp360Company.objects.get(pk="c2").client_set_by_hand
    hub = admin.get("/settings/integrations/").content.decode()
    assert "MSP360 backups" in hub and "Sync now" in hub and "Being rebuilt" in hub
    assert admin.get("/settings/msp360/").status_code == 200
    assert admin.get(f"/clients/{acme.pk}/?tab=Backups").status_code == 200
    assert admin.get("/m/backups/").status_code == 302


def test_tech_cannot_sync(fake, client):
    tech = signed_in(client, make_user(role="viewer"))
    assert tech.post("/backups/sync/").status_code == 403


def test_job_skips_when_off(fake):
    from apps.core.jobs import msp360_sync
    Setting.put("msp360.enabled", "false")
    assert "skipped" in msp360_sync()
