"""
The module registry: one entry per menu page that is a plain list of records.

Each Django app registers its modules in its modules.py. The generic list/edit screens, the menu and
the search all read from here, so adding a module is: write the model, register it, make a migration.
"""
from dataclasses import dataclass, field


@dataclass
class Module:
    slug: str                      # URL: /m/<slug>/
    model: type
    label: str                     # "Invoices"
    singular: str                  # "Invoice"
    area: str                      # permission area (see core.permissions)
    description: str
    list_fields: list[str]         # columns on the list page
    search_fields: list[str] = field(default_factory=list)
    status_field: str | None = None  # drives the status tabs
    form_exclude: list[str] = field(default_factory=list)
    number: tuple[str, str, int] | None = None   # (field, prefix, first number)
    lines: tuple[type, str] | None = None        # (line model, foreign key to parent)
    owner_scoped: bool = False     # non-managers only see/edit their own rows (field "user")
    owner_initial_status: str | None = None      # owner can only edit while the status is this
    primary_action: str = ""
    ordering: list[str] = field(default_factory=lambda: ["-id"])
    hidden: bool = False           # no menu page of its own (shown inside another page)

    @property
    def verbose(self):
        return self.model._meta


REGISTRY: dict[str, Module] = {}


def register(module: Module) -> Module:
    REGISTRY[module.slug] = module
    module.model.ws_module = module
    return module


def get(slug: str) -> Module | None:
    return REGISTRY.get(slug)


# ── Menu: same items and order as the old Weststar One sidebar ──
NAV = [
    (None, None, None, [("dashboard", "Dashboard", "/", "tickets"), ("tickets", "Tickets", "/tickets/", "tickets"), ("projects", "Projects", "/m/projects/", "projects")]),
    ("CRM & Marketing", "CRM", "clients", [("clients", "Clients", "/clients/", "clients")]),
    ("Sales & Marketing", "Sales", "leads", [("leads", "Leads", "/m/leads/", "sales"), ("marketing", "Marketing", "/m/campaigns/", "sales")]),
    ("Billing", "Billing", "invoices", [
        ("invoices", "Invoices", "/m/invoices/", "billing"), ("payments", "Payments", "/m/payments/", "billing"), ("recurring", "Recurring", "/m/recurring/", "billing"),
        ("banking", "Banking", "/m/banking/", "billing"), ("quotes", "Quotes", "/m/quotes/", "billing"),
        ("contracts", "Contracts", "/m/contracts/", "billing"), ("policies", "Policies", "/m/policies/", "billing"),
        ("training", "Security Training", "/m/training/", "billing"), ("renewals", "Renewals", "/m/renewals/", "billing"),
        ("expenses", "Expenses", "/m/expenses/", "billing"), ("vendors", "Vendors", "/m/vendors/", "billing"),
    ]),
    ("Tools", "Tools", "tools", [
        ("calendar", "Calendar", "/m/calendar/", "tools"), ("inventory", "Inventory", "/m/inventory/", "tools"),
        ("mileage", "Mileage", "/m/mileage/", "tools"), ("messages", "Secure Messages", "/m/messages/", "tools"),
        ("domains", "Domains & SSL", "/m/domains/", "tools"), ("backups", "Backups", "/m/backups/", "tools"),
        ("rmm", "RMM", "/m/rmm/", "tools"), ("kb", "Knowledge Base", "/m/kb/", "tools"), ("workflows", "Workflows", "/m/workflows/", "admin"),
    ]),
    ("H/R", "H/R", "my_hr", [("my_hr", "My HR", "/my-hr/", "*"), ("hr", "H/R Admin", "/hr/", "hr")]),
    ("Admin", "Admin", "settings", [("settings", "Settings", "/settings/", "*")]),
]
