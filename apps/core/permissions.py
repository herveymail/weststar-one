"""
Who can do what. Each person has a ROLE, plus a separate H/R switch (like the old app's user_hr_access).

Levels per area, lowest to highest: none < view < edit < manage
  view   — can open and read
  edit   — can add and change
  manage — can also archive/restore and approve (time off, timeclock)
"""
# Same roles as the old app (help desk, sales/CRM and accounting included).
ROLES = [("admin", "Admin"), ("manager", "Manager"), ("help_desk", "Help desk"), ("tech", "Tech"), ("sales", "Sales / CRM"),
         ("accounting", "Accounting"), ("viewer", "Viewer")]
AREAS = ["tickets", "clients", "projects", "sales", "billing", "tools", "hr", "admin"]
LEVELS = ["none", "view", "edit", "manage"]

ROLE_LEVELS = {
    "admin":   dict(tickets="manage", clients="manage", projects="manage", sales="manage", billing="manage", tools="manage", hr="manage", admin="manage"),
    "manager": dict(tickets="manage", clients="manage", projects="manage", sales="manage", billing="manage", tools="manage", hr="none", admin="view"),
    "tech":    dict(tickets="edit", clients="edit", projects="edit", sales="view", billing="none", tools="edit", hr="none", admin="none"),
    "help_desk": dict(tickets="edit", clients="view", projects="edit", sales="none", billing="none", tools="view", hr="none", admin="none"),
    "sales":   dict(tickets="edit", clients="edit", projects="view", sales="manage", billing="view", tools="view", hr="none", admin="none"),
    "accounting": dict(tickets="view", clients="edit", projects="view", sales="view", billing="manage", tools="view", hr="none", admin="none"),
    "viewer":  dict(tickets="view", clients="view", projects="view", sales="none", billing="none", tools="view", hr="none", admin="none"),
}


def level_for(user, area: str) -> str:
    if not user or not user.is_authenticated:
        return "none"
    if area == "hr" and user.hr_access:
        return "manage"
    return ROLE_LEVELS.get(user.role, {}).get(area, "none")


def can(user, area: str, need: str = "view") -> bool:
    return LEVELS.index(level_for(user, area)) >= LEVELS.index(need)
