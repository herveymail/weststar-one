"""Invoices and quotes as documents: the page clients see, the PDF, and sending them by email."""
import base64
import os
from decimal import Decimal

from django.conf import settings
from django.template.loader import render_to_string

from apps.core.models import Setting

from .models import Invoice, Quote

KINDS = {"invoice": Invoice, "quote": Quote}


def _logo_src(for_pdf: bool) -> str:
    from apps.core.branding import _dir, logo_url
    name = Setting.get("brand.logo", "")
    if not name:
        return ""
    if not for_pdf:
        return logo_url()
    path = os.path.join(_dir(), name)
    if not os.path.exists(path):
        return ""
    mime = {"svg": "image/svg+xml", "png": "image/png", "webp": "image/webp"}.get(name.rsplit(".", 1)[-1], "image/jpeg")
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def context(doc, kind: str, for_pdf=False) -> dict:
    co = {k: Setting.get(f"company.{k}", "") for k in ("name", "address", "phone", "email", "website")}
    co["email"] = Setting.get("company.billing_email", "") or co["email"]
    co["name"] = co["name"] or "Weststar MSP"
    is_inv = kind == "invoice"
    balance = (doc.total or Decimal(0)) - (getattr(doc, "amount_paid", 0) or Decimal(0)) if is_inv else Decimal(0)
    stamp = ""
    if is_inv and doc.status in ("Paid", "Void"):
        stamp = doc.status.upper()
    elif is_inv and doc.status == "Overdue":
        stamp = "OVERDUE"
    elif not is_inv and doc.status in ("Accepted", "Declined"):
        stamp = doc.status.upper()
    pct = Decimal(Setting.get("billing.quote_deposit_pct", "0") or 0) if not is_inv else Decimal(0)
    contact = doc.client.contacts.filter(archived_at__isnull=True, role="Billing").first() or doc.client.contacts.filter(archived_at__isnull=True, is_primary=True).first()
    terms = Setting.get("billing.invoice_terms" if is_inv else "billing.quote_terms", "")
    if not is_inv and Setting.get("billing.quote_disclaimer", ""):
        terms = (terms + "\n\n" + Setting.get("billing.quote_disclaimer", "")).strip()
    return {
        "doc": doc, "kind": kind, "title": "Invoice" if is_inv else "Quote", "co": co, "logo_src": _logo_src(for_pdf),
        "accent": Setting.get("brand.color", "") or "#0A4B85", "page_size": "letter",
        "date": doc.invoice_date if is_inv else doc.quote_date, "due": doc.due_date if is_inv else doc.expires_on,
        "lines": list(doc.lines.all()), "balance": balance, "stamp": stamp, "bill_to_contact": contact.name if contact else "",
        "tax_label": Setting.get("billing.tax_label", "") or "Tax",
        "deposit_pct": pct, "deposit": (doc.total * pct / 100).quantize(Decimal("0.01")) if pct and doc.total else 0,
        "pay_url": f"{settings.PORTAL_BASE}/invoices/{doc.pk}/" if is_inv else "",
        "instructions": Setting.get("billing.payment_instructions", "") if is_inv else "",
        "terms": terms, "footer": Setting.get("billing.invoice_footer" if is_inv else "billing.quote_footer", ""),
    }


def pdf(doc, kind: str) -> bytes:
    import logging
    for name in ("fontTools", "weasyprint"):
        logging.getLogger(name).setLevel(logging.WARNING)
    from weasyprint import HTML
    html = render_to_string("billing/pdf.html", context(doc, kind, for_pdf=True))
    return HTML(string=html, base_url=None).write_pdf()


def filename(doc, kind) -> str:
    return f"{'Invoice' if kind == 'invoice' else 'Quote'}-{doc.number or doc.pk}.pdf"


def default_subject(doc, kind) -> str:
    company = Setting.get("company.name", "") or "Weststar MSP"
    if kind == "invoice":
        tpl = Setting.get("billing.invoice_email_subject", "") or "Invoice {number} from {company}"
        return tpl.replace("{number}", doc.number or "").replace("{company}", company).replace("{total}", f"${doc.total:,.2f}").replace("{due_date}", f"{doc.due_date:%b %d, %Y}")
    tpl = Setting.get("billing.quote_email_subject", "") or "Quote {number} from {company}"
    return tpl.replace("{number}", doc.number or "").replace("{company}", company).replace("{total}", f"${doc.total:,.2f}")


def default_message(doc, kind) -> str:
    first = ""
    c = doc.client.contacts.filter(archived_at__isnull=True, role="Billing").first() or doc.client.contacts.filter(archived_at__isnull=True, is_primary=True).first()
    if c:
        first = c.name.split(" ")[0]
    hi = f"Hi {first}," if first else "Hello,"
    if kind == "invoice":
        due = f" It's due {doc.due_date:%B %d, %Y}." if doc.due_date else ""
        return f"{hi}\n\nAttached is invoice {doc.number} for ${doc.total:,.2f}.{due}\n\nYou can view and pay it online with the button below. Thank you for your business!"
    return f"{hi}\n\nHere is quote {doc.number} for ${doc.total:,.2f}. You can review and approve it online with the button below.\n\nLet us know if you have any questions."
