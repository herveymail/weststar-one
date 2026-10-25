from datetime import date, timedelta
from decimal import Decimal

import pytest

from apps.billing import documents, latefees
from apps.billing.models import Invoice, InvoiceLine
from apps.core.models import Setting
from apps.crm.models import Client, ClientNote

pytestmark = pytest.mark.django_db
TODAY = date(2026, 10, 24)


@pytest.fixture(autouse=True)
def rules():
    for k, v in {"billing.late_fee_enabled": "true", "billing.late_fee_type": "flat", "billing.late_fee_flat": "45.00",
                 "billing.late_fee_grace_days": "10", "billing.late_fee_repeat": "true", "import.late_fees_synced": "x"}.items():
        Setting.put(k, v)


def inv(days_past_due, client=None, status="Sent", **kw):
    c = client or Client.objects.create(name="Acme", email="ap@acme.test")
    i = Invoice.objects.create(number=f"INV-{Invoice.objects.count() + 1}", client=c, status=status, invoice_date=TODAY - timedelta(days=days_past_due + 15),
                               due_date=TODAY - timedelta(days=days_past_due), **kw)
    InvoiceLine.objects.create(invoice=i, description="Support", qty=1, rate=Decimal("100"), taxable=False)
    i.recalc()
    return i


def test_charges_45_after_10_days_once_then_every_30():
    late, edge, fresh = inv(11), inv(10), inv(3)
    r = latefees.run(TODAY)
    assert r["charged"] == 1
    late.refresh_from_db()
    assert late.total == Decimal("145.00") and late.status == "Overdue" and late.last_late_fee_on == TODAY
    assert late.lines.filter(description__startswith="Late fee").count() == 1
    assert ClientNote.objects.filter(client=late.client, title__contains="$45.00").exists()
    assert edge.lines.count() == fresh.lines.count() == 1
    assert latefees.run(TODAY)["charged"] == 0                      # no double charge the same day
    assert latefees.run(TODAY + timedelta(days=29))["charged"] == 2   # the other two are now past 10 days; the first waits for 30
    late.refresh_from_db()
    assert late.lines.count() == 2
    latefees.run(TODAY + timedelta(days=30))
    late.refresh_from_db()
    assert late.lines.count() == 3 and late.total == Decimal("190.00")


def test_skips_paid_exempt_void_and_old_app_fees():
    c = Client.objects.create(name="Exempt", late_fee_exempt=True)
    inv(40, client=c)
    inv(40, status="Paid")
    inv(40, status="Void")
    old = inv(40)
    InvoiceLine.objects.create(invoice=old, description="Late Fee (Oct 19, 2026)", qty=1, rate=35)
    assert latefees.run(TODAY)["charged"] == 0
    old.refresh_from_db()
    assert old.last_late_fee_on == date(2026, 10, 19)


def test_imported_invoices_wait_for_reimport():
    Setting.objects.filter(key="import.late_fees_synced").delete()
    inv(40, legacy_id=999)
    mine = inv(40)
    r = latefees.run(TODAY)
    assert r["charged"] == 1 and r["waiting_for_import"] == 1
    mine.refresh_from_db()
    assert mine.last_late_fee_on == TODAY


def test_off_does_nothing():
    Setting.put("billing.late_fee_enabled", "false")
    inv(40)
    assert latefees.run(TODAY)["charged"] == 0


def test_invoice_shows_legal_terms_and_late_notice():
    Setting.put("billing.invoice_terms", "A late fee of {late_fee} applies after {grace_days} days.")
    Setting.put("billing.late_notice", "Pay now or {late_fee} more.")
    Setting.put("billing.contract_state", "Arizona")
    Setting.put("billing.contract_county", "Maricopa")
    i = inv(20, status="Overdue")
    ctx = documents.context(i, "invoice")
    assert ctx["terms"] == "A late fee of $45.00 applies after 10 days."
    assert ctx["late_notice"] == "Pay now or $45.00 more."
    assert "State of Arizona" in ctx["law"] and "Maricopa County" in ctx["law"]
    assert ctx["terms_label"] == "Net 15"
    Setting.put("billing.invoice_terms", "Pay on time.")
    assert "$45.00" in documents.context(i, "invoice")["late_policy"]
    paid = inv(20, status="Paid")
    assert documents.context(paid, "invoice")["late_notice"] == ""
