"""Old Weststar One settings → new settings. Each old key maps to (new key, how to convert).
Only copied when the new app doesn't have its own value yet; every old setting is also kept in
LegacySetting so nothing is lost (Settings › Old system settings)."""
import re

SECRET_KEY_RX = re.compile(r"pass|secret|token|api_key|_key_enc|webhook_url|license_key", re.I)
SKIP_RX = re.compile(r"^(cron_lastrun_|schema_ok_|oidc_jwks_|update_|git_status|whatsnew_|backup_.*last|db_error_digest|payments_reconcile|"
                     r"autopay_last|msp360_sync_last|msp360_token|yeastar_(last|token|access|refresh)|zoho_.*(token|expires)|datto_(access|token)|"
                     r".*_seeded$|tickets_created_utc|ticket_billing_cleanup|tc_migrated|tc_webhook_registered|sla_alerts_since|install_date|app_installed)")


def b(v):
    return "true" if str(v).strip().lower() in ("1", "true", "yes", "on") else "false"


def x60(v):
    try:
        return str(int(float(v) * 60))
    except ValueError:
        return None


def num(v):
    try:
        float(v)
        return str(v).strip()
    except ValueError:
        return None


def lines(v):
    return "\n".join(x.strip() for x in re.split(r"[,\n]", v) if x.strip())


def subject(v):
    return v.replace("{prefix}{number}", "{number}").replace("{prefix}", "")


def cap(v):
    return v.strip().capitalize() if v.strip().lower() in ("low", "medium", "high", "critical") else None


def same(v):
    return v


