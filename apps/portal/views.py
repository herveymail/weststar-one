"""Client portal pages. Every query is limited to the signed-in person's own company (and, for tickets,
to their own tickets unless they may see all company tickets)."""
import base64
import hashlib
import io
import secrets as pysecrets
from datetime import timedelta

import pyotp
import qrcode
import qrcode.image.svg
from django.conf import settings
from django.contrib.auth.password_validation import validate_password
from django.core.cache import cache
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import F, Q, Sum
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.billing.models import Contract, Invoice, Policy, Quote
from apps.core import mail
from apps.core.audit import audit
from apps.core.crypto import decrypt, encrypt
from apps.core.models import Setting, get_secret, set_secret
from apps.core.net import client_ip
from apps.crm.models import Asset, Contact
from apps.files.models import INLINE_EXT, Upload
from apps.helpdesk import services
from apps.helpdesk.models import OPEN_STATUSES, Queue, Ticket
from apps.tools.models import KbArticle, SecureMessage

from . import auth
from .auth import enabled, portal_login_required
from .models import ContractSignature, PolicyAck, PortalGroup, PortalUser, QuoteApproval

UNPAID = ["Sent", "Viewed", "Partial", "Overdue"]
PRIORITY_CHOICES = [("Low", "Low — when you can"), ("Medium", "Medium — it's slowing me down"), ("High", "High — I can't work"),
                    ("Critical", "Critical — the whole office is down")]


def _ctx(request, **extra) -> dict:
    pu = request.portal_user
    ctx = {"pu": pu, "company": Setting.get("company.name") or "Weststar MSP", "company_phone": Setting.get("company.phone", ""),
           "nav": [], "active": (request.path.split("/") + ["", "", ""])[2] or "home", **extra}
    if pu:
        from .models import PERMS
        ctx["can"] = {p: pu.can(p) for p, _l in PERMS}
        nav = [("home", "Home", "/client-portal/"), ("tickets", "Tickets", "/client-portal/tickets/")]
        if pu.can("billing") and enabled("show_billing"):
            nav += [("invoices", "Invoices", "/client-portal/invoices/"), ("quotes", "Quotes", "/client-portal/quotes/")]
        if pu.can("contracts") and enabled("show_contracts"):
            nav.append(("contracts", "Contracts", "/client-portal/contracts/"))
        if pu.can("policies") and enabled("show_policies"):
            nav.append(("policies", "Policies", "/client-portal/policies/"))
        if pu.can("assets") and enabled("show_assets"):
            nav.append(("assets", "Assets", "/client-portal/assets/"))
        if pu.can("kb") and enabled("show_kb"):
            nav.append(("help", "Help", "/client-portal/help/"))
        if pu.can("messages") and enabled("show_messages"):
            nav.append(("messages", "Messages", "/client-portal/messages/"))
        ctx["nav"] = nav
        ctx["open_count"] = my_tickets(pu).filter(status__in=OPEN_STATUSES).count()
        ctx["unread_count"] = _threads(pu).filter(replies__direction="Outbound", replies__client_read_at__isnull=True).distinct().count() \
            + _threads(pu).filter(direction="Outbound", client_read_at__isnull=True).count() if pu.can("messages") else 0
    return ctx


def my_tickets(pu: PortalUser):
    qs = Ticket.objects.filter(client=pu.client, merged_into__isnull=True)
    if not pu.can("all_tickets"):
        cond = Q(contact_email__iexact=pu.email)
        if pu.contact_id:
            cond |= Q(contact_id=pu.contact_id)
        qs = qs.filter(cond)
    return qs


def _notify_staff(what: str, detail: str, link: str):
    to = Setting.get("email.support_address")
    if to:
        mail.send(to, what, "email/portal_staff_notice", {"what": what, "detail": detail, "link": f"{settings.APP_URL}{link}"})


def _rate_ok(key: str, limit: int, seconds: int) -> bool:
    n = cache.get(key, 0)
    if n >= limit:
        return False
    cache.set(key, n + 1, seconds)
    return True


