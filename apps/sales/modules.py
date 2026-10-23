from apps.core.registry import Module, register

from .models import Campaign, Lead

register(Module("leads", Lead, "Leads", "Lead", "sales", "Prospects from first call to signed contract.",
                ["company", "contact_name", "stage", "value", "next_followup"], ["company", "contact_name", "email"], "stage", primary_action="New lead"))
register(Module("campaigns", Campaign, "Marketing", "Campaign", "sales", "Email campaigns, call lists, review requests and surveys.",
                ["name", "type", "audience", "status", "send_date"], ["name"], "status", primary_action="New campaign"))