MAP = {
    # company & look
    "company_name": ("company.name", same), "company_phone": ("company.phone", same), "company_email": ("company.email", same),
    "company_tagline": ("company.tagline", same), "company_billing_email": ("company.billing_email", same),
    "company_noc_email": ("company.noc_email", same), "company_dispatch_email": ("company.dispatch_email", same),
    "company_operating_hours": ("company.hours", same), "company_service_area": ("company.service_area", same),
    "company_after_hours_phone": ("company.after_hours_phone", same), "company_license_number": ("company.license_number", same),
    "company_email_signature": ("email.signature", same), "google_review_link": ("company.review_link", same),
    "company_portal_theme_color": ("brand.color", lambda v: v if v.startswith("#") and len(v) == 7 else None),
    "navbar_app_name": ("brand.app_name", same), "dashboard_welcome": ("brand.welcome", same), "timezone": ("app.timezone", same),
    "date_format": ("app.date_format", same), "max_upload_mb": ("files.max_upload_mb", num),
    # billing & documents
    "default_tax_rate": ("billing.default_tax_rate", num), "default_hourly_rate": ("billing.hourly_rate", num),
    "default_mileage_rate": ("billing.mileage_rate", num), "default_net_terms": ("billing.net_terms", num), "tax_label": ("billing.tax_label", same),
    "currency_symbol": ("billing.currency_symbol", same), "invoice_footer_text": ("billing.invoice_footer", same), "invoice_terms": ("billing.invoice_terms", same),
    "invoice_payment_instructions": ("billing.payment_instructions", same), "invoice_paid_message": ("billing.paid_message", same),
    "invoice_email_subject": ("billing.invoice_email_subject", same), "invoice_reminder_subject": ("billing.invoice_reminder_subject", same),
    "invoice_reminder_days": ("billing.reminder_days", num), "invoice_grace_days": ("billing.late_fee_grace_days", num),
    "invoice_late_fee_enabled": ("billing.late_fee_enabled", b), "invoice_late_fee_type": ("billing.late_fee_type", same),
    "invoice_late_fee_flat": ("billing.late_fee_flat", num), "invoice_late_fee_pct": ("billing.late_fee_pct", num),
    "invoice_late_notice": ("billing.late_notice", same), "invoice_late_fee_recurring": ("billing.late_fee_repeat", b), "default_invoice_note": ("billing.invoice_note", same),
    "quote_terms": ("billing.quote_terms", same), "quote_disclaimer": ("billing.quote_disclaimer", same), "quote_footer_text": ("billing.quote_footer", same),
    "quote_acceptance_text": ("billing.quote_acceptance_text", same), "quote_valid_days": ("billing.quote_valid_days", num),
    "quote_deposit_pct": ("billing.quote_deposit_pct", num), "quote_email_subject": ("billing.quote_email_subject", same),
    "contract_default_terms": ("billing.contract_terms", same), "contract_default_duration": ("billing.contract_months", num),
    "contract_notice_days": ("billing.contract_notice_days", num), "contract_governing_state": ("billing.contract_state", same),
    "contract_court_county": ("billing.contract_county", same), "contract_early_term_pct": ("billing.contract_early_term_pct", num),
    "contract_auto_renew": ("billing.contract_auto_renew", b), "contract_indemnification": ("billing.contract_indemnification", same),
    "contract_insurance_text": ("billing.contract_insurance", same), "contract_nonsolicitation": ("billing.contract_nonsolicitation", same),
    "contract_email_subject": ("billing.contract_email_subject", same), "policy_review_months": ("billing.policy_review_months", num),
    "quote_number_padding": ("numbers.quote_padding", num), "invoice_number_padding": ("numbers.invoice_padding", num),
    # helpdesk
    "ticket_categories": ("tickets.categories", lines), "work_types": ("tickets.work_types", lines), "default_ticket_priority": ("tickets.email_priority", cap),
    "ticket_auto_close_days": ("tickets.auto_close_days", num), "ticket_reopen_window_hours": ("portal.reopen_hours", num),
    "ticket_auto_add_contacts": ("tickets.auto_add_contacts", b), "tq_email_new": ("tickets.email_ack", b),
    "ticket_status_email_enabled": ("tickets.email_on_close", b), "ticket_closed_footer": ("tickets.closed_footer", same),
    "ticket_email_new_subject": ("tickets.email_new_subject", subject), "ticket_email_reply_subject": ("tickets.email_reply_subject", subject),
    "ticket_email_closed_subject": ("tickets.email_closed_subject", subject), "ticket_afterhours_auto_reply": ("tickets.afterhours_enabled", b),
    "ticket_afterhours_message": ("tickets.afterhours_message", same), "helpdesk_open": ("helpdesk.open", same), "helpdesk_close": ("helpdesk.close", same),
    "ticket_afterhours_rate": ("billing.afterhours_rate", num), "ticket_afterhours_minimum": ("billing.afterhours_minimum", num),
    "ticket_default_rate": ("billing.hourly_rate", num), "auto_ticket_assignment": ("tickets.auto_assign", b),
    "sla_response_critical": ("tickets.sla_critical_min", x60), "sla_response_high": ("tickets.sla_high_min", x60),
    "sla_response_medium": ("tickets.sla_medium_min", x60), "sla_response_low": ("tickets.sla_low_min", x60),
    "sla_resolution_critical": ("tickets.resolve_critical_hours", num), "sla_resolution_high": ("tickets.resolve_high_hours", num),
    "sla_resolution_medium": ("tickets.resolve_medium_hours", num), "sla_resolution_low": ("tickets.resolve_low_hours", num),
    # email (sending and the support mailbox; email-to-ticket itself stays off until it's turned on here)
    "smtp2go_api_key": ("email.smtp2go_api_key", same), "smtp2go_from_email": ("email.from_address", same), "smtp2go_from_name": ("email.from_name", same),
    "mail_provider": ("email.provider", lambda v: "SMTP2GO (HTTPS)" if "smtp2go" in v.lower() else "Gmail / SMTP"),
    "smtp_host": ("email.smtp_host", same), "smtp_port": ("email.smtp_port", num), "smtp_user": ("email.smtp_user", same),
    "smtp_pass": ("email.smtp_password", same), "smtp_from_email": ("email.from_address", same), "smtp_from_name": ("email.from_name", same),
    "imap_host": ("email.imap_host", same), "imap_port": ("email.imap_port", num), "imap_user": ("email.imap_user", same),
    "imap_pass": ("email.imap_password", same), "imap_folder": ("email.imap_folder", same),
    "imap_last_uid": ("email.imap_last_uid", num), "imap_uidvalidity": ("email.imap_uidvalidity", same),
    # chat, portal, sign-in, integrations
    "gchat_webhook_url": ("chat.webhook_url", same), "gchat_notify_client_replies": ("chat.notify_client_replies", b),
    "portal_enabled": ("portal.enabled", b), "portal_show_invoices": ("portal.show_billing", b), "portal_show_contracts": ("portal.show_contracts", b),
    "portal_show_kb": ("portal.show_kb", b), "portal_asset_view": ("portal.show_assets", b),
    "sso_google_client_id": ("google.client_id", same), "sso_google_client_secret": ("google.client_secret", same),
    "security_session_timeout": ("security.idle_minutes", num),
    "sso_google_enabled": ("google.domains", None), "sso_require_for_linked": ("users.google_only", None),
    "ai_provider": ("ai.provider", lambda v: v.strip().lower() if v.strip().lower() in ("gemini", "anthropic", "openai", "ollama") else None),
    "ai_base_url": ("ai.base_url", same),
    "tai_triage": ("ai.triage", b), "tai_suggest": ("ai.suggest", b), "tai_firstresponse": ("ai.first_response", b),
    "tai_firstresponse_hours": ("ai.first_response_when", lambda v: "after_hours" if "after" in v.lower() else "always"),
    "tai_firstresponse_skip": ("ai.first_response_skip", same), "ai_model": ("ai.model", same), "ai_api_key": ("ai.api_key", same),
    "msp360_login": ("msp360.login", same), "msp360_password": ("msp360.password", same),
    "signoff_breakfix_required": ("tickets.signoff_breakfix_required", b),
    "msp360_enabled": ("msp360.enabled", b), "msp360_base_url": ("msp360.base_url", same), "msp360_ticket_on_failure": ("msp360.ticket_on_failure", b),
    "msp360_overdue_hours": ("msp360.overdue_hours", num), "msp360_auto_resolve": ("msp360.auto_resolve", b),
    "msp360_ticket_priority": ("msp360.ticket_priority", lambda v: str(v).strip().title() if str(v).strip().lower() in ("low", "medium", "high", "critical") else None),
    "datto_api_url": ("rmm.api_url", same), "datto_api_key": ("rmm.api_key", same), "datto_api_secret": ("rmm.api_secret", same),
    "yeastar_url": ("phone.yeastar_host", same), "yeastar_client_id": ("phone.yeastar_client_id", same), "yeastar_client_secret": ("phone.yeastar_secret", same),
    "autopay_enabled": ("autopay.enabled", b), "autopay_timing": ("autopay.timing", lambda v: "due_date" if "due" in v else "immediate"),
    "autopay_retry_days": ("autopay.retry_days", num), "autopay_max_attempts": ("autopay.max_attempts", num),
    "backup_s3_endpoint": ("backup.s3_endpoint", same), "backup_s3_bucket": ("backup.s3_bucket", same), "backup_s3_region": ("backup.s3_region", same),
    "backup_s3_prefix": ("backup.s3_prefix", same), "backup_s3_key": ("backup.s3_key", same), "backup_s3_secret": ("backup.s3_secret", same),
}

DAY_KEYS = [f"helpdesk_day_{i}" for i in range(1, 8)]
DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
