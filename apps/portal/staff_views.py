"""Staff side of the client portal: who can sign in for each client (client page › Portal tab),
portal groups (Settings), and secure-message conversations (Tools › Secure Messages)."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.core import mail
from apps.core.audit import audit
from apps.core.models import get_secret, set_secret
from apps.core.permissions import can
from apps.crm.models import Client, Contact
from apps.tools.models import SecureMessage

from . import auth
from .models import PERMS, PortalGroup, PortalUser

SEED_GROUPS = [
    ("Billing & Admin", "Office managers and owners who handle billing", {"billing", "contracts", "policies", "assets", "submit_tickets", "all_tickets", "messages", "kb"}),
    ("Server / Managed IT", "Client IT staff", {"policies", "assets", "submit_tickets", "all_tickets", "messages", "kb"}),
    ("Help Desk / End User", "Everyday staff: open and follow their own tickets", {"policies", "submit_tickets", "messages", "kb"}),
    ("Executive / Owner", "Sees everything", {p for p, _l in PERMS}),
    ("View Only", "Can look but not open tickets", {"policies", "kb"}),
]


def seed_groups():
    if PortalGroup.objects.exists():
        return
    for name, desc, perms in SEED_GROUPS:
        PortalGroup.objects.create(name=name, description=desc, **{f"can_{p}": p in perms for p, _l in PERMS})


def _perms_from(post) -> dict:
    return {f"can_{p}": post.get(f"can_{p}") == "on" for p, _l in PERMS}


# ── Settings › Portal groups ──
def groups_page(request):
    seed_groups()
    if request.method == "POST":
        if not can(request.user, "admin", "manage"):
            raise PermissionDenied
        g = PortalGroup.objects.filter(pk=request.POST.get("id") or 0).first()
        if request.POST.get("action") == "delete" and g:
            g.delete()
            messages.success(request, "Group deleted. Its people keep their own boxes.")
            return redirect(request.path)
        name = request.POST.get("name", "").strip()[:200]
        if not name:
            messages.error(request, "A group needs a name.")
            return redirect(request.path)
        if PortalGroup.objects.filter(name__iexact=name).exclude(pk=g.pk if g else 0).exists():
            messages.error(request, f"There's already a group called {name}.")
            return redirect(request.path)
        g = g or PortalGroup()
        g.name, g.description = name, request.POST.get("description", "").strip()[:255]
        for k, v in _perms_from(request.POST).items():
            setattr(g, k, v)
        g.save()
        audit(request, "settings", "portal_group", g.pk, f"Saved portal group {g.name}", area="admin")
        messages.success(request, f"Saved {g.name}.")
        return redirect(request.path)
    rows = list(PortalGroup.objects.all())
    for g in rows:
        g.count = g.users.count()
    return render(request, "portal/staff/groups.html", {"rows": rows, "perms": PERMS, "can_manage": can(request.user, "admin", "manage")})


# ── client page › Portal tab ──
@login_required
def client_portal(request, pk):
    if not can(request.user, "clients"):
        raise PermissionDenied
    client = get_object_or_404(Client, pk=pk)
    seed_groups()
    if request.method == "POST":
        if not can(request.user, "clients", "edit"):
            raise PermissionDenied
        _client_portal_post(request, client)
        return redirect(f"/clients/{client.pk}/?tab=Portal")
    users = list(PortalUser.objects.filter(client=client).select_related("group", "contact").order_by("-is_active", "name"))
    have = {u.email.lower() for u in users}
    contacts = [c for c in Contact.objects.filter(client=client, archived_at__isnull=True).exclude(email="").order_by("name") if c.email.lower() not in have]
    return render(request, "portal/staff/_client_tab.html", {"c": client, "users": users, "contacts": contacts, "groups": PortalGroup.objects.all(),
                                                             "perms": PERMS, "can_edit": can(request.user, "clients", "edit"), "mail_ok": mail.configured(), "now": timezone.now(),
                                                             "portal_url": __import__("django.conf", fromlist=["settings"]).settings.PORTAL_BASE + "/"})


def _client_portal_post(request, client):
    action = request.POST.get("action")
    if action == "add":
        contact = Contact.objects.filter(client=client, pk=request.POST.get("contact") or 0).first()
        name = (request.POST.get("name", "").strip() or (contact.name if contact else ""))[:200]
        email = (request.POST.get("email", "").strip() or (contact.email if contact else "")).lower()[:254]
        if not name or "@" not in email:
            messages.error(request, "Pick a contact, or type a name and email.")
            return
        if PortalUser.objects.filter(email__iexact=email).exists():
            messages.error(request, f"{email} already has a portal account.")
            return
        group = PortalGroup.objects.filter(pk=request.POST.get("group") or 0).first()
        u = PortalUser.objects.create(client=client, contact=contact or Contact.objects.filter(client=client, email__iexact=email).first(), name=name, email=email,
                                      group=group, role="admin" if request.POST.get("role") == "admin" else "standard")
        audit(request, "create", "portal_user", u.pk, f"Added portal user {email} for {client.name}", area="clients")
        if request.POST.get("invite") == "on":
            sent = auth.send_link(u, "invite", invited_by=request.user.name)
            messages.success(request, f"Added {name} and emailed an invitation." if sent else f"Added {name}. The invitation couldn't be emailed — check Settings › Email sending.")
        else:
            messages.success(request, f"Added {name}. Send the invitation when you're ready.")
        return
    u = PortalUser.objects.filter(client=client, pk=request.POST.get("user") or 0).first()
    if u is None:
        return
    if action == "save":
        u.name = request.POST.get("name", u.name).strip()[:200] or u.name
        u.role = "admin" if request.POST.get("role") == "admin" else "standard"
        u.group = PortalGroup.objects.filter(pk=request.POST.get("group") or 0).first()
        for k, v in _perms_from(request.POST).items():
            setattr(u, k, v)
        u.save()
        messages.success(request, f"Saved {u.name}.")
    elif action in ("invite", "reset"):
        kind = "invite" if action == "invite" or not u.has_password else "reset"
        sent = auth.send_link(u, kind, invited_by=request.user.name)
        messages.success(request, f"Emailed {u.email} a {'new invitation' if kind == 'invite' else 'password reset link'}.") if sent else \
            messages.error(request, "That email couldn't be sent — check Settings › Email sending.")
    elif action == "toggle":
        u.is_active = not u.is_active
        u.save(update_fields=["is_active", "updated_at"])
        messages.success(request, f"{u.name} {'can sign in again' if u.is_active else 'can no longer sign in'}.")
    elif action == "unlock":
        PortalUser.objects.filter(pk=u.pk).update(failed_logins=0, locked_until=None)
        messages.success(request, f"Unlocked {u.name}.")
    elif action == "mfa_off":
        PortalUser.objects.filter(pk=u.pk).update(mfa_enabled=False, totp_secret_enc="", totp_pending_enc="")
        messages.success(request, f"Turned off two-step sign-in for {u.name}. They can set it up again in their profile.")
    elif action == "delete":
        u.delete()
        messages.success(request, "Portal account removed. Their tickets stay.")
    else:
        return
    audit(request, f"portal_{action}", "portal_user", u.pk, f"Portal user {u.email}: {action}", area="clients")


# ── Tools › Secure Messages ──
@login_required
def messages_list(request):
    from apps.core.views import module_list
    return module_list(request, "messages", extra={"row_url": "/messages/{id}/"}, base_filter={"thread__isnull": True})


@login_required
def message_thread(request, pk):
    if not can(request.user, "tools"):
        raise PermissionDenied
    root = get_object_or_404(SecureMessage.objects.select_related("client", "portal_user"), pk=pk, thread__isnull=True)
    if request.method == "POST":
        if not can(request.user, "tools", "edit"):
            raise PermissionDenied
        body = request.POST.get("body", "").strip()[:20000]
        if body:
            m = SecureMessage(client=root.client, contact=root.contact, subject=root.subject, direction="Outbound", status="Read", thread=root,
                              portal_user=root.portal_user, author=request.user)
            set_secret(m, "body", body)
            m.save()
            SecureMessage.objects.filter(pk=root.pk).update(status="Read", updated_at=timezone.now())
            audit(request, "reply", "secure_message", root.pk, f"Replied to secure message {root.subject}", area="tools")
            _tell_client(root)
            messages.success(request, "Sent. The client gets an email saying there's a new secure message (the message itself stays in the portal).")
        return redirect(f"/messages/{root.pk}/")
    items = [root, *root.replies.select_related("author", "portal_user").order_by("created_at")]
    for m in items:
        try:
            m.text = get_secret(m, "body")
        except Exception:  # noqa: BLE001
            m.text = "(This message can't be shown.)"
    SecureMessage.objects.filter(Q(pk=root.pk) | Q(thread=root), direction="Inbound", status="Unread").update(status="Read")
    return render(request, "portal/staff/message.html", {"root": root, "items": items, "can_reply": can(request.user, "tools", "edit")})


def _tell_client(root):
    from django.conf import settings
    people = [root.portal_user] if root.portal_user_id else list(PortalUser.objects.filter(client=root.client, is_active=True))
    for u in people:
        if u and u.is_active and u.can("messages"):
            mail.send(u.email, "You have a new secure message", "email/portal_secure_notice",
                      {"u": u, "link": f"{settings.PORTAL_BASE}/messages/{root.pk}/"})
