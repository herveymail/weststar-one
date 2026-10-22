import {
  pgTable, serial, integer, text, varchar, boolean, timestamp, date, numeric, jsonb, index, uniqueIndex, primaryKey,
  type AnyPgColumn, type PgTableWithColumns,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';
import { RESOURCES, type Field } from '@ws/shared';

const created = () => timestamp('created_at', { withTimezone: true }).notNull().defaultNow();
const updated = () => timestamp('updated_at', { withTimezone: true }).notNull().defaultNow();

// ─────────────────────────────── Core tables ───────────────────────────────

export const users = pgTable('users', {
  id: serial('id').primaryKey(),
  email: varchar('email', { length: 254 }).notNull(),
  name: varchar('name', { length: 200 }).notNull(),
  /** argon2id hash, or a bcrypt hash carried over from the old app until the user next signs in. */
  password_hash: text('password_hash').notNull(),
  role: varchar('role', { length: 20 }).notNull().default('tech'),
  hr_access: boolean('hr_access').notNull().default(false),
  title: varchar('title', { length: 100 }),
  phone: varchar('phone', { length: 50 }),
  look: varchar('look', { length: 20 }).notNull().default('indigo'),
  /** TOTP seed, encrypted with APP_ENCRYPTION_KEY. */
  totp_secret_enc: text('totp_secret_enc'),
  /** New seed waiting for the user to confirm a first code. */
  totp_pending_enc: text('totp_pending_enc'),
  /** Last accepted 30-second step — a code can only be used once. */
  totp_last_step: integer('totp_last_step'),
  mfa_enabled: boolean('mfa_enabled').notNull().default(false),
  failed_logins: integer('failed_logins').notNull().default(0),
  locked_until: timestamp('locked_until', { withTimezone: true }),
  last_login_at: timestamp('last_login_at', { withTimezone: true }),
  password_changed_at: timestamp('password_changed_at', { withTimezone: true }),
  must_change_password: boolean('must_change_password').notNull().default(false),
  legacy_id: integer('legacy_id'),
  archived_at: timestamp('archived_at', { withTimezone: true }),
  created_at: created(),
  updated_at: updated(),
}, (t) => [uniqueIndex('users_email_lower').on(sql`lower(${t.email})`), uniqueIndex('users_legacy').on(t.legacy_id)]);

export const mfaRecoveryCodes = pgTable('mfa_recovery_codes', {
  id: serial('id').primaryKey(),
  user_id: integer('user_id').notNull().references(() => users.id, { onDelete: 'cascade' }),
  code_hash: text('code_hash').notNull(),
  used_at: timestamp('used_at', { withTimezone: true }),
  created_at: created(),
}, (t) => [index('mfa_codes_user').on(t.user_id)]);

export const sessions = pgTable('sessions', {
  /** sha256 of the cookie token — the token itself is never stored. */
  id: varchar('id', { length: 64 }).primaryKey(),
  user_id: integer('user_id').notNull().references(() => users.id, { onDelete: 'cascade' }),
  csrf_token: varchar('csrf_token', { length: 64 }).notNull(),
  /** false while the user still owes a two-factor code. */
  mfa_passed: boolean('mfa_passed').notNull().default(false),
  ip: varchar('ip', { length: 64 }),
  user_agent: varchar('user_agent', { length: 300 }),
  created_at: created(),
  last_seen_at: timestamp('last_seen_at', { withTimezone: true }).notNull().defaultNow(),
  expires_at: timestamp('expires_at', { withTimezone: true }).notNull(),
  revoked_at: timestamp('revoked_at', { withTimezone: true }),
}, (t) => [index('sessions_user').on(t.user_id)]);

export const loginAttempts = pgTable('login_attempts', {
  id: serial('id').primaryKey(),
  email: varchar('email', { length: 254 }),
  ip: varchar('ip', { length: 64 }),
  success: boolean('success').notNull(),
  reason: varchar('reason', { length: 60 }),
  created_at: created(),
}, (t) => [index('login_attempts_ip_time').on(t.ip, t.created_at), index('login_attempts_email_time').on(t.email, t.created_at)]);

export const auditLog = pgTable('audit_log', {
  id: serial('id').primaryKey(),
  user_id: integer('user_id').references(() => users.id, { onDelete: 'set null' }),
  action: varchar('action', { length: 40 }).notNull(),
  entity: varchar('entity', { length: 60 }).notNull(),
  entity_id: varchar('entity_id', { length: 60 }),
  summary: varchar('summary', { length: 500 }),
  changes: jsonb('changes'),
  ip: varchar('ip', { length: 64 }),
  created_at: created(),
}, (t) => [index('audit_entity').on(t.entity, t.entity_id), index('audit_time').on(t.created_at)]);

export const settings = pgTable('settings', {
  key: varchar('key', { length: 120 }).primaryKey(),
  /** Plain text, or ciphertext when is_secret. */
  value: text('value').notNull().default(''),
  is_secret: boolean('is_secret').notNull().default(false),
  updated_by: integer('updated_by').references(() => users.id, { onDelete: 'set null' }),
  updated_at: updated(),
});

/** Number sequences (ticket, invoice, quote …). Incremented under a row lock. */
export const counters = pgTable('counters', {
  name: varchar('name', { length: 60 }).primaryKey(),
  value: integer('value').notNull(),
});

export const importRuns = pgTable('import_runs', {
  id: serial('id').primaryKey(),
  started_at: timestamp('started_at', { withTimezone: true }).notNull().defaultNow(),
  finished_at: timestamp('finished_at', { withTimezone: true }),
  dry_run: boolean('dry_run').notNull().default(false),
  summary: jsonb('summary'),
  error: text('error'),
});

// ─────────────────────── Tables generated from the registry ───────────────────────

type AnyTable = PgTableWithColumns<any>;
export const resourceTables: Record<string, AnyTable> = {};

function refTable(ref: string): AnyTable {
  if (ref === 'users') return users as unknown as AnyTable;
  const t = resourceTables[ref];
  if (!t) throw new Error(`Unknown ref ${ref}`);
  return t;
}

function column(f: Field, parentFk: string | undefined) {
  switch (f.type) {
    case 'int': return integer(f.key);
    case 'decimal': return numeric(f.key, { precision: 14, scale: 2 });
    case 'money': return numeric(f.key, { precision: 14, scale: 2 });
    case 'date': return date(f.key);
    case 'datetime': return timestamp(f.key, { withTimezone: true });
    case 'bool': return boolean(f.key);
    case 'ref': {
      const c = integer(f.key);
      const onDelete = f.key === parentFk ? 'cascade' : f.required ? 'restrict' : 'set null';
      return c.references(() => refTable(f.ref!).id as AnyPgColumn, { onDelete });
    }
    case 'secret': case 'textarea': return text(f.key);
    default: return varchar(f.key, { length: f.max ?? 500 });
  }
}

// Line-item tables reference their parent with cascade; find those foreign keys first.
const parentFks = new Map<string, string>();
for (const r of RESOURCES) if (r.lineItems) parentFks.set(r.lineItems.resource, r.lineItems.fk);

for (const r of RESOURCES) {
  const cols: Record<string, any> = { id: serial('id').primaryKey() };
  for (const f of r.fields) {
    let c = column(f, parentFks.get(r.id));
    if (f.required && f.type !== 'ref') c = c.notNull();
    if (f.required && f.type === 'ref') c = c.notNull();
    if (f.default !== undefined && f.type !== 'ref') c = c.default(f.default as never);
    cols[f.key] = c;
  }
  cols.legacy_id = integer('legacy_id');
  cols.created_by = integer('created_by').references(() => users.id, { onDelete: 'set null' });
  cols.archived_at = timestamp('archived_at', { withTimezone: true });
  cols.created_at = created();
  cols.updated_at = updated();
  const refCols = r.fields.filter((f) => f.type === 'ref').map((f) => f.key);
  resourceTables[r.id] = pgTable(r.table, cols, (t: any) => [
    uniqueIndex(`${r.table}_legacy`).on(t.legacy_id),
    ...refCols.map((k) => index(`${r.table}_${k}`).on(t[k])),
    ...(r.number ? [uniqueIndex(`${r.table}_${r.number.key}`).on(t[r.number.key])] : []),
  ]) as AnyTable;
}

// Explicit exports so drizzle-kit sees every table.
export const {
  clients, contacts, assets, networks, client_notes, projects, leads, campaigns, invoices, invoice_items, recurring,
  recurring_items, banking, quotes, quote_items, contracts, policies, training, renewals, expenses, vendors,
  calendar, inventory, mileage, messages, domains, backups, rmm, kb, workflows, employees, pto, timeclock,
} = resourceTables;

// ─────────────────────────────── Tickets ───────────────────────────────

export const tickets = pgTable('tickets', {
  id: serial('id').primaryKey(),
  number: varchar('number', { length: 30 }).notNull(),
  subject: varchar('subject', { length: 255 }).notNull(),
  details: text('details').notNull().default(''),
  client_id: integer('client_id').references(() => clients.id as AnyPgColumn, { onDelete: 'set null' }),
  contact_id: integer('contact_id').references(() => contacts.id as AnyPgColumn, { onDelete: 'set null' }),
  contact_name: varchar('contact_name', { length: 150 }),
  contact_email: varchar('contact_email', { length: 254 }),
  assigned_to: integer('assigned_to').references(() => users.id, { onDelete: 'set null' }),
  priority: varchar('priority', { length: 20 }).notNull().default('Medium'),
  status: varchar('status', { length: 30 }).notNull().default('New'),
  category: varchar('category', { length: 100 }),
  source: varchar('source', { length: 20 }).notNull().default('Manual'),
  billable: boolean('billable').notNull().default(true),
  due_date: date('due_date'),
  response_due_at: timestamp('response_due_at', { withTimezone: true }),
  first_response_at: timestamp('first_response_at', { withTimezone: true }),
  resolved_at: timestamp('resolved_at', { withTimezone: true }),
  closed_at: timestamp('closed_at', { withTimezone: true }),
  sla_breached: boolean('sla_breached').notNull().default(false),
  created_by: integer('created_by').references(() => users.id, { onDelete: 'set null' }),
  legacy_id: integer('legacy_id'),
  created_at: created(),
  updated_at: updated(),
}, (t) => [
  uniqueIndex('tickets_number').on(t.number), uniqueIndex('tickets_legacy').on(t.legacy_id),
  index('tickets_status').on(t.status), index('tickets_client').on(t.client_id), index('tickets_assigned').on(t.assigned_to),
]);

export const ticketMessages = pgTable('ticket_messages', {
  id: serial('id').primaryKey(),
  ticket_id: integer('ticket_id').notNull().references(() => tickets.id, { onDelete: 'cascade' }),
  kind: varchar('kind', { length: 10 }).notNull(), // reply | note | event
  author_user_id: integer('author_user_id').references(() => users.id, { onDelete: 'set null' }),
  author_name: varchar('author_name', { length: 200 }),
  via: varchar('via', { length: 20 }).notNull().default('web'),
  body: text('body').notNull(),
  legacy_id: integer('legacy_id'),
  created_at: created(),
}, (t) => [index('ticket_messages_ticket').on(t.ticket_id, t.created_at), uniqueIndex('ticket_messages_legacy').on(t.legacy_id)]);

export const ticketTime = pgTable('ticket_time_entries', {
  id: serial('id').primaryKey(),
  ticket_id: integer('ticket_id').notNull().references(() => tickets.id, { onDelete: 'cascade' }),
  user_id: integer('user_id').references(() => users.id, { onDelete: 'set null' }),
  minutes: integer('minutes').notNull(),
  work_type: varchar('work_type', { length: 40 }).notNull().default('Remote'),
  description: text('description').notNull().default(''),
  billable: boolean('billable').notNull().default(true),
  work_date: date('work_date').notNull(),
  invoice_id: integer('invoice_id').references(() => invoices.id as AnyPgColumn, { onDelete: 'set null' }),
  legacy_id: integer('legacy_id'),
  created_at: created(),
}, (t) => [index('ticket_time_ticket').on(t.ticket_id), uniqueIndex('ticket_time_legacy').on(t.legacy_id)]);

export { primaryKey };
