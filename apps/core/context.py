from .models import Setting
from .permissions import can
from .registry import NAV


def app_context(request):
    user = getattr(request, "user", None)
    if not user or not user.is_authenticated:
        return {"app_name": "Weststar ONE"}
    path = request.path
    nav = []
    for group, short, icon, items in NAV:
        visible = []
        for item_id, label, url, area in items:
            if area == "*" or can(user, area):
                active = path == "/" if url == "/" else path.startswith(url)
                visible.append({"id": item_id, "label": label, "url": url, "active": active})
        if visible:
            nav.append({"group": group, "short": short, "icon": icon, "items": visible, "active": any(i["active"] for i in visible)})
    return {
        "app_name": Setting.get("brand.app_name", "Weststar ONE"),
        "nav": nav,
        "look": user.look,
        "can_tickets_edit": can(user, "tickets", "edit"),
        "open_ticket_count": _open_count(user),
        "clocked_in": _clocked_in(user),
    }


def _open_count(user):
    if not can(user, "tickets"):
        return 0
    from apps.helpdesk.models import OPEN_STATUSES, Ticket
    return Ticket.objects.filter(status__in=OPEN_STATUSES).count()


def _clocked_in(user):
    from apps.hr.models import TimeclockEntry
    return TimeclockEntry.objects.filter(user=user, status="Open", clock_out__isnull=True, archived_at__isnull=True).exists()