# ── sign in / out ──
def login_view(request):
    if not enabled():
        return render(request, "portal/closed.html", _ctx(request))
    if request.portal_user:
        return redirect("/client-portal/")
    error, sent = "", False
    if request.method == "POST":
        if request.POST.get("action") == "link" and enabled("magic_links"):
            email = request.POST.get("email", "").strip().lower()
            if _rate_ok(f"plink:{client_ip(request)}", 10, 3600) and _rate_ok(f"plink:{email}", 3, 900):
                u = PortalUser.objects.filter(email__iexact=email, is_active=True).first()
                if u:
                    auth.send_link(u, "magic")
            sent = True  # same answer whether or not the email has an account
        else:
            u = auth.check_password_step(request, request.POST.get("email", ""), request.POST.get("password", ""))
            if u:
                auth.start(request, u, mfa_ok=not u.mfa_enabled)
                return redirect("/client-portal/login/code/" if u.mfa_enabled else "/client-portal/")
            error = auth.GENERIC_FAIL
    return render(request, "portal/login.html", _ctx(request, error=error, sent=sent, expired=request.GET.get("expired"),
                                                      magic=enabled("magic_links") and mail.configured()))


def login_code(request):
    pu = getattr(request, "portal_pending", None)
    if not pu:
        return redirect("/client-portal/")
    error = ""
    if request.method == "POST":
        if auth.verify_totp(pu, request.POST.get("code", "")):
            auth.start(request, pu, mfa_ok=True)
            return redirect("/client-portal/")
        error = "That code isn't right. Use the newest code from your authenticator app."
    return render(request, "portal/login_code.html", _ctx(request, error=error))


@require_POST
def logout_view(request):
    auth.logout(request)
    return redirect("/client-portal/login/")


def forgot(request):
    sent = False
    if request.method == "POST":
        email = request.POST.get("email", "").strip().lower()
        if _rate_ok(f"preset:{client_ip(request)}", 10, 3600) and _rate_ok(f"preset:{email}", 3, 900):
            u = PortalUser.objects.filter(email__iexact=email, is_active=True).first()
            if u:
                auth.send_link(u, "reset")
        sent = True
    return render(request, "portal/forgot.html", _ctx(request, sent=sent))


def link_view(request, token):
    """Emailed links: sign-in link, password reset and invitation."""
    peek = auth.use_token(token, consume=False)
    if peek is None:
        return render(request, "portal/link_bad.html", _ctx(request), status=410)
    if peek.kind == "magic":
        if request.method != "POST":  # one click on a button, so mail scanners that open links don't use it up
            return render(request, "portal/link_confirm.html", _ctx(request, who=peek.user))
        t = auth.use_token(token, kinds=("magic",))
        if t is None:
            return render(request, "portal/link_bad.html", _ctx(request), status=410)
        auth.start(request, t.user, mfa_ok=not t.user.mfa_enabled)
        return redirect("/client-portal/login/code/" if t.user.mfa_enabled else "/client-portal/")
    error = ""
    if request.method == "POST":
        new, again = request.POST.get("new", ""), request.POST.get("again", "")
        if new != again:
            error = "The two passwords don't match."
        else:
            try:
                validate_password(new)
            except ValidationError as e:
                error = " ".join(e.messages)
        if not error:
            t = auth.use_token(token, kinds=(peek.kind,))
            if t is None:
                return render(request, "portal/link_bad.html", _ctx(request), status=410)
            u = t.user
            u.set_password(new)
            u.failed_logins, u.locked_until = 0, None
            u.save()
            auth.start(request, u, mfa_ok=not u.mfa_enabled)
            return redirect("/client-portal/login/code/" if u.mfa_enabled else "/client-portal/")
    return render(request, "portal/set_password.html", _ctx(request, who=peek.user, kind=peek.kind, error=error))


