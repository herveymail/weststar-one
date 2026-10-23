"""Settings pages — same groups as the old Weststar One Settings home.
Each item: (id, title, description, fields or a page name). Field: (key, label, type, options/help)."""

T, TA, I, B, S, SEL = "text", "textarea", "int", "bool", "secret", "select"

SETTINGS = [
    ("general", "General", "Your company, numbers, hours and how the app looks", [
        ("company", "Company profile", "Name, address, phone, emails, hours", [("company.name", "Company name", T), ("company.tagline", "Tagline", T), ("company.phone", "Phone", T), ("company.after_hours_phone", "After-hours phone", T), ("company.email", "Email", T),
            ("company.billing_email", "Billing email", T), ("company.noc_email", "NOC email", T), ("company.dispatch_email", "Dispatch email", T), ("company.address", "Address", TA), ("company.website", "Website", T),
            ("company.hours", "Operating hours (shown to clients)", T), ("company.service_area", "Service area", T), ("company.license_number", "License number", T), ("app.timezone", "Time zone", T, "e.g. America/Denver"), ("email.signature", "Email signature", TA)]),
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
        ("tickets", "Ticket settings", "Categories, work types, default priority, auto-close", [("tickets.categories", "Categories (one per line)", TA), ("tickets.work_types", "Work types (one per line)", TA), ("tickets.email_priority", "Priority for tickets that come in by email", SEL, ["Low", "Medium", "High", "Critical"]), ("tickets.auto_close_days", "Auto-close resolved tickets after (days)", I), ("tickets.auto_add_contacts", "Add unknown senders from a client's domain as contacts", B)]),
        ("sla", "SLA targets", "Response and resolve times by priority", [("tickets.sla_critical_min", "Critical: respond within (minutes)", I), ("tickets.sla_high_min", "High: respond within (minutes)", I), ("tickets.sla_medium_min", "Medium: respond within (minutes)", I), ("tickets.sla_low_min", "Low: respond within (minutes)", I),
            ("tickets.resolve_critical_hours", "Critical: resolve within (hours)", I), ("tickets.resolve_high_hours", "High: resolve within (hours)", I), ("tickets.resolve_medium_hours", "Medium: resolve within (hours)", I), ("tickets.resolve_low_hours", "Low: resolve within (hours)", I)]),
        ("email_in", "Email to ticket", "Turn email to support@ into tickets (Google Workspace mailbox)", [("email.fetch_enabled", "Check the mailbox for new email every minute", B), ("email.imap_user", "Mailbox (e.g. support@weststarmsp.com)", T), ("email.imap_password", "App password for that mailbox", S, "Google Account › Security › 2-Step Verification › App passwords"), ("email.imap_host", "IMAP server", T), ("email.imap_port", "IMAP port", I), ("email.imap_folder", "Folder", T), ("tickets.alert_senders", "Alert senders: always make tickets, even automatic mail (one address or domain per line)", TA)]),
        ("ticket_emails", "Ticket emails", "What clients get by email and the subject lines", [("tickets.email_ack", "Email the client when a ticket is created (\"we got your request\")", B), ("tickets.email_on_close", "Email the client when a ticket is resolved or closed", B),
            ("tickets.email_new_subject", "Subject: new ticket", T, "{number} and {subject} are filled in. Keep {number} so replies find the ticket."), ("tickets.email_reply_subject", "Subject: our replies", T), ("tickets.email_closed_subject", "Subject: resolved", T), ("tickets.closed_footer", "Message added to the resolved email", TA)]),
        ("afterhours", "Office hours & after hours", "Help desk hours and the after-hours note in replies", [("helpdesk.open", "Opens (24-hour, e.g. 07:00)", T), ("helpdesk.close", "Closes (e.g. 16:30)", T), ("helpdesk.days", "Open days (e.g. Mon,Tue,Wed,Thu,Fri)", T), ("tickets.afterhours_enabled", "Add the after-hours note to the \"we got your request\" email", B), ("tickets.afterhours_message", "After-hours note", TA)]),
        ("queues", "Helpdesk queues", "Level 1, Level 2, Billing, Dev, Bug Reports", "queues"),
        ("saved_replies", "Saved replies", "Reply templates", [("tickets.saved_replies", "Saved replies (separate with a line of ---)", TA)]),
        ("portal", "Customer portal", "What clients can see and do in the portal", [("portal.enabled", "Portal is on", B), ("portal.welcome", "Welcome message on the portal home page", TA), ("portal.magic_links", "Allow \"Email me a sign-in link\"", B), ("portal.reopen_hours", "Clients can reopen a closed ticket for (hours)", I),
            ("portal.show_billing", "Show invoices & quotes", B), ("portal.show_contracts", "Show contracts", B), ("portal.show_policies", "Show policies", B), ("portal.show_assets", "Show assets", B), ("portal.show_kb", "Show help articles", B), ("portal.show_messages", "Show secure messages", B)]),
    ]),
    ("comms", "Email & messaging", "Email, chat and phone connections", [
        ("email", "Email sending (SMTP)", "How the app sends email — Google Workspace / Gmail SMTP", [("email.smtp_host", "SMTP server", T), ("email.smtp_port", "SMTP port", I), ("email.smtp_user", "SMTP username (the mailbox, e.g. support@weststarmsp.com)", T), ("email.smtp_password", "SMTP password (Google: an app password)", S), ("email.from_address", "Send from address", T), ("email.from_name", "Send from name (e.g. Weststar Helpdesk)", T), ("email.support_address", "Support mailbox — replies go here and staff alerts are sent here", T)]),
        ("google_chat", "Google Chat", "Ticket alerts in Google Chat", [("chat.webhook_url", "Webhook URL", S), ("chat.notify_new_ticket", "Alert on new tickets from email", B), ("chat.notify_client_replies", "Alert when a client replies", B)]),
        ("phone", "Phone system", "Yeastar PBX, call sync and recordings", [("phone.yeastar_host", "Yeastar address", T), ("phone.yeastar_client_id", "Client ID", T), ("phone.yeastar_secret", "Client secret", S)]),
    ]),
    ("billing", "Billing & documents", "Invoices, quotes, contracts and getting paid", [
        ("invoice_defaults", "Invoice defaults", "Terms, notes, payment instructions, email subjects", [("billing.invoice_terms", "Invoice terms", TA), ("billing.invoice_footer", "Invoice footer", TA), ("billing.invoice_note", "Default invoice note", TA),
            ("billing.payment_instructions", "Payment instructions", TA), ("billing.paid_message", "Paid message", T), ("billing.tax_label", "Tax label", T), ("billing.currency_symbol", "Currency symbol", T),
            ("billing.invoice_email_subject", "Invoice email subject", T), ("billing.invoice_reminder_subject", "Reminder email subject", T), ("billing.reminder_days", "Send reminder after (days)", I),
            ("billing.afterhours_rate", "After-hours hourly rate", T), ("billing.afterhours_minimum", "After-hours minimum charge", T)]),
        ("late_fees", "Late fees", "Late fee amount, grace period and notice", [("billing.late_fee_enabled", "Charge late fees", B), ("billing.late_fee_type", "Late fee type", SEL, ["flat", "percent"]), ("billing.late_fee_flat", "Flat fee", T), ("billing.late_fee_pct", "Percent per month", T),
            ("billing.late_fee_grace_days", "Grace period (days)", I), ("billing.late_notice", "Late notice text", TA)]),
        ("quote_defaults", "Quote defaults", "Terms, disclaimer, acceptance text", [("billing.quote_terms", "Quote terms", TA), ("billing.quote_disclaimer", "Disclaimer", TA), ("billing.quote_acceptance_text", "Acceptance text", TA), ("billing.quote_footer", "Quote footer", T),
            ("billing.quote_valid_days", "Quotes are good for (days)", I), ("billing.quote_deposit_pct", "Deposit %", I), ("billing.quote_email_subject", "Quote email subject", T)]),
        ("contract_defaults", "Contract defaults", "Standard terms and legal clauses", [("billing.contract_terms", "Default terms", TA), ("billing.contract_months", "Default length (months)", I), ("billing.contract_auto_renew", "Renew automatically", B),
            ("billing.contract_notice_days", "Cancellation notice (days)", I), ("billing.contract_early_term_pct", "Early termination fee %", I), ("billing.contract_state", "Governing state", T), ("billing.contract_county", "Court county", T),
            ("billing.contract_indemnification", "Indemnification", TA), ("billing.contract_insurance", "Insurance", TA), ("billing.contract_nonsolicitation", "Non-solicitation", TA), ("billing.contract_email_subject", "Contract email subject", T), ("billing.policy_review_months", "Review policies every (months)", I)]),
        ("payments", "Payments & AutoPay", "Stripe card / ACH payments and AutoPay", [("stripe.publishable_key", "Stripe publishable key", T), ("stripe.secret_key", "Stripe secret key", S), ("stripe.webhook_secret", "Stripe webhook signing secret (whsec_…)", S),
            ("autopay.enabled", "AutoPay is on", B), ("autopay.timing", "Charge AutoPay invoices", SEL, ["immediate", "due_date"], "immediate = as soon as the invoice is sent; due_date = on the due date"),
            ("autopay.retry_days", "If a charge fails, try again after (days)", I), ("autopay.max_attempts", "Stop after this many tries", I)]),
    ]),
    ("people", "People & access", "Who can sign in and what they can do", [
        ("users", "Staff users", "Accounts, roles, H/R access, password and 2FA resets", "users"),
        ("portal_groups", "Portal groups", "What each kind of client portal user can see", "portal_groups"),
        ("signin", "Sign-in & 2FA", "Google Workspace sign-in, two-factor rules, session timeout", [("google.client_id", "Google OAuth client ID", T), ("google.client_secret", "Google OAuth client secret", S), ("google.domains", "Allowed Google Workspace domains (comma-separated, e.g. weststarmsp.com, dsotv.com)", T), ("google.counts_as_2fa", "Google sign-in counts as two-factor (turn on 2-Step Verification enforcement in Google Admin)", SEL, ["yes", "no"]), ("security.password_login", "Password sign-in (once Google is set up)", SEL, ["everyone", "admins"], "admins = only admins can still use a password, as a backup if Google is down"), ("security.require_mfa", "Require two-factor sign-in for", SEL, ["privileged", "everyone", "nobody"], "privileged = admins, managers and anyone with H/R access (recommended)"), ("security.idle_minutes", "Sign out after idle (minutes)", I)]),
    ]),
    ("integrations", "Integrations & automation", "Other apps, AI and scheduled jobs", [
        ("rmm", "Datto RMM", "Device and alert sync", [("rmm.api_url", "API URL", T), ("rmm.api_key", "API key", S), ("rmm.api_secret", "API secret", S)]),
        ("msp360", "MSP360 backups", "Backup job sync", [("msp360.login", "API login", T), ("msp360.password", "API password", S)]),
        ("ai", "AI assistant", "Ticket summaries and reply drafts", [("ai.provider", "Provider", SEL, ["none", "anthropic", "openai", "gemini", "ollama"]), ("ai.model", "Model", T), ("ai.api_key", "API key", S)]),
        ("jobs", "Scheduled jobs", "Background jobs and when they last ran", "jobs"),
        ("offsite", "Offsite backups (Wasabi / S3)", "Where nightly backups are copied", [("backup.s3_endpoint", "Endpoint", T), ("backup.s3_region", "Region", T), ("backup.s3_bucket", "Bucket", T), ("backup.s3_prefix", "Folder", T), ("backup.s3_key", "Access key", S), ("backup.s3_secret", "Secret key", S)]),
    ]),
    ("system", "Security & system", "Keep the app safe, backed up and up to date", [
        ("my_security", "My sign-in & 2FA", "Your password, two-factor and active sessions", "my_security"),
        ("audit", "Audit log", "Who changed what", "audit"),
        ("security_log", "Security log", "Sign-in attempts and lockouts", "security_log"),
        ("import", "Import from old Weststar One", "How to bring tickets and data across", "import"),
        ("old_settings", "Old system settings", "Every setting from the old Weststar One and where it went", "old_settings"),
    ]),
]


# Shown (and used) when a setting has never been saved.
DEFAULTS = {
    "portal.enabled": "true", "portal.magic_links": "true", "portal.reopen_hours": "48", "portal.show_billing": "true", "portal.show_contracts": "true",
    "portal.show_policies": "true", "portal.show_assets": "true", "portal.show_kb": "true", "portal.show_messages": "true",
    "tickets.email_ack": "true", "tickets.email_on_close": "true", "tickets.auto_add_contacts": "true", "tickets.email_priority": "Medium",
    "chat.notify_new_ticket": "true", "chat.notify_client_replies": "true", "email.imap_host": "imap.gmail.com", "email.imap_port": "993",
    "email.imap_folder": "INBOX", "email.smtp_host": "smtp.gmail.com", "email.smtp_port": "587", "email.fetch_enabled": "false",
    "autopay.enabled": "true", "autopay.timing": "immediate", "autopay.retry_days": "3", "autopay.max_attempts": "4",
    "tickets.email_new_subject": "[{number}] {subject}", "tickets.email_reply_subject": "Re: [{number}] {subject}", "tickets.email_closed_subject": "[{number}] Resolved: {subject}",
}


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
