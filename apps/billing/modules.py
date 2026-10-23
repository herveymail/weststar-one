from apps.core.registry import Module, register

from .models import (BankTransaction, Contract, Expense, Invoice, InvoiceLine, Policy, Quote, QuoteLine, RecurringInvoice,
                     RecurringLine, Renewal, TrainingAssignment, Vendor)

register(Module("invoices", Invoice, "Invoices", "Invoice", "billing", "Bill clients and track what is owed.",
                ["number", "client", "status", "invoice_date", "due_date", "total"], ["number", "scope"], "status",
                number=("number", "INV-", 1001), lines=(InvoiceLine, "invoice"), primary_action="New invoice", ordering=["-invoice_date", "-id"]))
register(Module("recurring", RecurringInvoice, "Recurring", "Recurring schedule", "billing", "Invoices that go out on a schedule.",
                ["name", "client", "frequency", "next_run", "status", "total"], ["name"], "status", lines=(RecurringLine, "schedule"), primary_action="New schedule"))
register(Module("banking", BankTransaction, "Banking", "Transaction", "billing", "Bank transactions, matched to invoices and expenses.",
                ["posted_on", "description", "account", "amount", "match_status"], ["description", "account"], "match_status", ordering=["-posted_on", "-id"]))
register(Module("quotes", Quote, "Quotes", "Quote", "billing", "Estimates for clients to approve.",
                ["number", "client", "status", "quote_date", "total"], ["number", "scope"], "status",
                number=("number", "QT-", 1001), lines=(QuoteLine, "quote"), primary_action="New quote", ordering=["-quote_date", "-id"]))
register(Module("contracts", Contract, "Contracts", "Contract", "billing", "Service agreements and their renewal dates.",
                ["name", "client", "type", "status", "end_date", "monthly_rate"], ["name", "number"], "status", number=("number", "CT-", 1001), primary_action="New contract"))
register(Module("policies", Policy, "Policies", "Policy", "billing", "IT and security policies clients review and acknowledge.",
                ["name", "client", "version", "status", "next_review"], ["name"], "status", primary_action="New policy"))
register(Module("training", TrainingAssignment, "Security Training", "Training assignment", "billing", "Security courses assigned to client staff, with completion.",
                ["course", "client", "learners", "due_date", "progress", "status"], ["course"], "status", primary_action="Assign course"))
register(Module("renewals", Renewal, "Renewals", "Renewal", "billing", "Licenses, domains, warranties and contracts coming up for renewal.",
                ["item", "client", "type", "renews_on", "cost", "status"], ["item"], "status", primary_action="Add renewal", ordering=["renews_on"]))
register(Module("expenses", Expense, "Expenses", "Expense", "billing", "Costs and billable expenses.",
                ["spent_on", "vendor", "category", "amount", "billable"], ["description", "category"], primary_action="Add expense", ordering=["-spent_on", "-id"]))
register(Module("vendors", Vendor, "Vendors", "Vendor", "billing", "Suppliers, distributors and their account reps.",
                ["name", "category", "contact_name", "phone"], ["name", "contact_name"], primary_action="Add vendor", ordering=["name"]))