# ── home ──
@portal_login_required()
def home(request):
    pu = request.portal_user
    ctx = _ctx(request, recent=my_tickets(pu).order_by("-updated_at")[:5], welcome=Setting.get("portal.welcome", ""))
    if pu.can("billing") and enabled("show_billing"):
        unpaid = Invoice.objects.filter(client=pu.client, status__in=UNPAID, archived_at__isnull=True)
        agg = unpaid.aggregate(t=Sum("total"), p=Sum("amount_paid"))
        ctx.update(unpaid=unpaid.order_by("due_date")[:5], balance=(agg["t"] or 0) - (agg["p"] or 0),
                   quotes_waiting=Quote.objects.filter(client=pu.client, status="Sent", archived_at__isnull=True)[:5])
    if pu.can("contracts") and enabled("show_contracts"):
        ctx["active_contracts"] = Contract.objects.filter(client=pu.client, status="Active", archived_at__isnull=True).count()
        ctx["to_sign"] = Contract.objects.filter(client=pu.client, status="Sent", archived_at__isnull=True)[:5]
    if pu.can("assets") and enabled("show_assets"):
        ctx["asset_count"] = Asset.objects.filter(client=pu.client, archived_at__isnull=True).count()
    if pu.can("policies") and enabled("show_policies"):
        ctx["policies_due"] = [p for p in _policies(pu) if not p.my_ack][:5]
    return render(request, "portal/home.html", ctx)


# ── tickets ──
@portal_login_required()
def tickets(request):
    pu = request.portal_user
    flt = request.GET.get("f", "all")
    qs = my_tickets(pu)
    if flt == "open":
        qs = qs.filter(status__in=OPEN_STATUSES)
    elif flt == "closed":
        qs = qs.exclude(status__in=OPEN_STATUSES)
    error = ""
    if request.method == "POST":
        if not pu.can("submit_tickets"):
            raise PermissionDenied
        subject, details = request.POST.get("subject", "").strip()[:255], request.POST.get("details", "").strip()[:20000]
        priority = request.POST.get("priority") if request.POST.get("priority") in dict(PRIORITY_CHOICES) else "Low"
        queue = Queue.objects.filter(pk=request.POST.get("queue") or 0, active=True).exclude(portal_label="").first()
        notify = [c.email for c in Contact.objects.filter(client=pu.client, pk__in=request.POST.getlist("notify")[:20]) if c.email and c.email != pu.email]
        if not subject:
            error = "Add a short subject."
        elif not _rate_ok(f"pticket:{pu.pk}", 20, 3600):
            error = "That's a lot of tickets in an hour. Please call us if it's urgent."
        else:
            t = services.create_ticket(subject=subject, details=details, client=pu.client, contact=pu.contact, priority=priority,
                                       source="Portal", queue=queue, cc=", ".join(notify), portal_user=pu)
            files = request.FILES.getlist("files")
            if files:
                _save_files(request, files, t)
            _notify_staff(f"New portal ticket {t.number}: {t.subject}", f"From {pu.name} ({pu.client.name})\n\n{details}", f"/tickets/{t.pk}/")
            return redirect(f"/client-portal/tickets/{t.pk}/?new=1")
    ctx = _ctx(request, rows=qs.order_by("-updated_at")[:200], f=flt, error=error, priorities=PRIORITY_CHOICES,
               queues=Queue.objects.filter(active=True).exclude(portal_label=""),
               coworkers=Contact.objects.filter(client=pu.client, archived_at__isnull=True).exclude(email="").exclude(email__iexact=pu.email))
    return render(request, "portal/tickets.html", ctx, status=400 if error else 200)


def _save_files(request, files, ticket, message=None):
    from apps.files.services import check
    for f in files[:10]:
        if check(f):
            continue
        u = Upload(kind="ticket", ticket=ticket, message=message, original_name=f.name[:255], content_type=f.content_type[:100] or "",
                   size=f.size, uploaded_by_name=request.portal_user.name)
        u.file.save(f.name, f, save=True)


