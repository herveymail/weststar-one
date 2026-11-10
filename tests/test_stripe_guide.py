"""Settings › Payments: the Stripe setup guide, Check connection and Set up the webhook for me."""
import pytest

from apps.billing import stripe_api
from apps.billing.models import StripeEvent
from apps.core.models import Setting

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(client):
    Setting.put("security.require_mfa", "nobody")
    return signed_in(client, make_user(role="admin"))


def test_guide_shows_steps_and_webhook_address(admin):
    page = admin.get("/settings/payments/").content.decode()
    assert "Stripe setup guide" in page and "/stripe/webhook/" in page and "4242 4242 4242 4242" in page
    for e in stripe_api.WEBHOOK_EVENTS:
        assert e in page
    assert 'value="webhook"' not in page  # the button needs a secret key first


def test_mismatched_keys_are_flagged(admin):
    Setting.put("stripe.publishable_key", "pk_live_abc")
    Setting.put("stripe.secret_key", "sk_test_abc", secret=True)
    page = admin.get("/settings/payments/").content.decode()
    assert "don't match" in page and 'value="webhook"' in page


def test_check_connection(admin, monkeypatch):
    Setting.put("stripe.publishable_key", "pk_test_abc")
    Setting.put("stripe.secret_key", "sk_test_abc", secret=True)
    monkeypatch.setattr(stripe_api, "call", lambda m, p, d=None, **kw: {"id": "acct_1", "business_profile": {"name": "Weststar MSP"}, "charges_enabled": True, "payouts_enabled": False})
    r = admin.post("/settings/payments/stripe/", {"what": "check"})
    assert r.status_code == 302
    page = admin.get("/settings/payments/").content.decode()
    assert "Connected to Weststar MSP" in page and "Payouts to your bank" in page


def test_set_up_webhook_for_me_replaces_old_one_and_saves_secret(admin, monkeypatch, settings):
    settings.APP_URL = "https://one.weststarmsp.com"
    Setting.put("stripe.secret_key", "sk_live_abc", secret=True)
    calls = []

    def fake(method, path, data=None, **kw):
        calls.append((method, path))
        if method == "GET":
            return {"data": [{"id": "we_old", "url": "https://one.weststarmsp.com/stripe/webhook/"}, {"id": "we_other", "url": "https://x.test/hook"}]}
        if method == "POST":
            assert data["url"] == "https://one.weststarmsp.com/stripe/webhook/" and data["enabled_events"] == stripe_api.WEBHOOK_EVENTS
            return {"id": "we_new", "secret": "whsec_new123"}
        return {}
    monkeypatch.setattr(stripe_api, "call", fake)
    admin.post("/settings/payments/stripe/", {"what": "webhook"})
    assert ("DELETE", "webhook_endpoints/we_old") in calls and ("DELETE", "webhook_endpoints/we_other") not in calls
    assert Setting.get("stripe.webhook_secret") == "whsec_new123"


def test_rejected_webhook_is_explained(admin, client):
    Setting.put("stripe.webhook_secret", "whsec_abc", secret=True)
    Setting.put("stripe.secret_key", "sk_test_abc", secret=True)
    assert client.post("/stripe/webhook/", b"{}", content_type="application/json", HTTP_STRIPE_SIGNATURE="t=1,v1=bad").status_code == 400
    page = admin.get("/settings/payments/").content.decode()
    assert "turned away" in page
    StripeEvent.objects.create(event_id="evt_1", type="checkout.session.completed")
    Setting.put("stripe.last_webhook_error", "")
    assert "Last message from Stripe" in admin.get("/settings/payments/").content.decode()


def test_only_admins(client):
    Setting.put("security.require_mfa", "nobody")
    tech = signed_in(client, make_user(role="tech"))
    assert tech.post("/settings/payments/stripe/", {"what": "webhook"}).status_code == 403
