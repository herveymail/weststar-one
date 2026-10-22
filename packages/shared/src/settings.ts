/**
 * Settings catalog — same groups and pages as the old Weststar One "Settings" home.
 * `fields` lists the keys stored in the settings table for pages that are simple forms;
 * `page` points at a dedicated screen instead (users, security, audit log …).
 */
export interface SettingField { key: string; label: string; type: 'text' | 'textarea' | 'int' | 'bool' | 'secret' | 'select'; options?: string[]; help?: string }
export interface SettingPage { id: string; title: string; desc: string; fields?: SettingField[]; page?: string }
export interface SettingGroup { id: string; title: string; desc: string; items: SettingPage[] }

export const SETTINGS: SettingGroup[] = [
  { id: 'general', title: 'General', desc: 'Your company, numbers, hours and how the app looks', items: [
    { id: 'company', title: 'Company profile', desc: 'Name, address, phone, email and logo', fields: [
      { key: 'company.name', label: 'Company name', type: 'text' }, { key: 'company.phone', label: 'Phone', type: 'text' },
      { key: 'company.email', label: 'Email', type: 'text' }, { key: 'company.address', label: 'Address', type: 'textarea' },
      { key: 'company.website', label: 'Website', type: 'text' }] },
    { id: 'numbers', title: 'Numbers & rates', desc: 'Ticket / invoice / quote prefixes, tax, hourly & mileage rates', fields: [
      { key: 'numbers.ticket_prefix', label: 'Ticket prefix', type: 'text', help: 'Default T-' },
      { key: 'billing.default_tax_rate', label: 'Default tax rate %', type: 'text' },
      { key: 'billing.hourly_rate', label: 'Default hourly rate', type: 'text' },
      { key: 'billing.mileage_rate', label: 'Mileage rate per mile', type: 'text' },
      { key: 'billing.net_terms', label: 'Default net terms (days)', type: 'int' }] },
    { id: 'hours', title: 'Hours & switches', desc: 'Timezone, business hours, portal, email, SLA, auto-assign', fields: [
      { key: 'app.timezone', label: 'Timezone', type: 'select', options: ['America/Denver', 'America/Phoenix', 'America/Chicago', 'America/New_York', 'America/Los_Angeles'] },
      { key: 'app.business_hours', label: 'Business hours', type: 'text', help: 'Example: Mon–Fri 8:00–17:00' },
      { key: 'tickets.auto_assign', label: 'Auto-assign new tickets', type: 'bool' }] },
    { id: 'appearance', title: 'Appearance', desc: 'Default look for new users (each person can change theirs in Profile)', fields: [
      { key: 'app.default_look', label: 'Default look', type: 'select', options: ['indigo', 'graphite'] }] },
    { id: 'branding', title: 'Branding', desc: 'App name, dashboard welcome, footer', fields: [
      { key: 'brand.app_name', label: 'App name', type: 'text' }, { key: 'brand.welcome', label: 'Dashboard welcome', type: 'text' }] },
    { id: 'company_extras', title: 'Company extras', desc: 'Social links, Google review link, portal branding', fields: [
      { key: 'company.review_link', label: 'Google review link', type: 'text' }, { key: 'company.social', label: 'Social links', type: 'textarea' }] },
  ] },
  { id: 'helpdesk', title: 'Helpdesk', desc: 'How tickets come in, get routed and answered', items: [
    { id: 'tickets', title: 'Ticket settings', desc: 'Priorities, SLA targets, categories, automation', fields: [
      { key: 'tickets.categories', label: 'Categories (one per line)', type: 'textarea' },
      { key: 'tickets.sla_critical_min', label: 'Critical response (minutes)', type: 'int' },
      { key: 'tickets.sla_high_min', label: 'High response (minutes)', type: 'int' },
      { key: 'tickets.sla_medium_min', label: 'Medium response (minutes)', type: 'int' },
      { key: 'tickets.sla_low_min', label: 'Low response (minutes)', type: 'int' },
      { key: 'tickets.auto_close_days', label: 'Auto-close resolved tickets after (days)', type: 'int' }] },
    { id: 'queues', title: 'Helpdesk queues', desc: 'Level 1, Level 2, Billing, Dev, Bug Reports: routing and alerts', fields: [
      { key: 'tickets.queues', label: 'Queues (one per line)', type: 'textarea' }] },
    { id: 'saved_replies', title: 'Saved replies', desc: 'Reply templates', fields: [{ key: 'tickets.saved_replies', label: 'Saved replies (separate with a line of ---)', type: 'textarea' }] },
    { id: 'alert_senders', title: 'Alert senders', desc: 'Turn Datto, RMM and backup alert emails into tickets', fields: [
      { key: 'tickets.alert_senders', label: 'Sender addresses (one per line)', type: 'textarea' }] },
    { id: 'portal', title: 'Customer portal', desc: 'What clients can see and do in the portal', fields: [
      { key: 'portal.enabled', label: 'Portal enabled', type: 'bool' }, { key: 'portal.show_invoices', label: 'Clients can see invoices', type: 'bool' }] },
  ] },
  { id: 'comms', title: 'Email & messaging', desc: 'Email, chat and phone connections', items: [
    { id: 'email', title: 'Email', desc: 'Microsoft 365 / Google sending and email-to-ticket', fields: [
      { key: 'email.provider', label: 'Provider', type: 'select', options: ['Microsoft 365', 'Google Workspace', 'SMTP'] },
      { key: 'email.support_address', label: 'Support mailbox', type: 'text' },
      { key: 'email.m365_tenant_id', label: 'Microsoft tenant ID', type: 'text' },
      { key: 'email.m365_client_id', label: 'Microsoft client ID', type: 'text' },
      { key: 'email.m365_client_secret', label: 'Microsoft client secret', type: 'secret' },
      { key: 'email.smtp_host', label: 'SMTP host', type: 'text' }, { key: 'email.smtp_password', label: 'SMTP password', type: 'secret' }] },
    { id: 'google_chat', title: 'Google Chat', desc: 'Ticket alerts in Google Chat', fields: [{ key: 'chat.webhook_url', label: 'Webhook URL', type: 'secret' }] },
    { id: 'phone', title: 'Phone system', desc: 'Yeastar PBX, call sync and recordings', fields: [
      { key: 'phone.yeastar_host', label: 'Yeastar address', type: 'text' }, { key: 'phone.yeastar_secret', label: 'API secret', type: 'secret' }] },
  ] },
  { id: 'billing', title: 'Billing & documents', desc: 'Invoices, quotes, contracts and getting paid', items: [
    { id: 'invoice_defaults', title: 'Invoice & quote defaults', desc: 'Terms, notes, disclaimers', fields: [
      { key: 'billing.invoice_footer', label: 'Invoice footer', type: 'textarea' }, { key: 'billing.quote_terms', label: 'Quote terms', type: 'textarea' }] },
    { id: 'payments', title: 'Payments', desc: 'Stripe card / ACH payments and AutoPay', fields: [
      { key: 'stripe.publishable_key', label: 'Stripe publishable key', type: 'text' },
      { key: 'stripe.secret_key', label: 'Stripe secret key', type: 'secret' }, { key: 'stripe.webhook_secret', label: 'Stripe webhook secret', type: 'secret' }] },
  ] },
  { id: 'people', title: 'People & access', desc: 'Who can sign in and what they can do', items: [
    { id: 'users', title: 'Staff users', desc: 'Accounts, roles, HR access, password and 2FA resets', page: 'users' },
    { id: 'signin', title: 'Sign-in & MFA', desc: 'Require two-factor, session timeout', fields: [
      { key: 'security.require_mfa', label: 'Require two-factor sign-in for', type: 'select', options: ['admins', 'everyone', 'nobody'] },
      { key: 'security.idle_minutes', label: 'Sign out after idle (minutes)', type: 'int' }] },
  ] },
  { id: 'integrations', title: 'Integrations & automation', desc: 'Other apps, AI and scheduled jobs', items: [
    { id: 'rmm', title: 'Datto RMM', desc: 'Device and alert sync', fields: [
      { key: 'rmm.api_url', label: 'API URL', type: 'text' }, { key: 'rmm.api_key', label: 'API key', type: 'text' }, { key: 'rmm.api_secret', label: 'API secret', type: 'secret' }] },
    { id: 'msp360', title: 'MSP360 backups', desc: 'Backup job sync', fields: [
      { key: 'msp360.login', label: 'API login', type: 'text' }, { key: 'msp360.password', label: 'API password', type: 'secret' }] },
    { id: 'ai', title: 'AI assistant', desc: 'Ticket summaries and reply drafts', fields: [
      { key: 'ai.provider', label: 'Provider', type: 'select', options: ['none', 'anthropic', 'openai', 'gemini', 'ollama'] },
      { key: 'ai.model', label: 'Model', type: 'text' }, { key: 'ai.api_key', label: 'API key', type: 'secret' }] },
    { id: 'jobs', title: 'Scheduled jobs', desc: 'Background jobs and when they last ran', page: 'jobs' },
  ] },
  { id: 'system', title: 'Security & system', desc: 'Keep the app safe, backed up and up to date', items: [
    { id: 'my_security', title: 'My sign-in & 2FA', desc: 'Your password, two-factor and active sessions', page: 'my-security' },
    { id: 'audit', title: 'Audit log', desc: 'Who changed what', page: 'audit' },
    { id: 'security_log', title: 'Security log', desc: 'Sign-in attempts and lockouts', page: 'security-log' },
    { id: 'import', title: 'Import from old Weststar One', desc: 'How to bring tickets and data across', page: 'import' },
  ] },
];

/** Keys that hold secrets — stored encrypted, never sent back to the browser. */
export const SECRET_SETTING_KEYS = new Set(
  SETTINGS.flatMap((g) => g.items.flatMap((i) => (i.fields ?? []).filter((f) => f.type === 'secret').map((f) => f.key))),
);
export const ALL_SETTING_FIELDS = SETTINGS.flatMap((g) => g.items.flatMap((i) => i.fields ?? []));