@portal_login_required()
def ticket(request, pk):
    pu = request.portal_user
    t = get_object_or_404(Ticket.objects.select_related("assigned_to", "queue"), pk=pk, client=pu.client)
    if t.merged_into_id:
        return redirect(f"/client-portal/tickets/{t.merged_into_id}/")
    if not my_tickets(pu).filter(pk=t.pk).exists():
        raise Http404
    reopen_hours = int(Setting.get("portal.reopen_hours", "48") or 48)
    can_reply = t.status in OPEN_STATUSES or (t.closed_at or t.resolved_at or timezone.now()) > timezone.now() - timedelta(hours=reopen_hours)
    if request.method == "POST":
        body = request.POST.get("body", "").strip()[:20000]
        files = request.FILES.getlist("files")
        if (body or files) and can_reply and _rate_ok(f"preply:{pu.pk}", 60, 3600):
            m = services.client_reply(t, portal_user=pu, body=body or "Attached files")
            if files:
                _save_files(request, files, t, m)
            _notify_staff(f"Client replied on {t.number}: {t.subject}", f"{pu.name}: {body}", f"/tickets/{t.pk}/")
        return redirect(f"/client-portal/tickets/{t.pk}/")
    msgs = list(t.messages.filter(kind="reply").select_related("author"))
    files = list(t.uploads.filter(Q(message__isnull=True) | Q(message__kind="reply")))
    by_msg = {}
    for u in files:
        by_msg.setdefault(u.message_id, []).append(u)
    for m in msgs:
        m.files = by_msg.get(m.pk, [])
    kb = KbArticle.objects.filter(visibility="Portal", archived_at__isnull=True)
    words = [w for w in t.subject.lower().split() if len(w) > 3][:4]
    related = kb.filter(Q(*[Q(title__icontains=w) for w in words], _connector=Q.OR))[:3] if words and pu.can("kb") else []
    return render(request, "portal/ticket.html", _ctx(request, t=t, msgs=msgs, loose=by_msg.get(None, []), can_reply=can_reply,
                                                      related=related, new=request.GET.get("new")))


