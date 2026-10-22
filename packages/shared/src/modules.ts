/**
 * The module registry — the single source of truth for every module in Weststar ONE.
 *
 * The API builds its database tables, validation and CRUD routes from this list, and the web app
 * builds its menus, list pages and forms from the same list. Add a field here once and it shows up
 * everywhere (and in the next generated migration).
 */

export type FieldType =
  | 'text' | 'textarea' | 'email' | 'phone' | 'url'
  | 'int' | 'decimal' | 'money'
  | 'date' | 'datetime' | 'bool'
  | 'select' | 'ref'
  | 'secret'; // encrypted at rest, never returned in lists, revealed one at a time (audited)

export interface Field {
  key: string;
  label: string;
  type: FieldType;
  required?: boolean;
  options?: readonly string[];
  /** For type 'ref': the resource id this points at ('clients', 'users', 'vendors', …). */
  ref?: string;
  /** Show as a column on the list page. */
  list?: boolean;
  default?: string | number | boolean;
  help?: string;
  max?: number;
  /** Set by the server; shown but never accepted from the client. */
  readOnly?: boolean;
}

export type PermArea = 'tickets' | 'clients' | 'projects' | 'sales' | 'billing' | 'tools' | 'hr' | 'admin';
export type Level = 'none' | 'view' | 'edit' | 'manage';

export interface Resource {
  id: string;
  table: string;
  label: string;
  singular: string;
  area: PermArea;
  description: string;
  fields: Field[];
  /** Field that drives the status tabs on the list page. */
  statusField?: string;
  search: string[];
  /** Auto-numbered field (e.g. invoice number) and its prefix. */
  number?: { key: string; prefix: string; start: number };
  /** Child line items edited inside the parent form. */
  lineItems?: { resource: string; fk: string };
  /** Non-managers only see and create their own rows (rows where user_id = them). */
  ownerScoped?: boolean;
  /** Not shown as its own page (e.g. line items). */
  hidden?: boolean;
  defaultSort?: { key: string; dir: 'asc' | 'desc' };
  primaryAction?: string;
}

const yesNo = ['Yes', 'No'] as const;

