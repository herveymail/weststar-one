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

from apps.core import mail
from apps.core.audit import audit
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
