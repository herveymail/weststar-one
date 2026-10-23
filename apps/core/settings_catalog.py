"""Settings pages — same groups as the old Weststar One Settings home.
Each item: (id, title, description, fields or a page name). Field: (key, label, type, options/help)."""

T, TA, I, B, S, SEL = "text", "textarea", "int", "bool", "secret", "select"

SETTINGS = [
    ("general", "General", "Your company, numbers, hours and how the app looks", [
        ("company", "Company profile", "Name, address, phone, email", [("company.name", "Company name", T), ("company.phone", "Phone", T), ("company.email", "Email", T), ("company.address", "Address", TA), ("company.website", "Website", T)]),
        ("numbers", "Numbers & rates", "Ticket prefix, tax, hourly & mileage rates", [("numbers.ticket_prefix", "Ticket prefix (default T-)", T), ("numbers.ticket_padding", "Ticket number digits (0 = no padding)", I),
            ("numbers.invoice_prefix", "Invoice prefix (default INV-)", T), ("numbers.invoice_padding", "Invoice number digits", I),
            ("numbers.quote_prefix", "Quote prefix (default QT-)", T), ("numbers.quote_padding", "Quote number digits", I),
            ("numbers.contract_prefix", "Contract prefix (default CT-)", T), ("numbers.project_prefix", "Project prefix (default PRJ-)", T), ("billing.default_tax_rate", "Default tax rate %", T), ("billing.hourly_rate", "Default hourly rate", T), ("billing.mileage_rate", "Mileage rate per mile", T), ("billing.net_terms", "Default net terms (days)", I)]),
        ("hours", "Hours & switches", "Business hours and helpdesk switches", [("app.business_hours", "Business hours", T), ("tickets.auto_assign", "Auto-assign new tickets", B)]),
        ("appearance", "Appearance", "Default look for new users (each person can change theirs in Profile)", [("app.default_look", "Default look", SEL, ["indigo", "graphite"])]),
        ("branding", "Branding", "App name and dashboard welcome", [("brand.app_name", "App name", T), ("brand.welcome", "Dashboard welcome", T)]),
        ("company_extras", "Company extras", "Social links, Google review link", [("company.review_link", "Google review link", T), ("company.social", "Social links", TA)]),
    ]),
    ("helpdesk", "Helpdesk", "How tickets come in, get routed and answered", [
        ("tickets", "Ticket settings", "SLA targets, categories, automation", [("tickets.categories", "Categories (one per line)", TA), ("tickets.sla_critical_min", "Critical response (minutes)", I), ("tickets.sla_high_min", "High response (minutes)", I), ("tickets.sla_medium_min", "Medium response (minutes)", I), ("tickets.sla_low_min", "Low response (minutes)", I), ("tickets.auto_close_days", "Auto-close resolved tickets after (days)", I)]),
        ("queues", "Helpdesk queues", "Level 1, Level 2, Billing, Dev, Bug Reports", [("tickets.queues", "Queues (one per line)", TA)]),
        ("saved_replies", "Saved replies", "Reply templates", [("tickets.saved_replies", "Saved replies (separate with a line of ---)", TA)]),
        ("alert_senders", "Alert senders", "Turn Datto, RMM and backup alert emails into tickets", [("tickets.alert_senders", "Sender addresses (one per line)", TA)]),
        ("portal", "Customer portal", "What clients can see and do in the portal", [("portal.enabled", "Portal enabled", B), ("portal.show_invoices", "Clients can see invoices", B)]),
    ]),
    ("comms", "Email & messaging", "Email, chat and phone connections", [
        ("email", "Email", "Microsoft 365 / Google sending and email-to-ticket", [("email.provider", "Provider", SEL, ["Microsoft 365", "Google Workspace", "SMTP"]), ("email.support_address", "Support mailbox", T), ("email.m365_tenant_id", "Microsoft tenant ID", T), ("email.m365_client_id", "Microsoft client ID", T), ("email.m365_client_secret", "Microsoft client secret", S), ("email.smtp_host", "SMTP host", T), ("email.smtp_password", "SMTP password", S)]),
        ("google_chat", "Google Chat", "Ticket alerts in Google Chat", [("chat.webhook_url", "Webhook URL", S)]),
        ("phone", "Phone system", "Yeastar PBX, call sync and recordings", [("phone.yeastar_host", "Yeastar address", T), ("phone.yeastar_secret", "API secret", S)]),
    ]),
    ("billing", "Billing & documents", "Invoices, quotes, contracts and getting paid", [
        ("invoice_defaults", "Invoice & quote defaults", "Terms, notes, disclaimers", [("billing.invoice_footer", "Invoice footer", TA), ("billing.quote_terms", "Quote terms", TA)]),
        ("payments", "Payments", "Stripe card / ACH payments and AutoPay", [("stripe.publishable_key", "Stripe publishable key", T), ("stripe.secret_key", "Stripe secret key", S), ("stripe.webhook_secret", "Stripe webhook secret", S)]),
    ]),
    ("people", "People & access", "Who can sign in and what they can do", [
        ("users", "Staff users", "Accounts, roles, H/R access, password and 2FA resets", "users"),
        ("signin", "Sign-in & 2FA", "Who must use two-factor, session timeout", [("security.require_mfa", "Require two-factor sign-in for", SEL, ["privileged", "everyone", "nobody"], "privileged = admins, managers and anyone with H/R access (recommended)"), ("security.idle_minutes", "Sign out after idle (minutes)", I)]),
    ]),
    ("integrations", "Integrations & automation", "Other apps, AI and scheduled jobs", [
        ("rmm", "Datto RMM", "Device and alert sync", [("rmm.api_url", "API URL", T), ("rmm.api_key", "API key", S), ("rmm.api_secret", "API secret", S)]),
        ("msp360", "MSP360 backups", "Backup job sync", [("msp360.login", "API login", T), ("msp360.password", "API password", S)]),
        ("ai", "AI assistant", "Ticket summaries and reply drafts", [("ai.provider", "Provider", SEL, ["none", "anthropic", "openai", "gemini", "ollama"]), ("ai.model", "Model", T), ("ai.api_key", "API key", S)]),
        ("jobs", "Scheduled jobs", "Background jobs and when they last ran", "jobs"),
    ]),
    ("system", "Security & system", "Keep the app safe, backed up and up to date", [
        ("my_security", "My sign-in & 2FA", "Your password, two-factor and active sessions", "my_security"),
        ("audit", "Audit log", "Who changed what", "audit"),
        ("security_log", "Security log", "Sign-in attempts and lockouts", "security_log"),
        ("import", "Import from old Weststar One", "How to bring tickets and data across", "import"),
    ]),
]


def all_pages():
    for gid, gtitle, gdesc, items in SETTINGS:
        for item in items:
            yield gid, gtitle, item


def find(page_id):
    for _gid, gtitle, item in all_pages():
        if item[0] == page_id:
            return gtitle, item
    return None, None


def field_specs(item):
    out = []
    for f in item[3]:
        key, label, typ = f[0], f[1], f[2]
        options = f[3] if len(f) > 3 and isinstance(f[3], list) else None
        help_text = f[4] if len(f) > 4 else (f[3] if len(f) > 3 and isinstance(f[3], str) else "")
        out.append({"key": key, "label": label, "type": typ, "options": options, "help": help_text})
    return out


ALL_FIELDS = {f["key"]: f for _g, _t, item in all_pages() if isinstance(item[3], list) for f in field_specs(item)}
