"""The "View & pay invoice" link in invoice emails: no sign-in, no client portal needed.

/pay/<token>/      the invoice, Download PDF, Pay now (Stripe Checkout)
/pay/<token>/pdf/  the PDF
The token is long and random (unguessable); only invoices that were sent (not drafts) can be opened.
"""
from django.conf import settings
from django.core.cache import cache
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render

from apps.core.models import Setting

from .models import Invoice


def _invoice(token):
    if Setting.get("billing.public_links", "true") == "false" or len(token) < 20:
        raise Http404
    inv = Invoice.objects.select_related("client").filter(public_token=token, archived_at__isnull=True).exclude(status="Draft").first()
    if inv is None:
        raise Http404
    return inv


def _rate_ok(key, limit, seconds):
    n = cache.get(key, 0)
    if n >= limit:
        return False
    cache.set(key, n + 1, seconds)
    return True


def _private(resp):
    resp["X-Robots-Tag"] = "noindex, nofollow"
    resp["Cache-Control"] = "private, no-store"
    resp["Referrer-Policy"] = "no-referrer"
    return resp


def pay_page(request, token):
    from apps.core.branding import login_brand, logo_url
    from apps.core.net import client_ip

    from . import payments, stripe_api
    inv = _invoice(token)
    base = f"{settings.APP_URL}/pay/{token}/"
    if inv.status == "Sent" and not request.user.is_authenticated:  # staff opening the link don't count as the client viewing it
        Invoice.objects.filter(pk=inv.pk, status="Sent").update(status="Viewed")
        inv.status = "Viewed"
    msg, error = "", ""
    if request.GET.get("session"):
        try:
            msg = payments.finish_checkout(request.GET["session"][:200], expect_client=inv.client)
        except stripe_api.StripeError as e:
            error = f"We couldn't confirm the payment yet ({e}). If you were charged, it will show here shortly."
        inv.refresh_from_db()
    elif request.GET.get("cancelled"):
        error = "Payment cancelled — nothing was charged."
    if request.method == "POST" and inv.status != "Void" and inv.balance > 0:
        if not stripe_api.configured():
            error = "Online payment isn't available right now. Please call us."
        elif not _rate_ok(f"pay:{client_ip(request)}", 20, 3600):
            error = "Too many tries — please wait a bit."
        else:
            try:
                return redirect(payments.checkout_pay(inv, base, base + "?cancelled=1"))
            except stripe_api.StripeError as e:
                error = f"Online payment couldn't start: {e}"
    pays = inv.payments.filter(archived_at__isnull=True).exclude(status="Failed").order_by("-paid_on", "-id")
    return _private(render(request, "billing/pay.html", {
        **login_brand(), "company": Setting.get("company.name", "") or "Weststar MSP", "logo_url": logo_url(),
        "inv": inv, "lines": inv.lines.all(), "balance": inv.balance, "pays": pays, "client": inv.client, "base": base,
        "msg": msg, "error": error, "can_pay": stripe_api.configured(), "instructions": Setting.get("billing.payment_instructions", "")}))


def pay_pdf(request, token):
    from .documents import filename, pdf
    inv = _invoice(token)
    r = HttpResponse(pdf(inv, "invoice"), content_type="application/pdf")
    r["Content-Disposition"] = f'attachment; filename="{filename(inv, "invoice")}"'
    return _private(r)
