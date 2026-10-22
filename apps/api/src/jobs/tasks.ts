import { and, eq, inArray, isNull, lt, lte, or } from 'drizzle-orm';
import { OPEN_STATUSES, PAUSED_STATUSES } from '@ws/shared';
import { db } from '../db';
import { clients, invoices, invoice_items, recurring, recurring_items, sessions, ticketMessages, tickets, loginAttempts } from '../db/schema';
import { audit, nextNumber, getSetting } from '../lib/util';

const today = () => new Date().toISOString().slice(0, 10);
const addDays = (d: string, n: number) => { const x = new Date(d + 'T00:00:00Z'); x.setUTCDate(x.getUTCDate() + n); return x.toISOString().slice(0, 10); };
const addMonths = (d: string, n: number) => { const x = new Date(d + 'T00:00:00Z'); const day = x.getUTCDate(); x.setUTCDate(1); x.setUTCMonth(x.getUTCMonth() + n); const last = new Date(Date.UTC(x.getUTCFullYear(), x.getUTCMonth() + 1, 0)).getUTCDate(); x.setUTCDate(Math.min(day, last)); return x.toISOString().slice(0, 10); };

/** Mark tickets whose first-response deadline has passed. */
export async function slaWatch() {
  const active = (OPEN_STATUSES as readonly string[]).filter((s) => !(PAUSED_STATUSES as readonly string[]).includes(s));
  const rows = await db().update(tickets).set({ sla_breached: true })
    .where(and(inArray(tickets.status, active), isNull(tickets.first_response_at), lt(tickets.response_due_at, new Date()), eq(tickets.sla_breached, false)))
    .returning({ id: tickets.id, number: tickets.number });
  for (const r of rows) await db().insert(ticketMessages).values({ ticket_id: r.id, kind: 'event', body: 'Response SLA missed', via: 'system' });
  return { breached: rows.length };
}

/** Create invoices from recurring schedules that are due. Each schedule is locked while it is processed. */
export async function runRecurring() {
  let created = 0;
  const due = await db().select({ id: recurring.id }).from(recurring)
    .where(and(eq(recurring.status, 'Active'), isNull(recurring.archived_at), lte(recurring.next_run, today())));
  for (const { id } of due) {
    await db().transaction(async (tx) => {
      const [s] = await tx.select().from(recurring).where(and(eq(recurring.id, id), lte(recurring.next_run, today()))).for('update', { skipLocked: true });
      if (!s) return;
      const [c] = await tx.select({ net: clients.net_terms }).from(clients).where(eq(clients.id, s.client_id));
      const items = await tx.select().from(recurring_items).where(eq(recurring_items.recurring_id, id));
      const number = 'INV-' + (await nextNumber(tx, 'invoices', 1001));
      const runDate = s.next_run as string;
      const taxRate = Number(s.tax_rate ?? 0);
      let subtotal = 0, taxable = 0;
      for (const it of items) { const l = Number(it.line_total ?? 0); subtotal += l; if (it.taxable) taxable += l; }
      const tax = Math.round(taxable * taxRate) / 100;
      const [inv] = await tx.insert(invoices).values({
        number, client_id: s.client_id, status: 'Draft', invoice_date: runDate, due_date: addDays(runDate, Number(c?.net ?? 30)),
        tax_rate: String(taxRate), subtotal: subtotal.toFixed(2), tax_amount: tax.toFixed(2), total: (subtotal + tax).toFixed(2),
        scope: `${s.name} — ${runDate}`, notes: s.notes,
      }).returning();
      if (items.length) await tx.insert(invoice_items).values(items.map((it: any, i: number) => ({ invoice_id: inv.id, description: it.description, qty: it.qty, rate: it.rate, taxable: it.taxable, line_total: it.line_total, sort_order: i })));
      const step = s.frequency === 'Year' ? 12 : s.frequency === 'Quarter' ? 3 : 1;
      await tx.update(recurring).set({ next_run: addMonths(runDate, step), updated_at: new Date() }).where(eq(recurring.id, id));
      await audit(null, { action: 'create', entity: 'invoices', entityId: inv.id, summary: `Recurring schedule "${s.name}" created ${number}` }, tx);
      created++;
    });
  }
  return { created };
}

/** Sent invoices past their due date become Overdue. */
export async function markOverdue() {
  const rows = await db().update(invoices).set({ status: 'Overdue', updated_at: new Date() })
    .where(and(inArray(invoices.status, ['Sent', 'Viewed', 'Partial']), lt(invoices.due_date, today()), isNull(invoices.archived_at)))
    .returning({ id: invoices.id });
  return { overdue: rows.length };
}

/** Close resolved tickets after N days (setting tickets.auto_close_days, 0 = never). */
export async function autoClose() {
  const days = parseInt(await getSetting('tickets.auto_close_days', '7'), 10);
  if (!days || days < 1) return { closed: 0 };
  const rows = await db().update(tickets).set({ status: 'Closed', closed_at: new Date() })
    .where(and(eq(tickets.status, 'Resolved'), lt(tickets.resolved_at, new Date(Date.now() - days * 86400_000)))).returning({ id: tickets.id });
  for (const r of rows) await db().insert(ticketMessages).values({ ticket_id: r.id, kind: 'event', body: `Closed automatically after ${days} days resolved`, via: 'system' });
  return { closed: rows.length };
}

/** Drop expired sessions and old sign-in attempts. */
export async function cleanup() {
  const s = await db().delete(sessions).where(or(lt(sessions.expires_at, new Date()), lt(sessions.revoked_at, new Date(Date.now() - 7 * 86400_000)))).returning({ id: sessions.id });
  const a = await db().delete(loginAttempts).where(lt(loginAttempts.created_at, new Date(Date.now() - 90 * 86400_000))).returning({ id: loginAttempts.id });
  return { sessions: s.length, attempts: a.length };
}

export const TASKS = {
  'sla-watch': { cron: '*/5 * * * *', run: slaWatch, label: 'SLA watch (every 5 minutes)' },
  'recurring-invoices': { cron: '15 6 * * *', run: runRecurring, label: 'Recurring invoices (daily 6:15)' },
  'overdue-invoices': { cron: '30 6 * * *', run: markOverdue, label: 'Mark overdue invoices (daily 6:30)' },
  'auto-close': { cron: '0 * * * *', run: autoClose, label: 'Auto-close resolved tickets (hourly)' },
  'cleanup': { cron: '0 3 * * *', run: cleanup, label: 'Clean up old sessions and sign-in records (daily 3:00)' },
} as const;
