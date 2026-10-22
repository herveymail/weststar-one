/**
 * Legacy importer — copies everything from the old Weststar One (MariaDB) into the new database.
 *
 *  • Idempotent: every imported row keeps its old id in `legacy_id`, and re-running updates rows
 *    instead of duplicating them. Run it as often as you like during the side-by-side period.
 *  • Ticket, invoice, quote and project numbers are kept exactly as they were.
 *  • Secrets (TOTP seeds, Wi-Fi passwords, HR SSN/bank fields) are decrypted with the OLD keys and
 *    re-encrypted with the new APP_ENCRYPTION_KEY. Plaintext never touches disk.
 *  • Old bcrypt password hashes are kept; each person's password is upgraded to argon2id the first
 *    time they sign in. Nobody has to reset their password.
 *  • --dry-run does everything inside a transaction and rolls it back.
 */
import mysql from 'mysql2/promise';
import { sql, inArray, eq } from 'drizzle-orm';
import { db, type Tx } from '../db';
import { importRuns, resourceTables, tickets, ticketMessages, ticketTime, users } from '../db/schema';
import { encrypt } from '../lib/crypto';
import { bumpCounter, audit } from '../lib/util';
import { decryptNetSecret, decryptSetting, decryptValue } from './legacy-crypto';

export interface ImportOptions {
  mysqlUrl: string;
  appKey: string;            // old APP_KEY
  encryptionKey: string;     // old ENCRYPTION_KEY (hex)
  dryRun?: boolean;
  log?: (msg: string) => void;
}

type Row = Record<string, any>;
interface Step { name: string; source: number; imported: number; skipped: number; warnings: string[] }