export const RESOURCES: Resource[] = [
  // ── CRM ─────────────────────────────────────────────────────────────
  {
    id: 'clients', table: 'clients', label: 'Clients', singular: 'Client', area: 'clients', primaryAction: 'New client',
    description: 'Every client with their contacts, assets, network and billing.',
    statusField: 'status', search: ['name', 'email', 'phone', 'city'],
    defaultSort: { key: 'name', dir: 'asc' },
    fields: [
      { key: 'name', label: 'Client name', type: 'text', required: true, list: true, max: 200 },
      { key: 'status', label: 'Status', type: 'select', options: ['Active', 'Lead', 'Inactive', 'Former'], default: 'Active', list: true },
      { key: 'type', label: 'Type', type: 'select', options: ['Business', 'Residential', 'Nonprofit', 'Government'], default: 'Business' },
      { key: 'plan', label: 'Plan', type: 'select', options: ['Managed · Gold', 'Managed · Silver', 'Managed · Bronze', 'Break/fix', 'Project'], list: true },
      { key: 'industry', label: 'Industry', type: 'text' },
      { key: 'phone', label: 'Phone', type: 'phone', list: true },
      { key: 'email', label: 'Email', type: 'email' },
      { key: 'website', label: 'Website', type: 'url' },
      { key: 'address', label: 'Address', type: 'text' },
      { key: 'city', label: 'City', type: 'text', list: true },
      { key: 'state', label: 'State', type: 'text' },
      { key: 'zip', label: 'ZIP', type: 'text' },
      { key: 'account_manager_id', label: 'Account manager', type: 'ref', ref: 'users' },
      { key: 'hourly_rate', label: 'Hourly rate', type: 'money' },
      { key: 'tax_rate', label: 'Tax rate %', type: 'decimal' },
      { key: 'net_terms', label: 'Net terms (days)', type: 'int', default: 30 },
      { key: 'sla_response_hours', label: 'SLA response (hours)', type: 'int', default: 4 },
      { key: 'sla_resolution_hours', label: 'SLA resolution (hours)', type: 'int', default: 24 },
      { key: 'account_alert', label: 'Account alert', type: 'text', help: 'Shown in red on every ticket for this client.' },
      { key: 'notes', label: 'Internal notes', type: 'textarea' },
    ],
  },
  {
    id: 'contacts', table: 'contacts', label: 'Contacts', singular: 'Contact', area: 'clients',
    description: 'People at each client.', search: ['name', 'email', 'phone'],
    defaultSort: { key: 'name', dir: 'asc' },
    fields: [
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'name', label: 'Name', type: 'text', required: true, list: true },
      { key: 'title', label: 'Title', type: 'text', list: true },
      { key: 'email', label: 'Email', type: 'email', list: true },
      { key: 'phone', label: 'Phone', type: 'phone', list: true },
      { key: 'mobile', label: 'Mobile', type: 'phone' },
      { key: 'role', label: 'Role', type: 'select', options: ['Decision maker', 'Technical', 'Billing', 'End user', 'Other'], default: 'Other' },
      { key: 'is_primary', label: 'Primary contact', type: 'bool' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'assets', table: 'assets', label: 'Assets', singular: 'Asset', area: 'clients',
    description: 'Computers, servers, network gear and printers at each client.',
    statusField: 'status', search: ['name', 'serial', 'ip', 'model'],
    fields: [
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'name', label: 'Name', type: 'text', required: true, list: true },
      { key: 'type', label: 'Type', type: 'select', options: ['Workstation', 'Laptop', 'Server', 'Network', 'Printer', 'Mobile', 'Other'], list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Active', 'Storage', 'RMA', 'Retired'], default: 'Active', list: true },
      { key: 'make', label: 'Make', type: 'text' },
      { key: 'model', label: 'Model', type: 'text' },
      { key: 'serial', label: 'Serial', type: 'text', list: true },
      { key: 'os', label: 'Operating system', type: 'text' },
      { key: 'ip', label: 'IP address', type: 'text' },
      { key: 'mac', label: 'MAC address', type: 'text' },
      { key: 'purchase_date', label: 'Purchased', type: 'date' },
      { key: 'warranty_expires', label: 'Warranty expires', type: 'date', list: true },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'networks', table: 'client_networks', label: 'Networks', singular: 'Network', area: 'clients',
    description: 'Client network details. Wi-Fi passwords and ISP account numbers are encrypted.', search: ['name', 'isp'],
    fields: [
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'name', label: 'Network name', type: 'text', required: true, list: true },
      { key: 'subnet', label: 'Subnet', type: 'text', list: true },
      { key: 'gateway', label: 'Gateway', type: 'text' },
      { key: 'dns', label: 'DNS servers', type: 'text' },
      { key: 'isp', label: 'ISP', type: 'text', list: true },
      { key: 'isp_account', label: 'ISP account number', type: 'secret' },
      { key: 'wifi_ssid', label: 'Wi-Fi name', type: 'text' },
      { key: 'wifi_password', label: 'Wi-Fi password', type: 'secret' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'client_notes', table: 'client_notes', label: 'Notes', singular: 'Note', area: 'clients',
    description: 'Notes on a client.', search: ['title', 'body'],
    fields: [
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'title', label: 'Title', type: 'text', required: true, list: true },
      { key: 'body', label: 'Note', type: 'textarea' },
    ],
  },

  // ── Projects ────────────────────────────────────────────────────────
  {
    id: 'projects', table: 'projects', label: 'Projects', singular: 'Project', area: 'projects', primaryAction: 'New project',
    description: 'Bigger jobs with tasks, files and time.', statusField: 'status', search: ['name', 'number'],
    number: { key: 'number', prefix: 'PRJ-', start: 1001 },
    fields: [
      { key: 'number', label: 'Project #', type: 'text', list: true, readOnly: true },
      { key: 'name', label: 'Project', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'owner_id', label: 'Owner', type: 'ref', ref: 'users', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Planning', 'In progress', 'On hold', 'Complete', 'Cancelled'], default: 'Planning', list: true },
      { key: 'start_date', label: 'Start', type: 'date' },
      { key: 'due_date', label: 'Due', type: 'date', list: true },
      { key: 'budget_hours', label: 'Budget hours', type: 'decimal' },
      { key: 'billable', label: 'Billable', type: 'bool', default: true },
      { key: 'description', label: 'Description', type: 'textarea' },
    ],
  },

  // ── Sales & marketing ───────────────────────────────────────────────
  {
    id: 'leads', table: 'leads', label: 'Leads', singular: 'Lead', area: 'sales', primaryAction: 'New lead',
    description: 'Prospects from first call to signed contract.', statusField: 'stage', search: ['company', 'contact_name', 'email'],
    fields: [
      { key: 'company', label: 'Company', type: 'text', required: true, list: true },
      { key: 'contact_name', label: 'Contact', type: 'text', list: true },
      { key: 'email', label: 'Email', type: 'email' },
      { key: 'phone', label: 'Phone', type: 'phone' },
      { key: 'stage', label: 'Stage', type: 'select', options: ['New', 'Contacted', 'Qualified', 'Proposal', 'Negotiation', 'Won', 'Lost'], default: 'New', list: true },
      { key: 'source', label: 'Source', type: 'text' },
      { key: 'value', label: 'Monthly value', type: 'money', list: true },
      { key: 'next_followup', label: 'Next follow-up', type: 'date', list: true },
      { key: 'assigned_to', label: 'Assigned to', type: 'ref', ref: 'users' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'campaigns', table: 'campaigns', label: 'Marketing', singular: 'Campaign', area: 'sales', primaryAction: 'New campaign',
    description: 'Email campaigns, call lists, review requests and surveys.', statusField: 'status', search: ['name'],
    fields: [
      { key: 'name', label: 'Campaign', type: 'text', required: true, list: true },
      { key: 'type', label: 'Type', type: 'select', options: ['Email', 'Call list', 'Review request', 'Survey'], default: 'Email', list: true },
      { key: 'audience', label: 'Audience', type: 'text', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Draft', 'Scheduled', 'Active', 'Sent', 'Paused'], default: 'Draft', list: true },
      { key: 'send_date', label: 'Send date', type: 'date', list: true },
      { key: 'subject', label: 'Subject line', type: 'text' },
      { key: 'body', label: 'Message / script', type: 'textarea' },
    ],
  },

  // ── Billing ─────────────────────────────────────────────────────────
  {
    id: 'invoices', table: 'invoices', label: 'Invoices', singular: 'Invoice', area: 'billing', primaryAction: 'New invoice',
    description: 'Bill clients and track what is owed.', statusField: 'status', search: ['number', 'scope'],
    number: { key: 'number', prefix: 'INV-', start: 1001 }, lineItems: { resource: 'invoice_items', fk: 'invoice_id' },
    defaultSort: { key: 'invoice_date', dir: 'desc' },
    fields: [
      { key: 'number', label: 'Invoice #', type: 'text', list: true, readOnly: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Draft', 'Sent', 'Viewed', 'Partial', 'Paid', 'Overdue', 'Void'], default: 'Draft', list: true },
      { key: 'invoice_date', label: 'Date', type: 'date', required: true, list: true },
      { key: 'due_date', label: 'Due', type: 'date', required: true, list: true },
      { key: 'tax_rate', label: 'Tax rate %', type: 'decimal' },
      { key: 'subtotal', label: 'Subtotal', type: 'money', readOnly: true },
      { key: 'tax_amount', label: 'Tax', type: 'money', readOnly: true },
      { key: 'total', label: 'Total', type: 'money', readOnly: true, list: true },
      { key: 'amount_paid', label: 'Paid', type: 'money' },
      { key: 'scope', label: 'Description of work', type: 'textarea' },
      { key: 'notes', label: 'Notes to client', type: 'textarea' },
    ],
  },
  {
    id: 'invoice_items', table: 'invoice_items', label: 'Invoice lines', singular: 'Line', area: 'billing', hidden: true,
    description: 'Invoice line items.', search: ['description'],
    fields: [
      { key: 'invoice_id', label: 'Invoice', type: 'ref', ref: 'invoices', required: true },
      { key: 'description', label: 'Description', type: 'text', required: true },
      { key: 'qty', label: 'Qty', type: 'decimal', default: 1 },
      { key: 'rate', label: 'Rate', type: 'money' },
      { key: 'taxable', label: 'Taxable', type: 'bool', default: true },
      { key: 'line_total', label: 'Total', type: 'money', readOnly: true },
      { key: 'sort_order', label: 'Order', type: 'int' },
    ],
  },
  {
    id: 'recurring', table: 'recurring_invoices', label: 'Recurring', singular: 'Recurring schedule', area: 'billing', primaryAction: 'New schedule',
    description: 'Invoices that go out on a schedule.', statusField: 'status', search: ['name'],
    lineItems: { resource: 'recurring_items', fk: 'recurring_id' },
    fields: [
      { key: 'name', label: 'Schedule', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'frequency', label: 'Every', type: 'select', options: ['Month', 'Quarter', 'Year'], default: 'Month', list: true },
      { key: 'next_run', label: 'Next run', type: 'date', required: true, list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Active', 'Paused'], default: 'Active', list: true },
      { key: 'autopay', label: 'AutoPay', type: 'bool' },
      { key: 'tax_rate', label: 'Tax rate %', type: 'decimal' },
      { key: 'total', label: 'Amount', type: 'money', readOnly: true, list: true },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'recurring_items', table: 'recurring_items', label: 'Recurring lines', singular: 'Line', area: 'billing', hidden: true,
    description: 'Recurring invoice line items.', search: ['description'],
    fields: [
      { key: 'recurring_id', label: 'Schedule', type: 'ref', ref: 'recurring', required: true },
      { key: 'description', label: 'Description', type: 'text', required: true },
      { key: 'qty', label: 'Qty', type: 'decimal', default: 1 },
      { key: 'rate', label: 'Rate', type: 'money' },
      { key: 'taxable', label: 'Taxable', type: 'bool', default: true },
      { key: 'line_total', label: 'Total', type: 'money', readOnly: true },
      { key: 'sort_order', label: 'Order', type: 'int' },
    ],
  },
  {
    id: 'banking', table: 'bank_transactions', label: 'Banking', singular: 'Transaction', area: 'billing',
    description: 'Bank transactions, matched to invoices and expenses.', statusField: 'match_status', search: ['description', 'account'],
    defaultSort: { key: 'posted_on', dir: 'desc' },
    fields: [
      { key: 'posted_on', label: 'Date', type: 'date', required: true, list: true },
      { key: 'description', label: 'Description', type: 'text', required: true, list: true },
      { key: 'account', label: 'Account', type: 'text', list: true },
      { key: 'amount', label: 'Amount', type: 'money', required: true, list: true },
      { key: 'match_status', label: 'Status', type: 'select', options: ['Unmatched', 'Matched', 'Ignored'], default: 'Unmatched', list: true },
      { key: 'invoice_id', label: 'Matched invoice', type: 'ref', ref: 'invoices' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'quotes', table: 'quotes', label: 'Quotes', singular: 'Quote', area: 'billing', primaryAction: 'New quote',
    description: 'Estimates for clients to approve.', statusField: 'status', search: ['number', 'scope'],
    number: { key: 'number', prefix: 'QT-', start: 1001 }, lineItems: { resource: 'quote_items', fk: 'quote_id' },
    defaultSort: { key: 'quote_date', dir: 'desc' },
    fields: [
      { key: 'number', label: 'Quote #', type: 'text', list: true, readOnly: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Draft', 'Sent', 'Accepted', 'Declined', 'Invoiced'], default: 'Draft', list: true },
      { key: 'quote_date', label: 'Date', type: 'date', required: true, list: true },
      { key: 'expires_on', label: 'Expires', type: 'date' },
      { key: 'tax_rate', label: 'Tax rate %', type: 'decimal' },
      { key: 'subtotal', label: 'Subtotal', type: 'money', readOnly: true },
      { key: 'tax_amount', label: 'Tax', type: 'money', readOnly: true },
      { key: 'total', label: 'Total', type: 'money', readOnly: true, list: true },
      { key: 'scope', label: 'Scope of work', type: 'textarea' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'quote_items', table: 'quote_items', label: 'Quote lines', singular: 'Line', area: 'billing', hidden: true,
    description: 'Quote line items.', search: ['description'],
    fields: [
      { key: 'quote_id', label: 'Quote', type: 'ref', ref: 'quotes', required: true },
      { key: 'description', label: 'Description', type: 'text', required: true },
      { key: 'qty', label: 'Qty', type: 'decimal', default: 1 },
      { key: 'rate', label: 'Rate', type: 'money' },
      { key: 'taxable', label: 'Taxable', type: 'bool', default: true },
      { key: 'line_total', label: 'Total', type: 'money', readOnly: true },
      { key: 'sort_order', label: 'Order', type: 'int' },
    ],
  },
  {
    id: 'contracts', table: 'contracts', label: 'Contracts', singular: 'Contract', area: 'billing', primaryAction: 'New contract',
    description: 'Service agreements and their renewal dates.', statusField: 'status', search: ['name', 'number'],
    number: { key: 'number', prefix: 'CT-', start: 1001 },
    fields: [
      { key: 'number', label: 'Contract #', type: 'text', readOnly: true },
      { key: 'name', label: 'Contract', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'type', label: 'Type', type: 'select', options: ['Managed', 'Break/fix', 'Project', 'BAA', 'NDA', 'Other'], default: 'Managed', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Draft', 'Sent', 'Active', 'Expired', 'Cancelled'], default: 'Draft', list: true },
      { key: 'start_date', label: 'Starts', type: 'date' },
      { key: 'end_date', label: 'Ends', type: 'date', list: true },
      { key: 'auto_renew', label: 'Auto-renew', type: 'bool', default: true },
      { key: 'monthly_rate', label: 'Monthly rate', type: 'money', list: true },
      { key: 'included_hours', label: 'Included hours', type: 'decimal' },
      { key: 'overage_rate', label: 'Overage rate', type: 'money' },
      { key: 'scope', label: 'Scope', type: 'textarea' },
      { key: 'terms', label: 'Terms', type: 'textarea' },
    ],
  },
  {
    id: 'policies', table: 'policies', label: 'Policies', singular: 'Policy', area: 'billing', primaryAction: 'New policy',
    description: 'IT and security policies clients review and acknowledge.', statusField: 'status', search: ['name'],
    fields: [
      { key: 'name', label: 'Policy', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client (blank = all clients)', type: 'ref', ref: 'clients', list: true },
      { key: 'version', label: 'Version', type: 'text', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Draft', 'Current', 'Review due', 'Retired'], default: 'Draft', list: true },
      { key: 'next_review', label: 'Next review', type: 'date', list: true },
      { key: 'body', label: 'Policy text', type: 'textarea' },
    ],
  },
  {
    id: 'training', table: 'training_assignments', label: 'Security Training', singular: 'Training assignment', area: 'billing', primaryAction: 'Assign course',
    description: 'Security courses assigned to client staff, with completion.', statusField: 'status', search: ['course'],
    fields: [
      { key: 'course', label: 'Course', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'learners', label: 'Learners', type: 'int', list: true },
      { key: 'due_date', label: 'Due', type: 'date', list: true },
      { key: 'progress', label: 'Progress %', type: 'int', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Not started', 'In progress', 'Complete'], default: 'Not started', list: true },
    ],
  },
  {
    id: 'renewals', table: 'renewals', label: 'Renewals', singular: 'Renewal', area: 'billing', primaryAction: 'Add renewal',
    description: 'Licenses, domains, warranties and contracts coming up for renewal.', statusField: 'status', search: ['item'],
    defaultSort: { key: 'renews_on', dir: 'asc' },
    fields: [
      { key: 'item', label: 'Item', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'type', label: 'Type', type: 'select', options: ['License', 'Domain', 'Warranty', 'Contract', 'Subscription', 'Other'], list: true },
      { key: 'renews_on', label: 'Renews', type: 'date', required: true, list: true },
      { key: 'cost', label: 'Cost', type: 'money', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Upcoming', 'Renewed', 'Cancelled'], default: 'Upcoming', list: true },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'expenses', table: 'expenses', label: 'Expenses', singular: 'Expense', area: 'billing', primaryAction: 'Add expense',
    description: 'Costs and billable expenses.', search: ['description', 'category'],
    defaultSort: { key: 'spent_on', dir: 'desc' },
    fields: [
      { key: 'spent_on', label: 'Date', type: 'date', required: true, list: true },
      { key: 'vendor_id', label: 'Vendor', type: 'ref', ref: 'vendors', list: true },
      { key: 'category', label: 'Category', type: 'text', list: true },
      { key: 'amount', label: 'Amount', type: 'money', required: true, list: true },
      { key: 'client_id', label: 'Bill to client', type: 'ref', ref: 'clients' },
      { key: 'billable', label: 'Billable', type: 'bool', list: true },
      { key: 'description', label: 'Description', type: 'text' },
    ],
  },
  {
    id: 'vendors', table: 'vendors', label: 'Vendors', singular: 'Vendor', area: 'billing', primaryAction: 'Add vendor',
    description: 'Suppliers, distributors and their account reps.', search: ['name', 'contact_name'],
    defaultSort: { key: 'name', dir: 'asc' },
    fields: [
      { key: 'name', label: 'Vendor', type: 'text', required: true, list: true },
      { key: 'category', label: 'Category', type: 'text', list: true },
      { key: 'contact_name', label: 'Account rep', type: 'text', list: true },
      { key: 'email', label: 'Email', type: 'email' },
      { key: 'phone', label: 'Phone', type: 'phone', list: true },
      { key: 'website', label: 'Website', type: 'url' },
      { key: 'account_number', label: 'Our account number', type: 'secret' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },

  // ── Tools ───────────────────────────────────────────────────────────
  {
    id: 'calendar', table: 'calendar_events', label: 'Calendar', singular: 'Event', area: 'tools', primaryAction: 'New event',
    description: 'Schedule and on-site visits.', search: ['title'], defaultSort: { key: 'starts_at', dir: 'asc' },
    fields: [
      { key: 'title', label: 'Event', type: 'text', required: true, list: true },
      { key: 'starts_at', label: 'Starts', type: 'datetime', required: true, list: true },
      { key: 'ends_at', label: 'Ends', type: 'datetime' },
      { key: 'user_id', label: 'Who', type: 'ref', ref: 'users', list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'location', label: 'Location', type: 'text' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'inventory', table: 'inventory_items', label: 'Inventory', singular: 'Item', area: 'tools', primaryAction: 'Add item',
    description: 'Parts and hardware in stock.', search: ['name', 'sku'], defaultSort: { key: 'name', dir: 'asc' },
    fields: [
      { key: 'name', label: 'Item', type: 'text', required: true, list: true },
      { key: 'sku', label: 'SKU', type: 'text', list: true },
      { key: 'on_hand', label: 'On hand', type: 'int', list: true },
      { key: 'reorder_at', label: 'Reorder at', type: 'int' },
      { key: 'cost', label: 'Cost', type: 'money', list: true },
      { key: 'price', label: 'Price', type: 'money', list: true },
      { key: 'location', label: 'Stored at', type: 'text' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'mileage', table: 'mileage_trips', label: 'Mileage', singular: 'Trip', area: 'tools', primaryAction: 'Log trip', ownerScoped: true,
    description: 'Trips to client sites.', search: ['trip'], defaultSort: { key: 'trip_date', dir: 'desc' },
    fields: [
      { key: 'trip_date', label: 'Date', type: 'date', required: true, list: true },
      { key: 'trip', label: 'From → To', type: 'text', required: true, list: true },
      { key: 'miles', label: 'Miles', type: 'decimal', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'billable', label: 'Billable', type: 'bool', list: true },
      { key: 'user_id', label: 'Driver', type: 'ref', ref: 'users', readOnly: true },
    ],
  },
  {
    id: 'messages', table: 'secure_messages', label: 'Secure Messages', singular: 'Message', area: 'tools', primaryAction: 'New message',
    description: 'Messages with clients through the portal. Message bodies are encrypted.', statusField: 'status', search: ['subject'],
    fields: [
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', required: true, list: true },
      { key: 'contact_id', label: 'Contact', type: 'ref', ref: 'contacts' },
      { key: 'subject', label: 'Subject', type: 'text', required: true, list: true },
      { key: 'direction', label: 'Direction', type: 'select', options: ['Inbound', 'Outbound'], default: 'Outbound', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Unread', 'Read', 'Archived'], default: 'Unread', list: true },
      { key: 'body', label: 'Message', type: 'secret' },
    ],
  },
  {
    id: 'domains', table: 'domains', label: 'Domains & SSL', singular: 'Domain', area: 'tools', primaryAction: 'Add domain',
    description: 'Domain expirations and SSL certificates.', search: ['name', 'registrar'], defaultSort: { key: 'expires_on', dir: 'asc' },
    fields: [
      { key: 'name', label: 'Domain', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'registrar', label: 'Registrar', type: 'text', list: true },
      { key: 'expires_on', label: 'Expires', type: 'date', list: true },
      { key: 'dns_provider', label: 'DNS provider', type: 'text' },
      { key: 'ssl_status', label: 'SSL', type: 'select', options: ['Valid', 'Expiring', 'Expired', 'None', 'Unknown'], default: 'Unknown', list: true },
      { key: 'ssl_expires_on', label: 'SSL expires', type: 'date' },
      { key: 'notes', label: 'Notes', type: 'textarea' },
    ],
  },
  {
    id: 'backups', table: 'backup_jobs', label: 'Backups', singular: 'Backup job', area: 'tools',
    description: 'Backup jobs across every client (synced from MSP360).', statusField: 'last_result', search: ['device', 'plan'],
    fields: [
      { key: 'device', label: 'Device', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'plan', label: 'Plan', type: 'text', list: true },
      { key: 'last_run_at', label: 'Last run', type: 'datetime', list: true },
      { key: 'last_result', label: 'Result', type: 'select', options: ['Success', 'Warning', 'Failed', 'Running', 'Unknown'], default: 'Unknown', list: true },
      { key: 'storage_gb', label: 'Storage (GB)', type: 'decimal' },
    ],
  },
  {
    id: 'rmm', table: 'rmm_devices', label: 'RMM', singular: 'Device', area: 'tools',
    description: 'Devices from Datto RMM.', statusField: 'status', search: ['name', 'os'],
    fields: [
      { key: 'name', label: 'Device', type: 'text', required: true, list: true },
      { key: 'client_id', label: 'Client', type: 'ref', ref: 'clients', list: true },
      { key: 'os', label: 'OS', type: 'text', list: true },
      { key: 'last_seen_at', label: 'Last seen', type: 'datetime', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['OK', 'Warning', 'Critical', 'Offline'], default: 'OK', list: true },
      { key: 'rmm_uid', label: 'RMM device ID', type: 'text' },
    ],
  },
  {
    id: 'kb', table: 'kb_articles', label: 'Knowledge Base', singular: 'Article', area: 'tools', primaryAction: 'New article',
    description: 'How-to articles for your team and for clients in the portal.', statusField: 'visibility', search: ['title', 'body', 'category'],
    fields: [
      { key: 'title', label: 'Article', type: 'text', required: true, list: true },
      { key: 'category', label: 'Category', type: 'text', list: true },
      { key: 'visibility', label: 'Visibility', type: 'select', options: ['Staff only', 'Portal', 'Draft'], default: 'Staff only', list: true },
      { key: 'views', label: 'Views', type: 'int', readOnly: true, list: true },
      { key: 'body', label: 'Article', type: 'textarea' },
    ],
  },
  {
    id: 'workflows', table: 'workflows', label: 'Workflows', singular: 'Workflow', area: 'admin', primaryAction: 'New workflow',
    description: 'Automations: when something happens, do something.', statusField: 'status', search: ['name'],
    fields: [
      { key: 'name', label: 'Workflow', type: 'text', required: true, list: true },
      { key: 'trigger', label: 'When', type: 'select', options: ['Ticket created', 'Ticket updated', 'SLA at risk', 'Invoice overdue', 'Client created', 'Contract expiring'], required: true, list: true },
      { key: 'conditions', label: 'Only if', type: 'textarea', help: 'Example: priority = Critical' },
      { key: 'action', label: 'Then', type: 'select', options: ['Send email', 'Notify Google Chat', 'Assign to', 'Set priority', 'Create task'], required: true, list: true },
      { key: 'action_value', label: 'Action details', type: 'text' },
      { key: 'status', label: 'Status', type: 'select', options: ['Active', 'Paused'], default: 'Active', list: true },
      { key: 'runs', label: 'Runs', type: 'int', readOnly: true, list: true },
    ],
  },

  // ── H/R ─────────────────────────────────────────────────────────────
  {
    id: 'employees', table: 'hr_employees', label: 'H/R Admin', singular: 'Employee', area: 'hr', primaryAction: 'Add employee',
    description: 'Employees. SSN and bank details are encrypted and every reveal is logged.', statusField: 'status', search: ['name', 'title'],
    fields: [
      { key: 'name', label: 'Employee', type: 'text', required: true, list: true },
      { key: 'user_id', label: 'Login account', type: 'ref', ref: 'users' },
      { key: 'title', label: 'Title', type: 'text', list: true },
      { key: 'office', label: 'Office', type: 'select', options: ['El Paso', 'Phoenix', 'Remote'], list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Active', 'Onboarding', 'On leave', 'Terminated'], default: 'Active', list: true },
      { key: 'hire_date', label: 'Started', type: 'date', list: true },
      { key: 'email', label: 'Work email', type: 'email' },
      { key: 'phone', label: 'Phone', type: 'phone' },
      { key: 'pay_type', label: 'Pay type', type: 'select', options: ['Hourly', 'Salary'] },
      { key: 'pto_balance_hours', label: 'PTO balance (hours)', type: 'decimal' },
      { key: 'ssn', label: 'SSN', type: 'secret' },
      { key: 'bank_routing', label: 'Bank routing #', type: 'secret' },
      { key: 'bank_account', label: 'Bank account #', type: 'secret' },
      { key: 'emergency_contact', label: 'Emergency contact', type: 'text' },
    ],
  },
  {
    id: 'pto', table: 'hr_pto_requests', label: 'Time off', singular: 'Time-off request', area: 'hr', primaryAction: 'Request time off', ownerScoped: true,
    description: 'Time-off requests.', statusField: 'status', search: ['reason'], defaultSort: { key: 'starts_on', dir: 'desc' },
    fields: [
      { key: 'user_id', label: 'Employee', type: 'ref', ref: 'users', readOnly: true, list: true },
      { key: 'kind', label: 'Type', type: 'select', options: ['Vacation', 'Sick', 'Personal', 'Unpaid'], default: 'Vacation', list: true },
      { key: 'starts_on', label: 'From', type: 'date', required: true, list: true },
      { key: 'ends_on', label: 'To', type: 'date', required: true, list: true },
      { key: 'hours', label: 'Hours', type: 'decimal', required: true, list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Pending', 'Approved', 'Denied'], default: 'Pending', list: true },
      { key: 'reason', label: 'Note', type: 'text' },
    ],
  },
  {
    id: 'timeclock', table: 'hr_timeclock', label: 'Timeclock', singular: 'Time entry', area: 'hr', ownerScoped: true,
    description: 'Clock-in and clock-out records.', statusField: 'status', search: [], defaultSort: { key: 'clock_in', dir: 'desc' },
    fields: [
      { key: 'user_id', label: 'Employee', type: 'ref', ref: 'users', readOnly: true, list: true },
      { key: 'clock_in', label: 'Clock in', type: 'datetime', required: true, list: true },
      { key: 'clock_out', label: 'Clock out', type: 'datetime', list: true },
      { key: 'status', label: 'Status', type: 'select', options: ['Open', 'Submitted', 'Approved'], default: 'Open', list: true },
      { key: 'notes', label: 'Notes', type: 'text' },
    ],
  },
];

export const RES: Record<string, Resource> = Object.fromEntries(RESOURCES.map((r) => [r.id, r]));

// ── Menu (same items and order as the old Weststar One sidebar) ──────────
export interface NavItem { id: string; label: string; icon: string; path: string; area: PermArea }
export interface NavGroup { group: string | null; short?: string; icon?: string; items: NavItem[] }

const n = (id: string, label: string, area: PermArea, path?: string, icon?: string): NavItem => ({ id, label, area, icon: icon ?? id, path: path ?? '/' + id });

export const NAV: NavGroup[] = [
  { group: null, items: [n('dashboard', 'Dashboard', 'tickets', '/'), n('tickets', 'Tickets', 'tickets'), n('projects', 'Projects', 'projects')] },
  { group: 'CRM & Marketing', short: 'CRM', icon: 'clients', items: [n('clients', 'Clients', 'clients')] },
  { group: 'Sales & Marketing', short: 'Sales', icon: 'leads', items: [n('leads', 'Leads', 'sales'), n('marketing', 'Marketing', 'sales', '/campaigns')] },
  { group: 'Billing', short: 'Billing', icon: 'invoices', items: [
    n('invoices', 'Invoices', 'billing'), n('recurring', 'Recurring', 'billing'), n('banking', 'Banking', 'billing'),
    n('quotes', 'Quotes', 'billing'), n('contracts', 'Contracts', 'billing'), n('policies', 'Policies', 'billing'),
    n('training', 'Security Training', 'billing'), n('renewals', 'Renewals', 'billing'), n('expenses', 'Expenses', 'billing'), n('vendors', 'Vendors', 'billing'),
  ] },
  { group: 'Tools', short: 'Tools', icon: 'tools', items: [
    n('calendar', 'Calendar', 'tools'), n('inventory', 'Inventory', 'tools'), n('mileage', 'Mileage', 'tools'),
    n('messages', 'Secure Messages', 'tools'), n('domains', 'Domains & SSL', 'tools'), n('backups', 'Backups', 'tools'),
    n('rmm', 'RMM', 'tools'), n('kb', 'Knowledge Base', 'tools'), n('workflows', 'Workflows', 'admin'),
  ] },
  { group: 'H/R', short: 'H/R', icon: 'my_hr', items: [n('my_hr', 'My HR', 'tickets', '/my-hr'), n('hr', 'H/R Admin', 'hr', '/employees')] },
  { group: 'Admin', short: 'Admin', icon: 'settings', items: [n('settings', 'Settings', 'admin')] },
];

// ── Roles and permissions ────────────────────────────────────────────────
export const ROLES = ['admin', 'manager', 'tech', 'viewer'] as const;
export type Role = (typeof ROLES)[number];

const ORDER: Level[] = ['none', 'view', 'edit', 'manage'];
export const ROLE_LEVELS: Record<Role, Record<PermArea, Level>> = {
  admin: { tickets: 'manage', clients: 'manage', projects: 'manage', sales: 'manage', billing: 'manage', tools: 'manage', hr: 'manage', admin: 'manage' },
  manager: { tickets: 'manage', clients: 'manage', projects: 'manage', sales: 'manage', billing: 'manage', tools: 'manage', hr: 'none', admin: 'view' },
  tech: { tickets: 'edit', clients: 'edit', projects: 'edit', sales: 'view', billing: 'none', tools: 'edit', hr: 'none', admin: 'none' },
  viewer: { tickets: 'view', clients: 'view', projects: 'view', sales: 'none', billing: 'none', tools: 'view', hr: 'none', admin: 'none' },
};

/** HR access is its own switch on a user (like the old user_hr_access), on top of their role. */
export function levelFor(role: Role, area: PermArea, hrAccess = false): Level {
  if (area === 'hr' && hrAccess) return 'manage';
  return ROLE_LEVELS[role]?.[area] ?? 'none';
}
export function atLeast(have: Level, need: Level): boolean {
  return ORDER.indexOf(have) >= ORDER.indexOf(need);
}
/** Owner-scoped resources (time off, timeclock, mileage) are usable by everyone for their own rows. */
export function canUse(role: Role, r: Resource, need: Level, hrAccess = false): boolean {
  if (r.ownerScoped && (need === 'view' || need === 'edit')) return true;
  return atLeast(levelFor(role, r.area, hrAccess), need);
}

export { yesNo };