@portal_login_required()
def file_download(request, pk):
    pu = request.portal_user
    u = get_object_or_404(Upload, pk=pk, kind="ticket", ticket__client=pu.client)
    if not my_tickets(pu).filter(pk=u.ticket_id).exists() or (u.message_id and u.message.kind != "reply"):
        raise Http404
    try:
        fh = u.file.open("rb")
    except OSError as e:
        raise Http404 from e
    inline = request.GET.get("view") == "1" and u.ext in INLINE_EXT
    r = FileResponse(fh, as_attachment=not inline, filename=u.original_name, content_type=u.content_type if inline else "application/octet-stream")
    r["X-Content-Type-Options"] = "nosniff"
    r["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
    return r


# ── billing ──
@portal_login_required("billing", "billing")
def invoices(request):
    pu = request.portal_user
    qs = Invoice.objects.filter(client=pu.client, archived_at__isnull=True).exclude(status__in=["Draft", "Void"])
    f = request.GET.get("f", "all")
    if f == "unpaid":
        qs = qs.filter(status__in=UNPAID)
    elif f == "paid":
        qs = qs.filter(status="Paid")
    pu.client.refresh_from_db()
    return render(request, "portal/invoices.html", _ctx(request, rows=qs.annotate(open_balance=F("total") - F("amount_paid")), f=f, client=pu.client,
                                                        autopay_available=Setting.get("autopay.enabled", "true") != "false"))


@portal_login_required("billing", "billing")
def invoice(request, pk):
    from apps.billing import payments, stripe_api
    pu = request.portal_user
    inv = get_object_or_404(Invoice, pk=pk, client=pu.client, archived_at__isnull=True)
    if inv.status in ("Draft", "Void"):
        raise Http404
    if inv.status == "Sent":
        Invoice.objects.filter(pk=inv.pk).update(status="Viewed")
    msg, error = "", ""
    if request.GET.get("session"):
        try:
            msg = payments.finish_checkout(request.GET["session"][:200], expect_client=pu.client)
        except stripe_api.StripeError as e:
            error = f"We couldn't confirm the payment yet ({e}). If you were charged, it will show here shortly."
        inv.refresh_from_db()
    elif request.GET.get("cancelled"):
        error = "Payment cancelled — nothing was charged."
    if request.method == "POST":
        if not stripe_api.configured():
            error = "Online payment isn't available right now. Please call us."
        elif not _rate_ok(f"ppay:{pu.pk}", 20, 3600):
            error = "Too many tries — please wait a bit."
        else:
            base = f"{settings.PORTAL_BASE}/invoices/{inv.pk}/"
            try:
                return redirect(payments.checkout_pay(inv, base, base + "?cancelled=1", save_for_autopay=request.POST.get("autopay") == "1"))
            except stripe_api.StripeError as e:
                error = str(e)
    pays = inv.payments.filter(archived_at__isnull=True).exclude(status="Failed").order_by("-paid_on", "-id")
    client = pu.client
    client.refresh_from_db()
    return render(request, "portal/invoice.html", _ctx(request, inv=inv, lines=inv.lines.all(), balance=inv.balance, pays=pays, msg=msg, error=error,
                                                      can_pay=stripe_api.configured(), client=client))


@portal_login_required("billing", "billing")
def autopay(request):
    """Billing › AutoPay: put a card or bank account on file, change it, or turn AutoPay off."""
    from apps.billing import payments, stripe_api
    pu = request.portal_user
    client = pu.client
    msg, error = "", ""
    if request.GET.get("session"):
        try:
            msg = payments.finish_checkout(request.GET["session"][:200], expect_client=client)
        except stripe_api.StripeError as e:
            error = str(e)
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "off" and client.autopay_method_id:
            payments.turn_off(client, by=f"{pu.name} (portal)")
            _notify_staff(f"AutoPay turned off by {pu.name}", f"{client.name} turned off AutoPay in the portal.", f"/clients/{client.pk}/?tab=Invoices")
            msg = "AutoPay is off and your card was removed."
        elif action == "setup":
            if not stripe_api.configured():
                error = "AutoPay setup isn't available right now. Please call us."
            else:
                base = f"{settings.PORTAL_BASE}/autopay/"
                try:
                    return redirect(payments.checkout_setup(client, base, base))
                except stripe_api.StripeError as e:
                    error = str(e)
    client.refresh_from_db()
    open_invoices = Invoice.objects.filter(client=client, status__in=UNPAID, archived_at__isnull=True).order_by("due_date")
    return render(request, "portal/autopay.html", _ctx(request, client=client, msg=msg, error=error, open_invoices=open_invoices,
                                                       timing=Setting.get("autopay.timing", "immediate"), can_pay=stripe_api.configured()))


def autopay_link(request, token):
    """Setup link emailed by staff — works without a portal account, once, for 7 days."""
    from apps.billing import payments, stripe_api
    link = payments.find_link(token)
    if request.GET.get("session"):
        t = payments.find_link(token)
        if t:
            try:
                done = payments.finish_checkout(request.GET["session"][:200], expect_client=t.client)
            except stripe_api.StripeError:
                done = ""
            if done:
                type(t).objects.filter(pk=t.pk).update(used_at=timezone.now())
                return render(request, "portal/autopay_link.html", _ctx(request, done=True, c=t.client))
    if link is None:
        return render(request, "portal/link_bad.html", _ctx(request), status=410)
    if request.method == "POST":
        if not _rate_ok(f"aplink:{client_ip(request)}", 20, 3600):
            raise PermissionDenied
        base = f"{settings.PORTAL_BASE}/autopay/link/{token}/"
        try:
            return redirect(payments.checkout_setup(link.client, base, base))
        except stripe_api.StripeError as e:
            return render(request, "portal/autopay_link.html", _ctx(request, c=link.client, error=str(e), link=link))
    return render(request, "portal/autopay_link.html", _ctx(request, c=link.client, link=link))


@portal_login_required("billing", "billing")
def quotes(request):
    pu = request.portal_user
    rows = Quote.objects.filter(client=pu.client, archived_at__isnull=True).exclude(status="Draft")
    return render(request, "portal/quotes.html", _ctx(request, rows=rows))


@portal_login_required("billing", "billing")
def quote(request, pk):
    pu = request.portal_user
    q = get_object_or_404(Quote, pk=pk, client=pu.client, archived_at__isnull=True)
    if q.status == "Draft":
        raise Http404
    error = ""
    if request.method == "POST" and q.status == "Sent":
        decision, name = request.POST.get("decision"), request.POST.get("name", "").strip()[:200]
        if decision == "accepted" and not (name and request.POST.get("agree")):
            error = "Type your name and tick the box to accept."
        elif decision in ("accepted", "declined"):
            with transaction.atomic():
                QuoteApproval.objects.create(quote=q, portal_user=pu, decision=decision, signed_name=name or pu.name, total=q.total,
                                             comment=request.POST.get("comment", "")[:2000], ip=client_ip(request))
                Quote.objects.filter(pk=q.pk).update(status="Accepted" if decision == "accepted" else "Declined", updated_at=timezone.now())
            audit(None, f"quote_{decision}", "quotes", q.pk, f"{pu.name} {decision} {q} in the portal", area="billing")
            _notify_staff(f"Quote {q} {decision} by {pu.name}", request.POST.get("comment", ""), f"/m/quotes/{q.pk}/")
            return redirect(f"/client-portal/quotes/{q.pk}/")
    return render(request, "portal/quote.html", _ctx(request, q=q, lines=q.lines.all(), error=error, approval=q.approvals.order_by("-created_at").first()))


# ── contracts & policies ──
def _contract_hash(c: Contract) -> str:
    text = "\n".join(str(x) for x in (c.number, c.name, c.type, c.start_date, c.end_date, c.monthly_rate, c.included_hours, c.overage_rate, c.scope, c.terms))
    return hashlib.sha256(text.encode()).hexdigest()


@portal_login_required("contracts", "contracts")
def contracts(request):
    pu = request.portal_user
    rows = Contract.objects.filter(client=pu.client, archived_at__isnull=True).exclude(status__in=["Draft", "Cancelled"])
    return render(request, "portal/contracts.html", _ctx(request, rows=rows))


@portal_login_required("contracts", "contracts")
def contract(request, pk):
    pu = request.portal_user
    c = get_object_or_404(Contract, pk=pk, client=pu.client, archived_at__isnull=True)
    if c.status in ("Draft", "Cancelled"):
        raise Http404
    error = ""
    if request.method == "POST" and c.status == "Sent":
        name, title = request.POST.get("name", "").strip()[:200], request.POST.get("title", "").strip()[:200]
        if not (name and request.POST.get("agree")):
            error = "Type your full name and tick the box to sign."
        else:
            with transaction.atomic():
                ContractSignature.objects.create(contract=c, portal_user=pu, signed_name=name, signed_title=title, content_hash=_contract_hash(c), ip=client_ip(request))
                Contract.objects.filter(pk=c.pk).update(status="Active", start_date=c.start_date or timezone.localdate(), updated_at=timezone.now())
            audit(None, "contract_signed", "contracts", c.pk, f"{name} signed {c} in the portal", area="billing")
            _notify_staff(f"Contract signed: {c}", f"Signed by {name}{', ' + title if title else ''} ({pu.client.name})", f"/m/contracts/{c.pk}/")
            return redirect(f"/client-portal/contracts/{c.pk}/")
    return render(request, "portal/contract.html", _ctx(request, c=c, error=error, signature=c.signatures.order_by("-created_at").first()))


def _policies(pu):
    rows = list(Policy.objects.filter(Q(client=pu.client) | Q(client__isnull=True), status="Current", archived_at__isnull=True).order_by("name"))
    acks = {(a.policy_id, a.version): a for a in PolicyAck.objects.filter(portal_user=pu)}
    for p in rows:
        p.my_ack = acks.get((p.pk, p.version))
    return rows


@portal_login_required("policies", "policies")
def policies(request):
    return render(request, "portal/policies.html", _ctx(request, rows=_policies(request.portal_user)))


@portal_login_required("policies", "policies")
def policy(request, pk):
    pu = request.portal_user
    p = next((x for x in _policies(pu) if x.pk == pk), None)
    if p is None:
        raise Http404
    if request.method == "POST" and not p.my_ack and request.POST.get("agree"):
        PolicyAck.objects.create(policy=p, portal_user=pu, version=p.version, signed_name=pu.name, ip=client_ip(request))
        audit(None, "policy_ack", "policies", p.pk, f"{pu.name} acknowledged {p.name} v{p.version}", area="billing")
        return redirect(f"/client-portal/policies/{p.pk}/")
    return render(request, "portal/policy.html", _ctx(request, p=p))


# ── assets & help ──
@portal_login_required("assets", "assets")
def assets(request):
    rows = Asset.objects.filter(client=request.portal_user.client, archived_at__isnull=True).order_by("type", "name")
    groups = {}
    for a in rows:
        groups.setdefault(a.type, []).append(a)
    return render(request, "portal/assets.html", _ctx(request, groups=sorted(groups.items()), today=timezone.localdate()))


@portal_login_required("kb", "kb")
def help_home(request):
    qs = KbArticle.objects.filter(visibility="Portal", archived_at__isnull=True)
    q = request.GET.get("q", "").strip()[:100]
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(body__icontains=q))
    cats = {}
    for a in qs.order_by("category", "title")[:300]:
        cats.setdefault(a.category or "General", []).append(a)
    return render(request, "portal/help.html", _ctx(request, cats=sorted(cats.items()), q=q,
                                                    popular=KbArticle.objects.filter(visibility="Portal", archived_at__isnull=True).order_by("-views")[:5]))