const title = (s: unknown, allowed: readonly string[], fallback: string) => {
  const v = String(s ?? '').trim().toLowerCase().replace(/[_-]+/g, ' ');
  return allowed.find((a) => a.toLowerCase() === v) ?? fallback;
};
const str = (v: unknown, max = 500) => (v == null || v === '' ? null : String(v).slice(0, max));
const txt = (v: unknown) => (v == null ? null : String(v));
const num = (v: unknown) => (v == null || v === '' || Number.isNaN(Number(v)) ? null : String(Number(v)));
const int = (v: unknown) => (v == null || v === '' || Number.isNaN(Number(v)) ? null : Math.trunc(Number(v)));
const bool = (v: unknown) => v === 1 || v === '1' || v === true;
const day = (v: unknown) => {
  if (v == null || v === '') return null;
  const s = v instanceof Date ? v.toISOString().slice(0, 10) : String(v).slice(0, 10);
  return /^\d{4}-\d{2}-\d{2}$/.test(s) && !s.startsWith('0000') ? s : null;
};
const ts = (v: unknown) => {
  if (v == null || v === '') return null;
  const d = v instanceof Date ? v : new Date(String(v).replace(' ', 'T') + 'Z');
  return Number.isNaN(d.getTime()) || d.getUTCFullYear() < 1971 ? null : d;
};
const email = (v: unknown) => { const s = String(v ?? '').trim(); return /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(s) ? s.slice(0, 254) : null; };
const url = (v: unknown) => { const s = String(v ?? '').trim(); if (!s) return null; return (/^https?:\/\//i.test(s) ? s : 'https://' + s).slice(0, 500); };

const TICKET_STATUS: Record<string, string> = {
  new: 'New', open: 'Open', in_progress: 'Open', pending: 'Waiting on client', on_hold: 'Waiting on client',
  waiting: 'Waiting on client', waiting_on_client: 'Waiting on client', waiting_on_vendor: 'Waiting on vendor',
  scheduled: 'Scheduled', resolved: 'Resolved', closed: 'Closed', cancelled: 'Closed',
};

export async function runImport(o: ImportOptions) {
  const log = o.log ?? console.log;
  const src = await mysql.createConnection({ uri: o.mysqlUrl, dateStrings: ['DATE'], timezone: 'Z', supportBigNumbers: true, bigNumberStrings: false });
  const steps: Step[] = [];
  const idMap: Record<string, Map<number, number>> = {};
  const [run] = await db().insert(importRuns).values({ dry_run: !!o.dryRun }).returning();

  const tableExists = async (t: string) => {
    const [rows] = await src.query<any[]>('SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = ?', [t]);
    return Number(rows[0].n) > 0;
  };
  const read = async (t: string, order: string): Promise<Row[]> => {
    if (!(await tableExists(t))) return [];
    const [rows] = await src.query<any[]>(`SELECT * FROM \`${t}\` ORDER BY \`${order}\``);
    return rows;
  };
  const ref = (map: string, v: unknown) => (v == null ? null : idMap[map]?.get(Number(v)) ?? null);

  /** Upsert rows into a registry table, keyed on legacy_id; records the old→new id map. */
  async function upsert(tx: Tx, resId: string, legacyKey: string, rows: Row[], mapRow: (r: Row, w: string[]) => Row | null, stepName = resId) {
    const t = resourceTables[resId];
    const step: Step = { name: stepName, source: rows.length, imported: 0, skipped: 0, warnings: [] };
    idMap[resId] ??= new Map();
    for (let i = 0; i < rows.length; i += 400) {
      const chunk: Row[] = [];
      for (const r of rows.slice(i, i + 400)) {
        const v = mapRow(r, step.warnings);
        if (!v) { step.skipped++; continue; }
        chunk.push({ ...v, legacy_id: Number(r[legacyKey]) });
      }
      if (!chunk.length) continue;
      const cols = Object.keys(chunk[0]).filter((k) => k !== 'legacy_id');
      const set = Object.fromEntries(cols.map((k) => [k, sql.raw(`excluded."${k}"`)]));
      const res = await tx.insert(t).values(chunk).onConflictDoUpdate({ target: t.legacy_id, set }).returning({ id: t.id, legacy_id: t.legacy_id });
      for (const x of res as { id: number; legacy_id: number }[]) idMap[resId].set(x.legacy_id, x.id);
      step.imported += res.length;
    }
    steps.push(step);
    log(`  ${stepName.padEnd(18)} ${String(step.imported).padStart(6)} of ${step.source}${step.skipped ? `  (${step.skipped} skipped)` : ''}`);
    return step;
  }

  /** Replace an imported parent's line items. */
  async function lineItems(tx: Tx, resId: string, fk: string, parentMap: string, rows: Row[], parentKey: string, mapRow: (r: Row) => Row) {
    const t = resourceTables[resId];
    const parents = [...new Set(rows.map((r) => ref(parentMap, r[parentKey])).filter((x): x is number => !!x))];
    for (let i = 0; i < parents.length; i += 500) await tx.delete(t).where(inArray(t[fk], parents.slice(i, i + 500)));
    const vals = rows.map((r) => ({ ...mapRow(r), [fk]: ref(parentMap, r[parentKey]), legacy_id: null })).filter((v) => v[fk]);
    for (let i = 0; i < vals.length; i += 500) await tx.insert(t).values(vals.slice(i, i + 500));
    steps.push({ name: resId, source: rows.length, imported: vals.length, skipped: rows.length - vals.length, warnings: [] });
    log(`  ${resId.padEnd(18)} ${String(vals.length).padStart(6)} of ${rows.length}`);
  }

  const secretOrWarn = (fn: () => string, w: string[], what: string): string | null => {
    try { const v = fn(); return v ? encrypt(v) : null; } catch { w.push(`Could not decrypt ${what} — check the old keys`); return null; }
  };

  try {
    await db().transaction(async (tx) => {
      log('Importing from the old Weststar One…');

      // ── Users ──
      {
        const rows = await read('users', 'user_id');
        const step: Step = { name: 'users', source: rows.length, imported: 0, skipped: 0, warnings: [] };
        idMap.users = new Map();
        for (const r of rows) {
          const em = email(r.user_email);
          if (!em) { step.skipped++; step.warnings.push(`user ${r.user_id}: no valid email`); continue; }
          let totp: string | null = null;
          if (r.user_totp_secret) totp = secretOrWarn(() => decryptSetting(String(r.user_totp_secret), o.appKey), step.warnings, `2FA seed for ${em}`);
          else if (r.user_2fa_secret) totp = encrypt(String(r.user_2fa_secret));
          const hash = String(r.user_password ?? '');
          const role = ['admin', 'manager', 'tech', 'viewer'].includes(r.user_role) ? r.user_role : 'tech';
          const values = {
            email: em, name: str(r.user_name, 200) ?? em, role, hr_access: bool(r.user_hr_access) || role === 'admin',
            title: str(r.user_title, 100), phone: str(r.user_phone, 50),
            password_hash: /^\$2[aby]\$|^\$argon2/.test(hash) ? hash : '!disabled',
            totp_secret_enc: totp, mfa_enabled: bool(r.user_2fa_enabled) && !!totp,
            must_change_password: bool(r.user_force_password_change),
            last_login_at: ts(r.user_last_login), archived_at: bool(r.user_archived) ? new Date() : null,
            legacy_id: Number(r.user_id),
          };
          // Match by legacy id first, then by email (the admin you created with seed:admin).
          const [existing] = await tx.select({ id: users.id }).from(users)
            .where(sql`${users.legacy_id} = ${values.legacy_id} OR lower(${users.email}) = ${em.toLowerCase()}`).limit(1);
          let id: number;
          if (existing) {
            const keep = await tx.select({ hash: users.password_hash, mfa: users.mfa_enabled, totp: users.totp_secret_enc }).from(users).where(eq(users.id, existing.id));
            // Don't clobber a password or 2FA someone already set up in the new app.
            const newer = keep[0].hash.startsWith('$argon2');
            await tx.update(users).set({ ...values, ...(newer ? { password_hash: keep[0].hash, must_change_password: false } : {}), ...(keep[0].mfa ? { totp_secret_enc: keep[0].totp, mfa_enabled: true } : {}) }).where(eq(users.id, existing.id));
            id = existing.id;
          } else {
            [{ id }] = await tx.insert(users).values(values).returning({ id: users.id });
          }
          idMap.users.set(Number(r.user_id), id);
          if (values.password_hash === '!disabled') step.warnings.push(`${em}: password could not be carried over — reset it in Staff users`);
          step.imported++;
        }
        steps.push(step);
        log(`  ${'users'.padEnd(18)} ${String(step.imported).padStart(6)} of ${rows.length}`);
      }

      // ── CRM ──
      await upsert(tx, 'clients', 'client_id', await read('clients', 'client_id'), (r) => ({
        name: str(r.client_name, 200) ?? `Client ${r.client_id}`,
        status: bool(r.client_archived) ? 'Former' : title(r.client_status, ['Active', 'Lead', 'Inactive', 'Former'], 'Active'),
        type: title(r.client_type, ['Business', 'Residential', 'Nonprofit', 'Government'], 'Business'),
        plan: r.client_billing_type === 'managed' || /managed/i.test(String(r.client_contract_type ?? '')) ? 'Managed · Gold' : r.client_billing_type === 'hourly' ? 'Break/fix' : null,
        industry: str(r.client_industry), phone: str(r.client_phone), email: email(r.client_email), website: url(r.client_website),
        address: str(r.client_address), city: str(r.client_city), state: str(r.client_state), zip: str(r.client_zip),
        account_manager_id: ref('users', r.client_account_manager), hourly_rate: num(r.client_rate), tax_rate: num(r.client_tax_rate),
        net_terms: int(r.client_net_terms), sla_response_hours: int(r.client_sla_response_hours), sla_resolution_hours: int(r.client_sla_resolution_hours),
        account_alert: str(r.client_alert_note) ?? (r.client_account_alert && r.client_account_alert !== 'none' ? `Account flag: ${r.client_account_alert}` : null), notes: txt(r.client_notes),
        archived_at: bool(r.client_archived) ? new Date() : null, created_at: ts(r.client_created_at) ?? new Date(),
      }));
      await upsert(tx, 'contacts', 'contact_id', await read('contacts', 'contact_id'), (r) => {
        const client_id = ref('clients', r.contact_client_id); if (!client_id) return null;
        return {
          client_id, name: str(r.contact_name, 500) ?? 'Unnamed', title: str(r.contact_title), email: email(r.contact_email),
          phone: str(r.contact_phone), mobile: str(r.contact_mobile), is_primary: bool(r.contact_primary), notes: txt(r.contact_notes),
          role: title(String(r.contact_role ?? '').replace('_', ' '), ['Decision maker', 'Technical', 'Billing', 'End user', 'Other'], 'Other'),
          archived_at: bool(r.contact_archived) ? new Date() : null,
        };
      });
      await upsert(tx, 'vendors', 'vendor_id', await read('vendors', 'vendor_id'), (r) => ({
        name: str(r.vendor_name) ?? 'Vendor', contact_name: str(r.vendor_contact_name), email: email(r.vendor_email), phone: str(r.vendor_phone),
        website: url(r.vendor_website), account_number: r.vendor_account_number ? encrypt(String(r.vendor_account_number)) : null, notes: txt(r.vendor_notes),
      }));
      await upsert(tx, 'assets', 'asset_id', await read('assets', 'asset_id'), (r) => {
        const client_id = ref('clients', r.asset_client_id); if (!client_id) return null;
        return {
          client_id, name: str(r.asset_name) ?? 'Asset', type: title(r.asset_type, ['Workstation', 'Laptop', 'Server', 'Network', 'Printer', 'Mobile', 'Other'], 'Other'),
          status: title(r.asset_status, ['Active', 'Storage', 'RMA', 'Retired'], 'Active'), make: str(r.asset_make), model: str(r.asset_model),
          serial: str(r.asset_serial), os: str(r.asset_os), ip: str(r.asset_ip), mac: str(r.asset_mac), purchase_date: day(r.asset_purchase_date),
          warranty_expires: day(r.asset_warranty_expires ?? r.asset_warranty_expire), notes: txt(r.asset_notes), archived_at: bool(r.asset_archived) ? new Date() : null,
        };
      });
      await upsert(tx, 'networks', 'network_id', await read('client_networks', 'network_id'), (r, w) => {
        const client_id = ref('clients', r.network_client_id); if (!client_id) return null;
        return {
          client_id, name: str(r.network_domain) ?? 'Office network', subnet: str(r.network_subnet ?? r.network_lan_range), gateway: str(r.network_gateway),
          dns: [r.network_dns_primary, r.network_dns_secondary].filter(Boolean).join(', ') || null, isp: str(r.network_isp_name),
          isp_account: secretOrWarn(() => decryptNetSecret(r.network_isp_account, o.encryptionKey), w, 'ISP account'),
          wifi_ssid: str(r.network_wifi_ssid), wifi_password: secretOrWarn(() => decryptNetSecret(r.network_wifi_password, o.encryptionKey), w, 'Wi-Fi password'),
          notes: [r.network_notes, r.network_firewall_model && `Firewall: ${r.network_firewall_model} ${r.network_firewall_ip ?? ''}`, r.network_switch_model && `Switch: ${r.network_switch_model} ${r.network_switch_ip ?? ''}`].filter(Boolean).join('\n') || null,
        };
      });
      await upsert(tx, 'client_notes', 'note_id', await read('client_notes', 'note_id'), (r) => {
        const client_id = ref('clients', r.note_client_id); if (!client_id) return null;
        const body = txt(r.note_content) ?? '';
        return { client_id, title: (body.split('\n')[0] || 'Note').slice(0, 120), body, created_by: ref('users', r.note_user_id), created_at: ts(r.note_created_at) ?? new Date() };
      }, 'client notes');

      // ── Projects, sales ──
      await upsert(tx, 'projects', 'project_id', await read('projects', 'project_id'), (r) => ({
        number: str(r.project_number), name: str(r.project_name) ?? 'Project', client_id: ref('clients', r.project_client_id), owner_id: ref('users', r.project_owner_id),
        status: title(r.project_status, ['Planning', 'In progress', 'On hold', 'Complete', 'Cancelled'], r.project_completed_at ? 'Complete' : 'Planning'),
        start_date: day(r.project_start_date), due_date: day(r.project_due_date), budget_hours: num(r.project_budget_hours), billable: bool(r.project_billable),
        description: txt(r.project_description), created_at: ts(r.project_created_at) ?? new Date(),
      }));
      await upsert(tx, 'leads', 'lead_id', await read('leads', 'lead_id'), (r) => ({
        company: str(r.lead_company) ?? 'Lead', contact_name: str(r.lead_contact_name), email: email(r.lead_email), phone: str(r.lead_phone),
        stage: title(r.lead_stage, ['New', 'Contacted', 'Qualified', 'Proposal', 'Negotiation', 'Won', 'Lost'], 'New'), source: str(r.lead_source),
        value: num(r.lead_value ?? r.lead_estimated_value), next_followup: day(r.lead_next_followup), assigned_to: ref('users', r.lead_assigned_to), notes: txt(r.lead_notes),
      }));
      await upsert(tx, 'campaigns', 'campaign_id', await read('email_campaigns', 'campaign_id'), (r) => ({
        name: str(r.campaign_name) ?? 'Campaign', type: 'Email', subject: str(r.campaign_subject), body: txt(r.campaign_body),
        status: title(r.campaign_status, ['Draft', 'Scheduled', 'Active', 'Sent', 'Paused'], 'Draft'), send_date: day(r.campaign_sent_at ?? r.campaign_scheduled_at),
      }), 'campaigns');

      // ── Billing ──
      await upsert(tx, 'invoices', 'invoice_id', await read('invoices', 'invoice_id'), (r) => {
        const client_id = ref('clients', r.invoice_client_id); if (!client_id) return null;
        const st = String(r.invoice_status ?? '');
        return {
          number: str(r.invoice_number, 50), client_id, status: st === 'cancelled' || st === 'voided' ? 'Void' : title(st, ['Draft', 'Sent', 'Viewed', 'Partial', 'Paid', 'Overdue', 'Void'], 'Draft'),
          invoice_date: day(r.invoice_date) ?? '2000-01-01', due_date: day(r.invoice_due_date) ?? day(r.invoice_date) ?? '2000-01-01',
          tax_rate: num(r.invoice_tax_rate), subtotal: num(r.invoice_subtotal), tax_amount: num(r.invoice_tax_amount), total: num(r.invoice_total),
          amount_paid: num(r.invoice_amount_paid), scope: txt(r.invoice_scope), notes: txt(r.invoice_notes), created_at: ts(r.invoice_created_at) ?? new Date(),
        };
      });
      await lineItems(tx, 'invoice_items', 'invoice_id', 'invoices', await read('invoice_items', 'item_id'), 'item_invoice_id', (r) => ({
        description: str(r.item_description) ?? '—', qty: num(r.item_qty) ?? '1', rate: num(r.item_rate) ?? '0', taxable: bool(r.item_tax),
        line_total: num(r.item_total) ?? String(Number(r.item_qty ?? 1) * Number(r.item_rate ?? 0)), sort_order: int(r.item_sort_order) ?? 0,
      }));
      await upsert(tx, 'recurring', 'recurring_id', await read('recurring_invoices', 'recurring_id'), (r) => {
        const client_id = ref('clients', r.recurring_client_id); if (!client_id) return null;
        const f = String(r.recurring_frequency ?? 'monthly');
        return {
          name: (str(r.recurring_scope, 200) ?? 'Recurring invoice').split('\n')[0], client_id,
          frequency: /year|annual/.test(f) ? 'Year' : /quarter/.test(f) ? 'Quarter' : 'Month',
          next_run: day(r.recurring_next_date) ?? new Date().toISOString().slice(0, 10),
          status: /active/i.test(String(r.recurring_status ?? 'active')) ? 'Active' : 'Paused', tax_rate: num(r.recurring_tax_rate), total: num(r.recurring_subtotal), notes: txt(r.recurring_scope),
        };
      }, 'recurring');
      await lineItems(tx, 'recurring_items', 'recurring_id', 'recurring', await read('recurring_invoice_items', 'ri_item_id'), 'ri_recurring_id', (r) => ({
        description: str(r.ri_description) ?? '—', qty: num(r.ri_qty) ?? '1', rate: num(r.ri_rate) ?? '0', taxable: true,
        line_total: num(r.ri_total) ?? String(Number(r.ri_qty ?? 1) * Number(r.ri_rate ?? 0)), sort_order: int(r.ri_sort) ?? 0,
      }));
      await upsert(tx, 'quotes', 'quote_id', await read('quotes', 'quote_id'), (r) => {
        const client_id = ref('clients', r.quote_client_id); if (!client_id) return null;
        return {
          number: str(r.quote_number, 50), client_id, status: title(r.quote_status, ['Draft', 'Sent', 'Accepted', 'Declined', 'Invoiced'], 'Draft'),
          quote_date: day(r.quote_date) ?? '2000-01-01', expires_on: day(r.quote_expire_date), tax_rate: num(r.quote_tax_rate),
          subtotal: num(r.quote_subtotal), total: num(r.quote_total), scope: txt(r.quote_scope), notes: txt(r.quote_notes),
        };
      });
      await lineItems(tx, 'quote_items', 'quote_id', 'quotes', await read('quote_items', 'qi_id'), 'qi_quote_id', (r) => ({
        description: str(r.qi_description) ?? '—', qty: num(r.qi_quantity) ?? '1', rate: num(r.qi_rate) ?? '0', taxable: r.qi_taxable == null ? true : bool(r.qi_taxable),
        line_total: num(r.qi_amount) ?? '0', sort_order: int(r.qi_sort_order) ?? 0,
      }));
      await upsert(tx, 'contracts', 'contract_id', await read('contracts', 'contract_id'), (r) => {
        const client_id = ref('clients', r.contract_client_id); if (!client_id) return null;
        const st = String(r.contract_status ?? '');
        return {
          number: str(r.contract_number, 50), name: str(r.contract_name ?? r.contract_title) ?? 'Contract', client_id,
          type: title(r.contract_type, ['Managed', 'Break/fix', 'Project', 'BAA', 'NDA', 'Other'], 'Other'),
          status: st === 'voided' ? 'Cancelled' : title(st, ['Draft', 'Sent', 'Active', 'Expired', 'Cancelled'], 'Draft'),
          start_date: day(r.contract_start_date), end_date: day(r.contract_end_date), auto_renew: bool(r.contract_auto_renew),
          monthly_rate: num(r.contract_recurring_amount ?? r.contract_monthly_rate), included_hours: num(r.contract_included_hours),
          overage_rate: num(r.contract_overage_rate), scope: txt(r.contract_scope), terms: txt(r.contract_terms),
        };
      });
      await upsert(tx, 'policies', 'cp_id', await read('client_policies', 'cp_id'), (r) => ({
        name: str(r.cp_name) ?? 'Policy', client_id: ref('clients', r.cp_client_id), version: str(r.cp_version),
        status: r.cp_signed_at ? 'Current' : title(r.cp_status, ['Draft', 'Current', 'Review due', 'Retired'], 'Draft'), next_review: day(r.cp_review_date),
      }));
      const courses = new Map((await read('training_courses', 'tc_id')).map((c) => [String(c.tc_key ?? c.tc_id), String(c.tc_name)]));
      await upsert(tx, 'training', 'te_id', await read('training_enrollments', 'te_id'), (r) => {
        const client_id = ref('clients', r.te_client_id); if (!client_id) return null;
        let list: string[] = []; try { list = JSON.parse(String(r.te_courses ?? '[]')); } catch { list = String(r.te_courses ?? '').split(','); }
        return { course: list.map((k) => courses.get(String(k).trim()) ?? String(k).trim()).filter(Boolean).join(', ').slice(0, 500) || 'Security training', client_id, due_date: day(r.te_due_date), status: /complete/i.test(String(r.te_status)) ? 'Complete' : 'In progress' };
      });
      await upsert(tx, 'renewals', 'warranty_id', await read('warranties', 'warranty_id'), (r) => ({
        item: str(r.warranty_name) ?? 'Warranty', client_id: ref('clients', r.warranty_client_id),
        type: title(r.warranty_type, ['License', 'Domain', 'Warranty', 'Contract', 'Subscription', 'Other'], 'Warranty'),
        renews_on: day(r.warranty_end_date) ?? '2000-01-01', cost: num(r.warranty_cost), notes: txt(r.warranty_notes),
      }));
      const cats = new Map((await read('expense_categories', 'category_id')).map((c) => [Number(c.category_id), String(c.category_name)]));
      await upsert(tx, 'expenses', 'expense_id', await read('expenses', 'expense_id'), (r) => ({
        spent_on: day(r.expense_date) ?? '2000-01-01', vendor_id: ref('vendors', r.expense_vendor_id), category: cats.get(Number(r.expense_category_id)) ?? null,
        amount: num(r.expense_amount) ?? '0', client_id: ref('clients', r.expense_client_id), billable: !!r.expense_client_id, description: str(r.expense_description),
      }));
      await upsert(tx, 'banking', 'btxn_id', await read('bank_transactions', 'btxn_id'), (r) => ({
        posted_on: day(r.btxn_date) ?? '2000-01-01', description: str(r.btxn_description) ?? '—', amount: num(r.btxn_amount) ?? '0',
        match_status: r.btxn_matched_invoice_id || r.btxn_expense_id ? 'Matched' : r.btxn_status === 'ignored' ? 'Ignored' : 'Unmatched',
        invoice_id: ref('invoices', r.btxn_matched_invoice_id), notes: str(r.btxn_match_note),
      }), 'bank transactions');

      // ── Tools ──
      await upsert(tx, 'calendar', 'event_id', await read('calendar_events', 'event_id'), (r) => {
        const starts = ts(r.event_start); if (!starts) return null;
        return { title: str(r.event_title) ?? 'Event', starts_at: starts, ends_at: ts(r.event_end), client_id: ref('clients', r.event_client_id), notes: txt(r.event_description) };
      }, 'calendar');
      await upsert(tx, 'inventory', 'inv_id', await read('inventory_items', 'inv_id'), (r) => ({
        name: str(r.inv_name) ?? 'Item', sku: str(r.inv_sku), on_hand: int(r.inv_qty_on_hand), reorder_at: int(r.inv_reorder_point),
        cost: num(r.inv_unit_cost), price: num(r.inv_unit_price), location: str(r.inv_location), notes: txt(r.inv_notes ?? r.inv_description),
        archived_at: bool(r.inv_archived) ? new Date() : null,
      }));
      await upsert(tx, 'mileage', 'mile_id', await read('hr_mileage', 'mile_id'), (r) => ({
        trip_date: day(r.mile_date) ?? '2000-01-01', trip: [r.mile_from, r.mile_to].filter(Boolean).join(' → ').slice(0, 500) || str(r.mile_purpose) || 'Trip',
        miles: num(r.mile_distance) ?? '0', client_id: ref('clients', r.mile_client_id), billable: !!r.mile_client_id, user_id: ref('users', r.mile_user_id),
      }));
      await upsert(tx, 'messages', 'msg_id', await read('secure_messages', 'msg_id'), (r) => {
        const client_id = ref('clients', r.msg_client_id); if (!client_id) return null;
        return {
          client_id, subject: str(r.msg_subject) ?? '(no subject)', direction: r.msg_direction === 'inbound' ? 'Inbound' : 'Outbound',
          status: bool(r.msg_archived) ? 'Archived' : bool(r.msg_read) ? 'Read' : 'Unread', body: r.msg_body ? encrypt(String(r.msg_body)) : null,
          created_at: ts(r.msg_created_at) ?? new Date(),
        };
      }, 'secure messages');
      const certs = await read('certificates', 'cert_id');
      await upsert(tx, 'domains', 'domain_id', await read('domains', 'domain_id'), (r) => {
        const c = certs.find((x) => String(x.cert_domain ?? '').toLowerCase() === String(r.domain_name ?? '').toLowerCase());
        const sslExp = day(c?.cert_live_expiry ?? c?.cert_expire_date);
        const sslStatus = !c ? 'Unknown' : !sslExp ? 'Unknown' : sslExp < new Date().toISOString().slice(0, 10) ? 'Expired' : sslExp < new Date(Date.now() + 30 * 86400_000).toISOString().slice(0, 10) ? 'Expiring' : 'Valid';
        return { name: str(r.domain_name, 500) ?? 'domain', client_id: ref('clients', r.domain_client_id), registrar: str(r.domain_registrar), expires_on: day(r.domain_whois_expiry ?? r.domain_expire_date), dns_provider: str(r.domain_dns_provider), ssl_status: sslStatus, ssl_expires_on: sslExp, notes: txt(r.domain_notes) };
      });
      const kbc = new Map((await read('kb_categories', 'kbc_id')).map((c) => [Number(c.kbc_id), String(c.kbc_name)]));
      await upsert(tx, 'kb', 'kb_id', await read('kb_articles', 'kb_id'), (r) => ({
        title: str(r.kb_title) ?? 'Article', category: kbc.get(Number(r.kb_category_id)) ?? null, visibility: bool(r.kb_portal_visible) ? 'Portal' : 'Staff only',
        views: int(r.kb_views) ?? 0, body: txt(r.kb_content), archived_at: bool(r.kb_archived) ? new Date() : null,
      }), 'knowledge base');
      await upsert(tx, 'workflows', 'wr_id', await read('workflow_rules', 'wr_id'), (r) => ({
        name: str(r.wr_name) ?? 'Workflow', trigger: 'Ticket created', action: 'Send email',
        conditions: [`Imported from old workflow (trigger: ${r.wr_trigger ?? '?'})`, txt(r.wr_conditions), txt(r.wr_actions)].filter(Boolean).join('\n'),
        status: 'Paused', runs: int(r.wr_run_count) ?? 0,
      }));

      // ── H/R ──
      await upsert(tx, 'employees', 'emp_id', await read('hr_employees', 'emp_id'), (r, w) => {
        const dec = (col: string, what: string) => (r[col] ? secretOrWarn(() => decryptValue(String(r[col]), o.encryptionKey), w, what) : null);
        return {
          name: [r.emp_first_name, r.emp_last_name].filter(Boolean).join(' ') || 'Employee', user_id: ref('users', r.emp_user_id), title: str(r.emp_position),
          office: /phoenix/i.test(String(r.emp_city ?? r.emp_department ?? '')) ? 'Phoenix' : /el paso/i.test(String(r.emp_city ?? '')) ? 'El Paso' : null,
          status: title(r.emp_status, ['Active', 'Onboarding', 'On leave', 'Terminated'], 'Active'), hire_date: day(r.emp_hire_date), email: email(r.emp_email),
          phone: str(r.emp_phone), pay_type: r.emp_pay_type ? title(r.emp_pay_type, ['Hourly', 'Salary'], 'Hourly') : null, pto_balance_hours: num(r.emp_pto_balance),
          ssn: dec('emp_ssn_enc', 'SSN'), bank_routing: dec('emp_bank_routing_enc', 'bank routing'), bank_account: dec('emp_bank_account_enc', 'bank account'),
          emergency_contact: [r.emp_emergency_name, r.emp_emergency_phone, r.emp_emergency_relation].filter(Boolean).join(' · ') || null,
        };
      }, 'employees');
      const empUser = new Map((await read('hr_employees', 'emp_id')).map((e) => [Number(e.emp_id), ref('users', e.emp_user_id)]));
      const pto = [...(await read('hr_pto_requests', 'pto_id')).map((r) => ({ ...r, _uid: empUser.get(Number(r.pto_emp_id)) })), ...(await read('hr_pto', 'pto_id')).map((r) => ({ ...r, _uid: ref('users', r.pto_user_id), pto_id: 1_000_000 + Number(r.pto_id) }))];
      await upsert(tx, 'pto', 'pto_id', pto, (r) => {
        if (!r._uid) return null;
        return { user_id: r._uid, kind: title(r.pto_type, ['Vacation', 'Sick', 'Personal', 'Unpaid'], 'Vacation'), starts_on: day(r.pto_start_date) ?? '2000-01-01', ends_on: day(r.pto_end_date) ?? day(r.pto_start_date) ?? '2000-01-01', hours: num(r.pto_hours) ?? '0', status: title(r.pto_status, ['Pending', 'Approved', 'Denied'], 'Pending'), reason: str(r.pto_notes ?? r.pto_reason) };
      }, 'time off');
      await upsert(tx, 'timeclock', 'tc_id', await read('hr_timeclock', 'tc_id'), (r) => {
        const uid = ref('users', r.tc_user_id) ?? empUser.get(Number(r.tc_employee_id)); const inAt = ts(r.tc_clock_in);
        if (!uid || !inAt) return null;
        return { user_id: uid, clock_in: inAt, clock_out: ts(r.tc_clock_out), status: bool(r.tc_approved) ? 'Approved' : r.tc_clock_out ? 'Submitted' : 'Open', notes: str(r.tc_notes) };
      }, 'timeclock');

      // ── Tickets (numbers kept) ──
      {
        const rows = await read('tickets', 'ticket_id');
        const step: Step = { name: 'tickets', source: rows.length, imported: 0, skipped: 0, warnings: [] };
        idMap.tickets = new Map();
        let maxNum = 0;
        for (let i = 0; i < rows.length; i += 300) {
          const vals = rows.slice(i, i + 300).map((r) => {
            const number = str(r.ticket_number, 30) ?? `T-${r.ticket_id}`;
            const m = number.match(/(\d+)\s*$/); if (m) maxNum = Math.max(maxNum, Number(m[1]));
            const status = TICKET_STATUS[String(r.ticket_status ?? '').toLowerCase()] ?? 'Open';
            return {
              number, subject: str(r.ticket_subject, 255) ?? '(no subject)', details: txt(r.ticket_details) ?? '',
              client_id: ref('clients', r.ticket_client_id), contact_id: ref('contacts', r.ticket_contact_id),
              contact_name: str(r.ticket_contact_name, 150), contact_email: email(r.ticket_contact_email), assigned_to: ref('users', r.ticket_assigned_to),
              priority: title(r.ticket_priority, ['Critical', 'High', 'Medium', 'Low'], 'Medium'), status, category: str(r.ticket_category, 100),
              source: title(r.ticket_source, ['Manual', 'Email', 'Portal', 'Phone', 'Alert', 'Import'], 'Import'), billable: r.ticket_billable == null ? true : bool(r.ticket_billable),
              due_date: day(r.ticket_due_date), response_due_at: ts(r.ticket_sla_response_due), first_response_at: ts(r.ticket_first_response_at),
              resolved_at: ts(r.ticket_resolved_at), closed_at: ts(r.ticket_closed_at), sla_breached: bool(r.ticket_sla_breached),
              legacy_id: Number(r.ticket_id), created_at: ts(r.ticket_created_at) ?? new Date(), updated_at: ts(r.ticket_updated_at) ?? new Date(),
            };
          });
          const cols = Object.keys(vals[0]).filter((k) => k !== 'legacy_id');
          const res = await tx.insert(tickets).values(vals).onConflictDoUpdate({ target: tickets.legacy_id, set: Object.fromEntries(cols.map((k) => [k, sql.raw(`excluded."${k}"`)])) }).returning({ id: tickets.id, legacy_id: tickets.legacy_id });
          for (const x of res) idMap.tickets.set(x.legacy_id!, x.id);
          step.imported += res.length;
        }
        steps.push(step);
        log(`  ${'tickets'.padEnd(18)} ${String(step.imported).padStart(6)} of ${rows.length}`);
        if (maxNum) await bumpCounter(tx, 'ticket', maxNum);

        // Original request text becomes the first message (idempotent via a negative legacy id).
        const firsts = rows.filter((r) => String(r.ticket_details ?? '').trim()).map((r) => ({
          ticket_id: ref('tickets', r.ticket_id)!, kind: 'reply', body: String(r.ticket_details), author_name: str(r.ticket_contact_name, 200), via: 'import',
          legacy_id: -Number(r.ticket_id), created_at: ts(r.ticket_created_at) ?? new Date(),
        }));
        const replies = (await read('ticket_replies', 'reply_id')).filter((r) => ref('tickets', r.reply_ticket_id)).map((r) => ({
          ticket_id: ref('tickets', r.reply_ticket_id)!, kind: r.reply_type === 'note' || r.reply_type === 'work' ? 'note' : 'reply', body: String(r.reply_body ?? ''),
          author_user_id: ref('users', r.reply_user_id), author_name: null as string | null, via: String(r.reply_from ?? 'staff') === 'staff' ? 'web' : String(r.reply_from).slice(0, 20),
          legacy_id: Number(r.reply_id), created_at: ts(r.reply_created_at) ?? new Date(),
        }));
        const allMsgs = [...firsts, ...replies];
        for (let i = 0; i < allMsgs.length; i += 500) {
          await tx.insert(ticketMessages).values(allMsgs.slice(i, i + 500)).onConflictDoUpdate({ target: ticketMessages.legacy_id, set: { body: sql.raw('excluded."body"'), kind: sql.raw('excluded."kind"') } });
        }
        steps.push({ name: 'ticket messages', source: allMsgs.length, imported: allMsgs.length, skipped: 0, warnings: [] });
        log(`  ${'ticket messages'.padEnd(18)} ${String(allMsgs.length).padStart(6)}`);

        const tte = (await read('ticket_time_entries', 'tte_id')).filter((r) => ref('tickets', r.tte_ticket_id)).map((r) => ({
          ticket_id: ref('tickets', r.tte_ticket_id)!, user_id: ref('users', r.tte_user_id), minutes: Math.round(Number(r.tte_hours ?? 0) * 60),
          work_type: /site/i.test(String(r.tte_work_type)) ? 'On-site' : /phone/i.test(String(r.tte_work_type)) ? 'Phone' : /travel/i.test(String(r.tte_work_type)) ? 'Travel' : 'Remote',
          description: String(r.tte_description ?? ''), billable: bool(r.tte_billable), work_date: day(r.tte_date) ?? '2000-01-01',
          invoice_id: ref('invoices', r.tte_invoice_id), legacy_id: Number(r.tte_id),
        }));
        // Older tickets logged time on the reply itself.
        const replyTime = (await read('ticket_replies', 'reply_id')).filter((r) => Number(r.reply_time_spent) > 0 && ref('tickets', r.reply_ticket_id)).map((r) => ({
          ticket_id: ref('tickets', r.reply_ticket_id)!, user_id: ref('users', r.reply_user_id), minutes: Math.round(Number(r.reply_time_spent) * 60),
          work_type: 'Remote', description: String(r.reply_work_type ?? ''), billable: bool(r.reply_billable), work_date: day(r.reply_created_at) ?? '2000-01-01',
          invoice_id: ref('invoices', r.reply_invoice_id), legacy_id: 10_000_000 + Number(r.reply_id),
        }));
        const allTime = [...tte, ...replyTime].filter((x) => x.minutes > 0);
        for (let i = 0; i < allTime.length; i += 500) {
          await tx.insert(ticketTime).values(allTime.slice(i, i + 500)).onConflictDoUpdate({ target: ticketTime.legacy_id, set: { minutes: sql.raw('excluded."minutes"') } });
        }
        steps.push({ name: 'ticket time', source: allTime.length, imported: allTime.length, skipped: 0, warnings: [] });
        log(`  ${'ticket time'.padEnd(18)} ${String(allTime.length).padStart(6)}`);
      }

      // Keep number sequences ahead of imported numbers.
      for (const [res, key, name] of [['invoices', 'number', 'invoices'], ['quotes', 'number', 'quotes'], ['projects', 'number', 'projects'], ['contracts', 'number', 'contracts']] as const) {
        const t = resourceTables[res];
        const [{ m }] = await tx.select({ m: sql<number>`coalesce(max(nullif(regexp_replace(${t[key]}, '\\D', '', 'g'), '')::bigint), 0)` }).from(t);
        if (Number(m) > 0) await bumpCounter(tx, name, Number(m));
      }

      await audit(null, { action: 'import', entity: 'import', entityId: run.id, summary: `${o.dryRun ? 'Dry run' : 'Import'} from old Weststar One: ${steps.reduce((a, s) => a + s.imported, 0)} records` }, tx);
      if (o.dryRun) throw new DryRunDone();
    });
  } catch (e) {
    if (!(e instanceof DryRunDone)) {
      await db().update(importRuns).set({ finished_at: new Date(), error: String((e as Error).message ?? e), summary: steps as never }).where(eq(importRuns.id, run.id));
      await src.end();
      throw e;
    }
  }
  await db().update(importRuns).set({ finished_at: new Date(), summary: steps as never }).where(eq(importRuns.id, run.id));
  await src.end();
  return { runId: run.id, dryRun: !!o.dryRun, steps };
}

class DryRunDone extends Error { constructor() { super('dry run'); } }
