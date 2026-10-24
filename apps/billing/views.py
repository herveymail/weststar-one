"""Stripe webhook (no sign-in; checked by Stripe's signature) and staff payment actions."""
import json
import logging
from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from django.conf import settings

from apps.core import mail
from apps.core.audit import audit
from apps.core.models import Setting
from apps.core.permissions import can
from apps.crm.models import Client

from . import payments, stripe_api
from .models import Invoice

log = logging.getLogger("weststar.payments")


@csrf_exempt
@require_POST
def stripe_webhook(request):
    try:
        event = stripe_api.verify_webhook(request.body, request.headers.get("Stripe-Signature", ""))
    except (stripe_api.StripeError, ValueError, json.JSONDecodeError) as e:
        log.warning("Stripe webhook rejected: %s", e)
        return HttpResponse(status=400)
    try:
        payments.handle_event(event)
    except stripe_api.StripeError as e:
        log.error("Stripe webhook %s failed: %s", event.get("type"), e)
        return HttpResponse(status=500)  # Stripe retries
    return HttpResponse("ok")


@login_required
@require_POST
def client_autopay(request, pk):
    """Client page › AutoPay box: send a setup link, charge now, or turn AutoPay off."""
    if not can(request.user, "billing", "edit"):
        raise PermissionDenied
    c = get_object_or_404(Client, pk=pk)
    action = request.POST.get("action")
    back = f"/clients/{c.pk}/?tab=Invoices"
    try:
        if action == "link":
            link = payments.make_link(c, by=request.user)
            to = [a.strip() for a in request.POST.get("to", "").replace(";", ",").split(",") if "@" in a]
            if to and mail.send(to, f"Set up AutoPay with {mail.from_address().split('<')[0].strip() or 'us'}", "email/autopay_setup_link",
                                {"c": c, "link": link, "expires": timezone.now() + timedelta(days=7)}):
                messages.success(request, f"Emailed the AutoPay setup link to {', '.join(to)}.")
            else:
                messages.info(request, f"Here's the AutoPay setup link (works once, for 7 days): {link}")
            audit(request, "autopay_link", "client", c.pk, f"AutoPay setup link made for {c.name}", area="billing")
        elif action == "off":
            payments.turn_off(c, by=request.user.name)
            messages.success(request, "AutoPay is off and the card was removed from Stripe.")
        elif action == "charge":
            inv = get_object_or_404(Invoice, pk=request.POST.get("invoice") or 0, client=c)
            p = payments.charge_invoice(inv, source="staff", by=request.user)
            if p and p.status == "Succeeded":
                messages.success(request, f"Charged ${p.amount} to {c.autopay_label} for {inv.number}.")
            elif p:
                messages.info(request, f"Bank payment of ${p.amount} started for {inv.number}; it clears in a few business days.")
            else:
                inv.refresh_from_db()
                messages.error(request, f"The charge didn't go through: {inv.autopay_error or 'declined'}")
    except stripe_api.StripeError as e:
        messages.error(request, str(e))
    return redirect(back)


# ── invoice / quote documents ──
def _doc_or_404(request, kind, pk, need="view"):
    from django.http import Http404

    from .documents import KINDS
    if kind not in KINDS:
        raise Http404
    if not can(request.user, "billing", need):
        raise PermissionDenied
    return get_object_or_404(KINDS[kind].objects.select_related("client"), pk=pk)


@login_required
def document(request, kind, pk):
    from django.shortcuts import render

    from .documents import context
    doc = _doc_or_404(request, kind, pk)
    ctx = context(doc, kind)
    ctx.update(can_edit=can(request.user, "billing", "edit"), slug="invoices" if kind == "invoice" else "quotes",
               payments=doc.payments.filter(archived_at__isnull=True).order_by("-paid_on") if kind == "invoice" else [],
               approvals=list(doc.approvals.order_by("-created_at")) if kind == "quote" else [])
    return render(request, "billing/document.html", ctx)


@login_required
def document_pdf(request, kind, pk):
    from .documents import filename, pdf
    doc = _doc_or_404(request, kind, pk)
    r = HttpResponse(pdf(doc, kind), content_type="application/pdf")
    disp = "inline" if request.GET.get("view") else "attachment"
    r["Content-Disposition"] = f'{disp}; filename="{filename(doc, kind)}"'
    return r


@login_required
def document_send(request, kind, pk):
    """Send an invoice/quote: edit the email, see exactly what goes out, PDF attached."""
    from django.shortcuts import render

    from apps.billing.payments import _billing_people

    from . import documents
    doc = _doc_or_404(request, kind, pk, "edit")
    if doc.status == "Void":
        messages.error(request, "This invoice is void.")
        return redirect(f"/billing/{kind}/{pk}/")
    link = f"{settings.PORTAL_BASE}/{'invoices' if kind == 'invoice' else 'quotes'}/{doc.pk}/"
    form = {"to": ", ".join(_billing_people(doc.client)), "cc": "", "subject": documents.default_subject(doc, kind),
            "message": documents.default_message(doc, kind), "attach": True}
    error = ""
    if request.method == "POST":
        form = {"to": request.POST.get("to", ""), "cc": request.POST.get("cc", ""), "subject": request.POST.get("subject", "")[:200],
                "message": request.POST.get("message", "")[:10000], "attach": request.POST.get("attach") == "1"}
        to = [a.strip() for a in form["to"].replace(";", ",").split(",") if "@" in a]
        cc = [a.strip() for a in form["cc"].replace(";", ",").split(",") if "@" in a]
        if request.POST.get("preview"):
            pass
        elif not to:
            error = "Add at least one email address."
        elif not doc.lines.exists():
            error = "Add line items before sending."
        else:
            files = [(documents.filename(doc, kind), documents.pdf(doc, kind), "application/pdf")] if form["attach"] else None
            ctx = {"doc": doc, "message": form["message"], "link": link, "sender": request.user.name, "meta": f"{documents.context(doc, kind)['title']} {doc.number}"}
            if mail.send(to, form["subject"], f"email/{kind}", ctx, cc=cc, attachments=files):
                if doc.status == "Draft":
                    type(doc).objects.filter(pk=doc.pk).update(status="Sent")
                audit(request, "send", kind, doc.pk, f"Emailed {kind} {doc.number} to {', '.join(to + cc)}", area="billing")
                messages.success(request, f"Sent {doc.number} to {', '.join(to)}.")
                return redirect(f"/billing/{kind}/{pk}/")
            error = "The email couldn't be sent. Check Settings › Email sending (Send test email)."
    preview_ctx = {"doc": doc, "message": form["message"], "link": link, "sender": request.user.name, "company": Setting.get("company.name") or "Weststar MSP",
                   "meta": f"{'Invoice' if kind == 'invoice' else 'Quote'} {doc.number}"}
    from django.template.loader import render_to_string
    import re

    from django.utils.safestring import mark_safe
    email_html = mail.render_html(f"email/{kind}", preview_ctx, render_to_string(f"email/{kind}.txt", preview_ctx), form["subject"])
    m = re.search(r"<body[^>]*>(.*)</body>", email_html, re.S)
    email_html = mark_safe(m.group(1) if m else email_html)  # our own template; every value in it is escaped
    return render(request, "billing/send.html", {"doc": doc, "kind": kind, "form": form, "error": error, "email_html": email_html,
                                                  "title": "Invoice" if kind == "invoice" else "Quote", "mail_ok": mail.configured()})
