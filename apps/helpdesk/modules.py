from apps.core.registry import Module, register

from .models import RecurringTicket, TicketTemplate

register(Module("ticket_templates", TicketTemplate, "Ticket templates", "Template", "tickets",
                "Ready-made tickets with a checklist, priority and time estimate. Pick one in New ticket, or open them on a schedule.",
                ["name", "subject", "priority", "estimate_minutes"], ["name", "subject"], primary_action="New template", ordering=["name"], hidden=True))
register(Module("recurring_tickets", RecurringTicket, "Recurring tickets", "Schedule", "tickets",
                "Tickets that open by themselves on a schedule — monthly maintenance, quarterly reviews, backup tests.",
                ["name", "template", "client", "frequency", "next_run", "assigned_to", "status"], ["name"], "status",
                primary_action="New schedule", ordering=["next_run"], hidden=True))
