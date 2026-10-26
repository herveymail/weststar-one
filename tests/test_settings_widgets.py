import pytest

from apps.core.models import Setting

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db


@pytest.fixture
def admin(client):
    Setting.put("security.require_mfa", "nobody")
    return signed_in(client, make_user(role="admin"))


def test_every_settings_page_renders(admin):
    from apps.core.settings_catalog import all_pages
    for _g, _t, item in all_pages():
        if isinstance(item[3], list):
            r = admin.get(f"/settings/{item[0]}/")
            assert r.status_code == 200, item[0]


def test_hours_days_and_time(admin):
    r = admin.post("/settings/afterhours/", {"helpdesk.open": "07:30", "helpdesk.close": "17:00", "helpdesk.days": ["Mon", "Wed", "Fri"], "tickets.afterhours_message": "x"})
    assert r.status_code == 302
    assert Setting.get("helpdesk.days") == "Mon,Wed,Fri" and Setting.get("helpdesk.open") == "07:30"
    page = admin.get("/settings/afterhours/").content.decode()
    assert 'value="Wed" checked' in page and 'value="Tue" checked' not in page
    admin.post("/settings/afterhours/", {"helpdesk.open": "7am", "helpdesk.close": "17:00"})
    assert Setting.get("helpdesk.open") == "07:30"  # bad time rejected


def test_preset_and_custom(admin):
    admin.post("/settings/sla/", {"tickets.sla_critical_min": "30"})
    assert Setting.get("tickets.sla_critical_min") == "30"
    admin.post("/settings/sla/", {"tickets.sla_critical_min": "__custom__", "tickets.sla_critical_min__custom": "45"})
    assert Setting.get("tickets.sla_critical_min") == "45"
    page = admin.get("/settings/sla/").content.decode()
    assert 'value="__custom__" selected' in page and 'value="45"' in page
    admin.post("/settings/sla/", {"tickets.sla_critical_min": "__custom__", "tickets.sla_critical_min__custom": "soon"})
    assert Setting.get("tickets.sla_critical_min") == "45"


def test_tags_add_and_remove(admin):
    Setting.put("tickets.categories", "Network\nEmail\nPrinters")
    admin.post("/settings/tickets/", {"tickets.categories": ["Network", "Printers"], "tickets.categories__add": "Backup, email, Backup"})
    assert Setting.get("tickets.categories") == "Network\nPrinters\nBackup\nemail"
    admin.post("/settings/signin/", {"google.domains__add": "weststarmsp.com, dsotv.com", "security.idle_minutes": "60"})
    assert Setting.get("google.domains") == "weststarmsp.com, dsotv.com"


def test_colour_money_timezone(admin):
    admin.post("/settings/branding/", {"brand.color": "__custom__", "brand.color__custom": "#123ABC"})
    assert Setting.get("brand.color") == "#123ABC"
    admin.post("/settings/branding/", {"brand.color": "__custom__", "brand.color__custom": "red;}"})
    assert Setting.get("brand.color") == "#123ABC"
    admin.post("/settings/numbers/", {"billing.hourly_rate": "$1,250.50", "billing.default_tax_rate": "8.6%"})
    assert Setting.get("billing.hourly_rate") == "1250.50" and Setting.get("billing.default_tax_rate") == "8.6"
    admin.post("/settings/company/", {"app.timezone": "America/Phoenix", "company.name": "W"})
    assert Setting.get("app.timezone") == "America/Phoenix"
    admin.post("/settings/company/", {"app.timezone": "Mars/Base", "company.name": "W"})
    assert Setting.get("app.timezone") == "America/Phoenix"


def test_secret_shows_saved_not_value(admin):
    Setting.put("stripe.secret_key", "sk_live_abc", secret=True)
    page = admin.get("/settings/payments/").content.decode()
    assert "✓ Saved" in page and "sk_live_abc" not in page


def test_ui_style_picker(admin):
    admin.post("/profile/", {"ui_style": "terminal"})
    page = admin.get("/profile/").content.decode()
    assert 'data-style="terminal"' in page and "JetBrains+Mono" in page
    admin.post("/profile/", {"ui_style": "nope"})
    assert 'data-style="terminal"' in admin.get("/").content.decode()


def test_forms_opened_directly_show_in_the_app_and_have_dates(admin):
    from apps.crm.models import Client
    r = admin.get("/m/clients/new/")
    assert r.status_code == 302 and r["Location"].startswith("/m/clients/?open_form=")
    page = admin.get(r["Location"]).content.decode()
    assert 'hx-get="/m/clients/new/"' in page
    assert 'hx-get="https://evil.test/"' not in admin.get("/m/clients/?open_form=https://evil.test/").content.decode()
    assert admin.get("/tickets/new/").status_code == 302
    Client.objects.create(name="Acme")
    Setting.put("billing.net_terms", "15")
    form = admin.get("/m/invoices/new/", HTTP_HX_REQUEST="true").content.decode()
    from datetime import timedelta

    from django.utils import timezone
    today = timezone.localdate()
    assert f'value="{today:%Y-%m-%d}"' in form and f'value="{today + timedelta(days=15):%Y-%m-%d}"' in form
    assert form.index('name="client"') < form.index('name="tax_rate"')


def test_settings_pages_show_the_real_defaults(admin):
    page = admin.get("/settings/ai/").content.decode()
    assert 'name="ai.summary" checked' in page or 'name="ai.summary"  checked' in page or ('name="ai.summary"' in page and "checked" in page.split('name="ai.summary"')[1][:20])
