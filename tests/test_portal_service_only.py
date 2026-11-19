"""Client portal in "Service calls only" mode (the default): tickets and nothing else."""
import pytest

from apps.accounts import google
from apps.core.models import Setting
from apps.portal import auth

from .helpers import make_user

pytestmark = pytest.mark.django_db


def test_service_only_is_the_default_and_hides_everything_else(settings):
    del settings.PORTAL_SERVICE_ONLY          # tests switch it off globally; real servers don't set it
    assert auth.service_only() is True
    for part in ("invoices", "billing", "contracts", "policies", "assets", "kb", "messages"):
        assert auth.enabled(f"show_{part}") is False, part
    assert auth.enabled() is True              # the portal itself (service calls) stays on
    Setting.put("portal.service_only", "false")
    assert auth.enabled("show_contracts") is True


def test_billing_pages_refuse_in_service_only(client, settings):
    from apps.crm.models import Client

    from .test_portal import make_pu, sign_in
    del settings.PORTAL_SERVICE_ONLY
    make_pu(Client.objects.create(name="Acme"))
    browser = sign_in(client)
    home = browser.get("/client-portal/")
    assert home.status_code == 200
    for bad in (b"/client-portal/invoices/", b"/client-portal/quotes/", b"/client-portal/contracts/", b"/client-portal/autopay/"):
        assert bad not in home.content, bad
    for url in ("/client-portal/invoices/", "/client-portal/autopay/", "/client-portal/quotes/", "/client-portal/contracts/",
                "/client-portal/policies/", "/client-portal/assets/", "/client-portal/help/", "/client-portal/messages/"):
        assert browser.get(url).status_code == 403, url
    assert browser.get("/client-portal/tickets/").status_code == 200


def test_google_button_first_and_missing_hint(client):
    assert google.missing() == ["the OAuth client ID", "the OAuth client secret", "the allowed Google Workspace domain"]
    Setting.put("google.client_id", "x.apps.googleusercontent.com")
    Setting.put("google.client_secret", "s", secret=True)
    assert google.missing() == ["the allowed Google Workspace domain"]
    assert b"Sign in with Google" not in client.get("/login/").content
    Setting.put("google.domains", "weststarmsp.com")
    page = client.get("/login/").content
    assert page.index(b"Sign in with Google") < page.index(b'name="password"')
    assert make_user


def test_signin_warnings(client):
    from apps.crm.models import Client

    from .test_portal import make_pu, sign_in
    staff = client.get("/login/").content
    assert b"Authorized use only" in staff and b"logged and monitored" in staff
    portal = client.get("/client-portal/login/").content
    assert b"HIPAA" in portal and b"not responsible" in portal and b"Do not enter passwords" in portal
    make_pu(Client.objects.create(name="Acme"))
    c = sign_in(client)
    assert b"do not include passwords" in c.get("/client-portal/tickets/?new=1").content or b"do not include passwords" in c.get("/client-portal/tickets/").content
    Setting.put("legal.notice_staff", "Custom warning for {company}.")
    Setting.put("company.name", "Weststar MSP")
    assert b"Custom warning for Weststar MSP." in client.get("/login/").content
    Setting.put("legal.notices_on", "false")
    assert b"Custom warning" not in client.get("/login/").content and b"HIPAA" not in client.get("/client-portal/login/").content