@portal_login_required("kb", "kb")
def help_article(request, pk):
    a = get_object_or_404(KbArticle, pk=pk, visibility="Portal", archived_at__isnull=True)
    KbArticle.objects.filter(pk=a.pk).update(views=F("views") + 1)
    return render(request, "portal/article.html", _ctx(request, a=a))


# ── secure messages ──
def _threads(pu):
    return SecureMessage.objects.filter(client=pu.client, thread__isnull=True, archived_at__isnull=True).filter(Q(portal_user=pu) | Q(portal_user__isnull=True))


@portal_login_required("messages", "messages")
def messages_list(request):
    pu = request.portal_user
    error = ""
    if request.method == "POST":
        subject, body = request.POST.get("subject", "").strip()[:255], request.POST.get("body", "").strip()[:20000]
        if not (subject and body):
            error = "Add a subject and a message."
        elif _rate_ok(f"pmsg:{pu.pk}", 30, 3600):
            m = SecureMessage(client=pu.client, contact=pu.contact, subject=subject, direction="Inbound", status="Unread", portal_user=pu)
            set_secret(m, "body", body)
            m.save()
            _notify_staff(f"New secure message from {pu.name}", subject, f"/messages/{m.pk}/")
            return redirect(f"/client-portal/messages/{m.pk}/")
    rows = []
    for t in _threads(pu).order_by("-created_at")[:100]:
        last = t.replies.order_by("-created_at").first() or t
        t.last_at = last.created_at
        t.unread = (t.direction == "Outbound" and not t.client_read_at) or t.replies.filter(direction="Outbound", client_read_at__isnull=True).exists()
        rows.append(t)
    rows.sort(key=lambda x: x.last_at, reverse=True)
    return render(request, "portal/messages.html", _ctx(request, rows=rows, error=error))


