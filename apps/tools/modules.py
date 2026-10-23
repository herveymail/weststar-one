from apps.core.registry import Module, register

from .models import BackupJob, CalendarEvent, Domain, InventoryItem, KbArticle, MileageTrip, RmmDevice, SecureMessage, Workflow

register(Module("calendar", CalendarEvent, "Calendar", "Event", "tools", "Schedule and on-site visits.", ["title", "starts_at", "who", "client"], ["title"], primary_action="New event", ordering=["starts_at"]))
register(Module("inventory", InventoryItem, "Inventory", "Item", "tools", "Parts and hardware in stock.", ["name", "sku", "on_hand", "cost", "price"], ["name", "sku"], primary_action="Add item", ordering=["name"]))
register(Module("mileage", MileageTrip, "Mileage", "Trip", "tools", "Trips to client sites. You only see your own unless you manage Tools.",
                ["trip_date", "trip", "miles", "client", "billable", "user"], ["trip"], owner_scoped=True, primary_action="Log trip", ordering=["-trip_date", "-id"]))
register(Module("messages", SecureMessage, "Secure Messages", "Message", "tools", "Messages with clients through the portal. Message text is encrypted.",
                ["subject", "client", "direction", "status"], ["subject"], "status", primary_action="New message"))
register(Module("domains", Domain, "Domains & SSL", "Domain", "tools", "Domain expirations and SSL certificates.", ["name", "client", "registrar", "expires_on", "ssl_status"], ["name", "registrar"], primary_action="Add domain", ordering=["expires_on"]))
register(Module("backups", BackupJob, "Backups", "Backup job", "tools", "Backup jobs across every client (synced from MSP360).", ["device", "client", "plan", "last_run_at", "last_result"], ["device", "plan"], "last_result"))
register(Module("rmm", RmmDevice, "RMM", "Device", "tools", "Devices from Datto RMM.", ["name", "client", "os", "last_seen_at", "status"], ["name", "os"], "status"))
register(Module("kb", KbArticle, "Knowledge Base", "Article", "tools", "How-to articles for your team and for clients in the portal.", ["title", "category", "visibility", "views"], ["title", "body", "category"], "visibility", primary_action="New article"))
register(Module("workflows", Workflow, "Workflows", "Workflow", "admin", "Automations: when something happens, do something.", ["name", "trigger", "action", "status", "runs"], ["name"], "status", primary_action="New workflow"))
