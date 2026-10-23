from apps.core.registry import Module, register

from .models import Asset, Client, ClientNote, Contact, Network, Project

register(Module("clients", Client, "Clients", "Client", "clients", "Every client with their contacts, assets, network and billing.",
                ["name", "status", "plan", "phone", "city"], ["name", "email", "phone", "city"], "status", primary_action="New client", ordering=["name"]))
register(Module("contacts", Contact, "Contacts", "Contact", "clients", "People at each client.", ["name", "client", "title", "email", "phone"],
                ["name", "email", "phone"], hidden=True, ordering=["name"]))
register(Module("assets", Asset, "Assets", "Asset", "clients", "Computers, servers, network gear and printers at each client.",
                ["name", "client", "type", "status", "serial", "warranty_expires"], ["name", "serial", "ip", "model"], "status", hidden=True))
register(Module("networks", Network, "Networks", "Network", "clients", "Client networks. Wi-Fi passwords and ISP accounts are encrypted.",
                ["name", "client", "subnet", "isp"], ["name", "isp"], hidden=True))
register(Module("client_notes", ClientNote, "Notes", "Note", "clients", "Notes on a client.", ["title", "client", "created_at"], ["title", "body"], hidden=True))
register(Module("projects", Project, "Projects", "Project", "projects", "Bigger jobs with tasks, files and time.",
                ["number", "name", "client", "owner", "status", "due_date"], ["name", "number"], "status", number=("number", "PRJ-", 1001), primary_action="New project"))
