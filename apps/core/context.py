from .models import Setting
from .permissions import can
from .registry import NAV, NAV_BI, NAV_COLORS


def app_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        from apps.core.branding import logo_url
        return {"app_name": Setting.get("brand.app_name", "Weststar ONE"), "logo_url": logo_url(), **_auth_copy()}
    path = request.path
    import re as _re
    of = request.GET.get("open_form", "")
    open_form = of if _re.fullmatch(r"/(m/[a-z_]+/(new|\d+)|tickets/new)/(\?[A-Za-z0-9_=&%.+-]*)?", of) else ""
    nav = []
    for group, short, icon, items in NAV:
        visible = []
        for item_id, label, url, area in items:
            if area == "*" or can(user, area):
                active = path == "/" if url == "/" else path.startswith(url)
                visible.append({"id": item_id, "label": label, "url": url, "active": active, "bi": NAV_BI.get(item_id, "bi-circle")})
        if visible:
            nav.append({"group": group, "short": short, "icon": icon, "items": visible, "active": any(i["active"] for i in visible),
                        "color": NAV_COLORS.get(group, "slate")})
    from apps.core.branding import logo_url
    return {
        "settings_nav": _settings_nav(user, path) if path.startswith("/settings/") else None,
        **(_auth_copy() if path.startswith(("/login", "/account")) else {}),
        "logo_url": logo_url(),
        "app_name": Setting.get("brand.app_name", "Weststar ONE"),
        "nav": nav,
        "open_form": open_form,
        "look": user.look,
        "ui_style": user.ui_style,
        "ui_font": __import__("apps.core.ui_styles", fromlist=["font_query"]).font_query(user.ui_style),
        "look_mode": __import__("apps.core.themes", fromlist=["mode"]).mode(user.look),
        "can_tickets_edit": can(user, "tickets", "edit"),
        "open_ticket_count": _open_count(user),
        "clocked_in": _clocked_in(user),
        "app_version": __import__("django.conf", fromlist=["settings"]).settings.APP_VERSION,
        "company_name": Setting.get("company.name", ""),
    }


def _open_count(user):
    if not can(user, "tickets"):
        return 0
    from apps.helpdesk.models import OPEN_STATUSES, Ticket
    return Ticket.objects.filter(status__in=OPEN_STATUSES).count()


def _clocked_in(user):
    from apps.hr.models import TimeclockEntry
    return TimeclockEntry.objects.filter(user=user, status="Open", clock_out__isnull=True, archived_at__isnull=True).exists()


def _settings_nav(user, path):
    """Left menu on every Settings page: groups → pages, with the words each page holds (for the filter box)."""
    from .settings_catalog import SETTINGS, TILE_LOOK, field_specs
    admin = can(user, "admin")
    current = path.split("/")[2] if path.count("/") >= 3 else ""
    out = []
    for gid, title, _desc, items in SETTINGS:
        pages = []
        for item in items:
            if item[0] != "my_security" and not admin:
                continue
            words = " ".join(f["label"] for f in field_specs(item) if f["type"] != "section") if isinstance(item[3], list) else ""
            icon, color = TILE_LOOK.get(item[0], ("bi-gear", "#64748b"))
            pages.append({"id": item[0], "title": item[1], "desc": item[2], "words": f"{item[1]} {item[2]} {words}".lower(), "icon": icon, "color": color,
                          "active": item[0] == current or (current == "users" and item[0] == "users")})
        if pages:
            out.append({"id": gid, "title": title, "pages": pages, "open": any(pg["active"] for pg in pages)})
    return out


def _auth_copy():
    from .branding import login_brand
    return {**login_brand(), "login_heading": Setting.get("brand.login_heading", "") or "Everything your team needs, in one place.",
            "login_text": Setting.get("brand.login_text", "") or f"Tickets, clients, billing and contracts for {Setting.get('company.name', '') or 'your team'}."}
