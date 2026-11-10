"""Settings › Legal & terms: terms on invoices and quotes, portal terms + privacy, staff agreements, workplace notices."""
from datetime import date
from decimal import Decimal

import pytest

from apps.billing.models import Invoice, InvoiceLine, invoice_link
from apps.core import legal
from apps.core.models import LegalAcceptance, Setting
from apps.crm.models import Client
from apps.portal.models import PortalUser

from .helpers import make_user, signed_in

pytestmark = pytest.mark.django_db
PW = "Correct-horse-battery-9"


def test_state_follows_the_clients_office():
    assert legal.jurisdiction(Client(state="TX")) == ("Texas", "El Paso")
    assert legal.jurisdiction(Client(address="221 N Kansas St, El Paso, Texas 79901")) == ("Texas", "El Paso")
    assert legal.jurisdiction(Client(state="AZ")) == ("Arizona", "Maricopa")
    assert legal.jurisdiction(Client()) == ("Arizona", "Maricopa")
    Setting.put("legal.az_county", "Pima")
    assert legal.jurisdiction(Client(state="Arizona")) == ("Arizona", "Pima")


def test_invoice_pdf_page_and_pay_page_carry_the_terms(client):
    Setting.put("security.require_mfa", "nobody")
    tx = Client.objects.create(name="El Paso Co", state="TX")
    inv = Invoice.objects.create(client=tx, number="INV-77", status="Sent", invoice_date=date.today(), due_date=date.today())
    InvoiceLine.objects.create(invoice=inv, description="Support", qty=1, rate=Decimal("100"))
    inv.recalc()
    web = signed_in(client, make_user(role="admin"))
    page = web.get(f"/billing/invoice/{inv.pk}/").content.decode()
    assert "Limitation of liability" in page and "laws of the State of Texas" in page and "El Paso County" in page
    assert web.get(f"/billing/invoice/{inv.pk}/pdf/").content[:5] == b"%PDF-"
    web.post("/logout/")
    pay = client.get("/pay/" + invoice_link(inv).rsplit("/pay/", 1)[1]).content.decode()
    assert "Terms &amp; Conditions" in pay and "Texas" in pay and "/legal/privacy/" in pay


def test_public_pages():
    from django.test import Client as Browser
    b = Browser()
    assert b"Privacy Policy" in b.get("/legal/privacy/").content
    assert b"Client Portal Terms of Use" in b.get("/legal/terms/").content
    assert b.get("/legal/nope/").status_code == 404


def test_portal_asks_once_and_again_after_a_change(client, settings):
    settings.LEGAL_GATES = True
    c = Client.objects.create(name="Acme")
    pu = PortalUser(client=c, name="Pat", email="pat@acme.test")
    pu.set_password(PW)
    pu.save()
    client.post("/client-portal/login/", {"email": "pat@acme.test", "password": PW, "action": "password"})
    r = client.get("/client-portal/tickets/")
    assert r.status_code == 302 and r["Location"].startswith("/client-portal/agree/")
    assert client.post("/client-portal/agree/?next=/client-portal/tickets/", {})  # no tick: stays
    r = client.post("/client-portal/agree/?next=/client-portal/tickets/", {"agree": "1"})
    assert r["Location"] == "/client-portal/tickets/" and client.get("/client-portal/tickets/").status_code == 200
    assert set(LegalAcceptance.objects.filter(portal_user=pu).values_list("doc", flat=True)) == {"portal_terms", "privacy"}
    Setting.put("legal.portal_terms", legal.text("portal_terms") + "\n\nNew paragraph.")
    assert client.get("/client-portal/tickets/")["Location"].startswith("/client-portal/agree/")
    assert b"Our terms have changed" in client.get("/client-portal/agree/").content


def test_staff_sign_agreements_and_hr_sees_them(client, settings):
    settings.LEGAL_GATES = True
    Setting.put("security.require_mfa", "nobody")
    admin = make_user(role="admin")
    web = signed_in(client, admin)
    r = web.get("/tickets/")
    assert r.status_code == 302 and r["Location"].startswith("/account/agreements/")
    page = web.get("/account/agreements/").content.decode()
    assert "Confidentiality" in page and "Handbook" in page
    r = web.post("/account/agreements/?next=/tickets/", {"signed_name": "Casey Hervey", "agree_staff_confidentiality": "1", "agree_handbook_ack": "1"})
    assert r["Location"] == "/tickets/" and web.get("/tickets/").status_code == 200
    assert LegalAcceptance.objects.filter(user=admin, signed_name="Casey Hervey").count() == 2
    assert "Casey Hervey" in web.get("/hr/?tab=agreements").content.decode()
    assert "Signed" in web.get("/my-hr/?tab=agreements", HTTP_HX_REQUEST="true").content.decode()


def test_workplace_notices_follow_headcount(client):
    Setting.put("security.require_mfa", "nobody")
    Setting.put("legal.employee_count", "8")
    Setting.put("legal.tx_workers_comp", "no")
    by = {n["title"]: n for n in legal.notices()}
    assert not by['"Know Your Rights": Workplace Discrimination is Illegal']["applies"]  # under 15
    assert not by["Employee Rights Under the Family and Medical Leave Act"]["applies"]
    assert not by["Employer's Notice of Ombudsman Program"]["applies"]
    assert by["Reporting Workplace Violence (English/Español)"]["applies"]
    web = signed_in(client, make_user())
    html = web.get("/my-hr/?tab=notices", HTTP_HX_REQUEST="true").content.decode()
    assert "Earned Paid Sick Time" in html and "twc.texas.gov" in html


def test_editing_a_text_updates_its_date(client):
    Setting.put("security.require_mfa", "nobody")
    web = signed_in(client, make_user(role="admin"))
    page = web.get("/settings/legal/").content.decode()
    assert "Invoice terms &amp; conditions" in page
    web.post("/settings/legal/", {"legal.privacy": "## Privacy\\nShort.", "legal.az_county": "Maricopa", "legal.tx_county": "El Paso"})
    assert Setting.get("legal.privacy.updated") == date.today().isoformat()