@portal_login_required("messages", "messages")
def message_thread(request, pk):
    pu = request.portal_user
    root = get_object_or_404(_threads(pu), pk=pk)
    if request.method == "POST":
        body = request.POST.get("body", "").strip()[:20000]
        if body and _rate_ok(f"pmsg:{pu.pk}", 30, 3600):
            m = SecureMessage(client=pu.client, contact=pu.contact, subject=root.subject, direction="Inbound", status="Unread", portal_user=pu, thread=root)
            set_secret(m, "body", body)
            m.save()
            SecureMessage.objects.filter(pk=root.pk).update(status="Unread", updated_at=timezone.now())
            _notify_staff(f"Reply to secure message from {pu.name}", root.subject, f"/messages/{root.pk}/")
        return redirect(f"/client-portal/messages/{root.pk}/")
    items = [root, *root.replies.order_by("created_at")]
    for m in items:
        try:
            m.text = get_secret(m, "body")
        except Exception:  # noqa: BLE001
            m.text = "(This message can't be shown.)"
    SecureMessage.objects.filter(Q(pk=root.pk) | Q(thread=root), direction="Outbound", client_read_at__isnull=True).update(client_read_at=timezone.now())
    return render(request, "portal/message.html", _ctx(request, root=root, items=items))


# ── profile ──
def _qr(uri):
    img = qrcode.make(uri, image_factory=qrcode.image.svg.SvgPathFillImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return "data:image/svg+xml;base64," + base64.b64encode(buf.getvalue()).decode()


@portal_login_required()
def profile(request):
    pu = request.portal_user
    msg, error, qr, secret = "", "", None, None
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "password":
            cur, new, again = request.POST.get("current", ""), request.POST.get("new", ""), request.POST.get("again", "")
            if pu.has_password and not pu.check_password(cur):
                error = "Your current password isn't right."
            elif new != again:
                error = "The two new passwords don't match."
            else:
                try:
                    validate_password(new)
                    pu.set_password(new)
                    pu.save(update_fields=["password", "updated_at"])
                    auth.start(request, pu, mfa_ok=True)  # keeps this browser signed in; signs out the others
                    msg = "Password changed. You were signed out everywhere else."
                except ValidationError as e:
                    error = " ".join(e.messages)
        elif action == "mfa_start":
            secret = pyotp.random_base32(32)
            PortalUser.objects.filter(pk=pu.pk).update(totp_pending_enc=encrypt(secret))
            qr = _qr(pyotp.TOTP(secret).provisioning_uri(name=pu.email, issuer_name=Setting.get("company.name") or "Weststar"))
        elif action == "mfa_confirm":
            pu.refresh_from_db()
            if auth.verify_totp(pu, request.POST.get("code", ""), field="totp_pending_enc"):
                PortalUser.objects.filter(pk=pu.pk).update(totp_secret_enc=F("totp_pending_enc"), totp_pending_enc="", mfa_enabled=True)
                msg = "Two-step sign-in is on."
            else:
                secret = decrypt(pu.totp_pending_enc) if pu.totp_pending_enc else None
                qr = _qr(pyotp.TOTP(secret).provisioning_uri(name=pu.email, issuer_name=Setting.get("company.name") or "Weststar")) if secret else None
                error = "That code isn't right. Check the time on your phone and use the newest code."
        elif action == "mfa_off":
            if pu.has_password and not pu.check_password(request.POST.get("password", "")):
                error = "Your password isn't right."
            else:
                PortalUser.objects.filter(pk=pu.pk).update(mfa_enabled=False, totp_secret_enc="", totp_pending_enc="")
                msg = "Two-step sign-in is off."
        elif action == "invite" and pu.role == "admin":
            name, email = request.POST.get("name", "").strip()[:200], request.POST.get("email", "").strip().lower()[:254]
            if not name or "@" not in email:
                error = "Enter their name and email."
            elif PortalUser.objects.filter(email__iexact=email).exists():
                error = "That email already has a portal account."
            elif not _rate_ok(f"pinvite:{pu.pk}", 20, 86400):
                error = "Too many invitations today."
            else:
                group = PortalGroup.objects.filter(name="Help Desk / End User").first()
                new = PortalUser.objects.create(client=pu.client, name=name, email=email, group=group,
                                                contact=Contact.objects.filter(client=pu.client, email__iexact=email).first())
                sent = auth.send_link(new, "invite", invited_by=pu.name)
                audit(None, "portal_invite", "portal_user", new.pk, f"{pu.name} invited {email} to the portal", area="clients")
                msg = f"Invitation sent to {email}." if sent else f"Added {email}, but the email couldn't be sent. Ask us to resend it."
        elif action == "deactivate" and pu.role == "admin":
            other = PortalUser.objects.filter(pk=request.POST.get("user") or 0, client=pu.client).exclude(pk=pu.pk).first()
            if other:
                PortalUser.objects.filter(pk=other.pk).update(is_active=False)
                audit(None, "portal_deactivate", "portal_user", other.pk, f"{pu.name} turned off portal access for {other.email}", area="clients")
                msg = f"{other.name} can no longer sign in."
        pu.refresh_from_db()
    team = PortalUser.objects.filter(client=pu.client).order_by("-is_active", "name")
    return render(request, "portal/profile.html", _ctx(request, msg=msg, error=error, qr=qr, secret=secret, team=team))


_ = pysecrets


@portal_login_required("billing", "billing")
def document_pdf(request, kind, pk):
    from apps.billing.documents import filename, pdf
    pu = request.portal_user
    model = Invoice if kind == "invoice" else Quote if kind == "quote" else None
    if model is None:
        raise Http404
    doc = get_object_or_404(model, pk=pk, client=pu.client, archived_at__isnull=True)
    if doc.status == "Draft":
        raise Http404
    from django.http import HttpResponse
    r = HttpResponse(pdf(doc, kind), content_type="application/pdf")
    r["Content-Disposition"] = f'attachment; filename="{filename(doc, kind)}"'
    return r
