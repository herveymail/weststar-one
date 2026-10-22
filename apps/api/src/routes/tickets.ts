import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { and, asc, count, desc, eq, ilike, inArray, isNull, lt, notInArray, or, sql, type SQL } from 'drizzle-orm';
import {
  DEFAULT_RESPONSE_MINUTES, OPEN_STATUSES, PAUSED_STATUSES, TICKET_STATUSES,
  ticketCreateSchema, ticketMessageSchema, ticketUpdateSchema, timeEntrySchema, type TicketPriority,
} from '@ws/shared';
import { db, type Tx } from '../db';
import { clients, contacts, ticketMessages, tickets, ticketTime, users } from '../db/schema';
import { audit, bad, getSetting, nextNumber, notFound } from '../lib/util';
import { requireLevel } from '../auth/session';

const OPEN = OPEN_STATUSES as readonly string[];
const escapeLike = (s: string) => s.replace(/[\\%_]/g, (c) => '\\' + c);

async function responseMinutes(priority: TicketPriority, clientId: number | null | undefined, tx: Tx | ReturnType<typeof db>) {
  if (clientId) {
    const [c] = await tx.select({ h: clients.sla_response_hours }).from(clients).where(eq(clients.id, clientId));
    // A client's own SLA only tightens Critical/High; Medium/Low keep the defaults.
    if (c?.h && (priority === 'Critical' || priority === 'High')) return Math.min(Number(c.h) * 60, DEFAULT_RESPONSE_MINUTES[priority]);
  }
  const key = `tickets.sla_${priority.toLowerCase()}_min`;
  const v = parseInt(await getSetting(key, ''), 10);
  return Number.isFinite(v) && v > 0 ? v : DEFAULT_RESPONSE_MINUTES[priority];
}

function slaState(t: typeof tickets.$inferSelect) {
  if (!OPEN.includes(t.status)) return 'done';
  if ((PAUSED_STATUSES as readonly string[]).includes(t.status)) return 'paused';
  if (t.first_response_at || !t.response_due_at) return 'ok';
  const left = t.response_due_at.getTime() - Date.now();
  if (left < 0) return 'breached';
  if (left < 60 * 60_000) return 'risk';
  return 'ok';
}

async function decorate(rows: (typeof tickets.$inferSelect)[]) {
  const clientIds = [...new Set(rows.map((r) => r.client_id).filter((x): x is number => !!x))];
  const userIds = [...new Set(rows.map((r) => r.assigned_to).filter((x): x is number => !!x))];
  const [cl, us] = await Promise.all([
    clientIds.length ? db().select({ id: clients.id, name: clients.name }).from(clients).where(inArray(clients.id, clientIds)) : [],
    userIds.length ? db().select({ id: users.id, name: users.name }).from(users).where(inArray(users.id, userIds)) : [],
  ]);
  const cn = new Map(cl.map((c: any) => [c.id, c.name])), un = new Map(us.map((u) => [u.id, u.name]));
  return rows.map((r) => ({ ...r, client_name: r.client_id ? cn.get(r.client_id) ?? null : null, assignee_name: r.assigned_to ? un.get(r.assigned_to) ?? null : null, sla: slaState(r) }));
}

const riskCond = () => and(
  inArray(tickets.status, OPEN.filter((s) => !(PAUSED_STATUSES as readonly string[]).includes(s))),
  isNull(tickets.first_response_at),
  lt(tickets.response_due_at, new Date(Date.now() + 60 * 60_000)),
);

async function addEvent(tx: Tx, ticketId: number, text: string, userId: number | null, name: string | null) {
  await tx.insert(ticketMessages).values({ ticket_id: ticketId, kind: 'event', body: text, author_user_id: userId, author_name: name, via: 'web' });
}

export async function ticketRoutes(app: FastifyInstance) {
  app.get('/api/tickets', async (req) => {
    const u = requireLevel(req, 'tickets', 'view');
    const q = z.object({
      view: z.enum(['inbox', 'queue']).default('inbox'),
      filter: z.enum(['open', 'unassigned', 'risk', 'all', 'closed']).default('open'),
      q: z.string().max(200).optional(), client_id: z.coerce.number().int().positive().optional(),
      page: z.coerce.number().int().min(1).default(1), limit: z.coerce.number().int().min(1).max(200).default(50),
    }).parse(req.query);
    const base: (SQL | undefined)[] = [];
    if (q.view === 'queue') base.push(eq(tickets.assigned_to, u.id));
    if (q.client_id) base.push(eq(tickets.client_id, q.client_id));
    if (q.q) {
      const like = `%${escapeLike(q.q)}%`;
      base.push(or(ilike(tickets.subject, like), ilike(tickets.number, like), ilike(tickets.contact_name, like), ilike(tickets.contact_email, like)));
    }
    const F: Record<string, SQL | undefined> = {
      open: inArray(tickets.status, [...OPEN]),
      unassigned: and(inArray(tickets.status, [...OPEN]), isNull(tickets.assigned_to)),
      risk: riskCond(),
      all: undefined,
      closed: notInArray(tickets.status, [...OPEN]),
    };
    const where = and(...base.filter(Boolean), F[q.filter]);
    const prioOrder = sql`CASE ${tickets.priority} WHEN 'Critical' THEN 0 WHEN 'High' THEN 1 WHEN 'Medium' THEN 2 ELSE 3 END`;
    const rows = await db().select().from(tickets).where(where)
      .orderBy(asc(sql`CASE WHEN ${tickets.status} IN ('Resolved','Closed') THEN 1 ELSE 0 END`), asc(prioOrder), desc(tickets.updated_at))
      .limit(q.limit).offset((q.page - 1) * q.limit);
    const countsRows = await Promise.all(Object.entries(F).map(async ([k, c]) => {
      const [{ n }] = await db().select({ n: count() }).from(tickets).where(and(...base.filter(Boolean), c));
      return [k, Number(n)] as const;
    }));
    return { rows: await decorate(rows), counts: Object.fromEntries(countsRows) };
  });

  app.get('/api/tickets/board', async (req) => {
    requireLevel(req, 'tickets', 'view');
    const { q } = z.object({ q: z.string().max(200).optional() }).parse(req.query);
    const s = q ? or(ilike(tickets.subject, `%${escapeLike(q)}%`), ilike(tickets.number, `%${escapeLike(q)}%`)) : undefined;
    const open = await db().select().from(tickets).where(and(inArray(tickets.status, [...OPEN]), s)).orderBy(desc(tickets.updated_at)).limit(500);
    const done = await db().select().from(tickets).where(and(notInArray(tickets.status, [...OPEN]), s)).orderBy(desc(tickets.updated_at)).limit(25);
    return { rows: await decorate([...open, ...done]) };
  });

  app.get('/api/tickets/:id', async (req) => {
    requireLevel(req, 'tickets', 'view');
    const { id } = z.object({ id: z.coerce.number().int().positive() }).parse(req.params);
    const [t] = await db().select().from(tickets).where(eq(tickets.id, id));
    if (!t) throw notFound('Ticket not found');
    const [msgs, time, client] = await Promise.all([
      db().select({ m: ticketMessages, user_name: users.name }).from(ticketMessages).leftJoin(users, eq(users.id, ticketMessages.author_user_id))
        .where(eq(ticketMessages.ticket_id, id)).orderBy(asc(ticketMessages.created_at), asc(ticketMessages.id))
        .then((rows) => rows.map((r) => ({ ...r.m, author_name: r.m.author_name ?? r.user_name ?? null }))),
      db().select({ e: ticketTime, user_name: users.name }).from(ticketTime).leftJoin(users, eq(users.id, ticketTime.user_id)).where(eq(ticketTime.ticket_id, id)).orderBy(asc(ticketTime.created_at)),
      t.client_id ? db().select({ id: clients.id, name: clients.name, plan: clients.plan, account_alert: clients.account_alert, phone: clients.phone }).from(clients).where(eq(clients.id, t.client_id)).then((r) => r[0] ?? null) : null,
    ]);
    const [deco] = await decorate([t]);
    return { ticket: deco, messages: msgs, time: time.map((x) => ({ ...x.e, user_name: x.user_name })), client, minutes: time.reduce((a, x) => a + x.e.minutes, 0) };
  });

  app.post('/api/tickets', async (req) => {
    const u = requireLevel(req, 'tickets', 'edit');
    const b = ticketCreateSchema.parse(req.body);
    if (b.contact_id && b.client_id) {
      const [c] = await db().select({ client_id: contacts.client_id }).from(contacts).where(eq(contacts.id, b.contact_id));
      if (!c || c.client_id !== b.client_id) throw bad('That contact does not belong to the chosen client.');
    }
    const row = await db().transaction(async (tx) => {
      const prefix = (await getSetting('numbers.ticket_prefix', 'T-')) || 'T-';
      const number = prefix + (await nextNumber(tx, 'ticket', 10001));
      const minutes = await responseMinutes(b.priority, b.client_id, tx);
      let contactName = b.contact_name ?? null, contactEmail = b.contact_email ?? null;
      if (b.contact_id) {
        const [c] = await tx.select({ name: contacts.name, email: contacts.email }).from(contacts).where(eq(contacts.id, b.contact_id));
        contactName = c?.name ?? contactName; contactEmail = (c?.email as string | null) ?? contactEmail;
      }
      const [t] = await tx.insert(tickets).values({
        number, subject: b.subject, details: b.details ?? '', client_id: b.client_id ?? null, contact_id: b.contact_id ?? null,
        contact_name: contactName, contact_email: contactEmail, priority: b.priority, status: 'New', category: b.category ?? null,
        source: b.source, billable: b.billable, assigned_to: b.assigned_to ?? null, created_by: u.id,
        response_due_at: new Date(Date.now() + minutes * 60_000),
      }).returning();
      if (b.details?.trim()) await tx.insert(ticketMessages).values({ ticket_id: t.id, kind: 'reply', body: b.details, author_name: contactName ?? u.name, via: b.source === 'Manual' ? 'web' : b.source.toLowerCase() });
      await addEvent(tx, t.id, `Created by ${u.name}`, u.id, u.name);
      await audit(req, { action: 'create', entity: 'ticket', entityId: t.id, summary: `Created ticket ${number}: ${b.subject}` }, tx);
      return t;
    });
    return { ticket: row };
  });

  app.patch('/api/tickets/:id', async (req) => {
    const u = requireLevel(req, 'tickets', 'edit');
    const { id } = z.object({ id: z.coerce.number().int().positive() }).parse(req.params);
    const b = ticketUpdateSchema.parse(req.body);
    const out = await db().transaction(async (tx) => {
      const [before] = await tx.select().from(tickets).where(eq(tickets.id, id)).for('update');
      if (!before) throw notFound('Ticket not found');
      const set: Partial<typeof tickets.$inferInsert> = { updated_at: new Date() };
      const events: string[] = [];
      if (b.subject !== undefined && b.subject !== before.subject) set.subject = b.subject;
      if (b.category !== undefined) set.category = b.category;
      if (b.billable !== undefined) set.billable = b.billable;
      if (b.due_date !== undefined) set.due_date = b.due_date;
      if (b.client_id !== undefined && b.client_id !== before.client_id) { set.client_id = b.client_id; events.push('Client changed'); }
      if (b.contact_id !== undefined) set.contact_id = b.contact_id;
      if (b.priority && b.priority !== before.priority) {
        set.priority = b.priority; events.push(`Priority ${before.priority} → ${b.priority}`);
        if (!before.first_response_at) set.response_due_at = new Date(before.created_at.getTime() + (await responseMinutes(b.priority, before.client_id, tx)) * 60_000);
      }
      if (b.assigned_to !== undefined && b.assigned_to !== before.assigned_to) {
        if (b.assigned_to) {
          const [a] = await tx.select({ name: users.name }).from(users).where(and(eq(users.id, b.assigned_to), isNull(users.archived_at)));
          if (!a) throw bad('That person cannot be assigned.');
          events.push(`Assigned to ${a.name}`);
        } else events.push('Unassigned');
        set.assigned_to = b.assigned_to;
      }
      if (b.status && b.status !== before.status) {
        if (!(TICKET_STATUSES as readonly string[]).includes(b.status)) throw bad('Unknown status');
        set.status = b.status; events.push(`Status ${before.status} → ${b.status}`);
        if (b.status === 'Resolved') set.resolved_at = new Date();
        if (b.status === 'Closed') { set.closed_at = new Date(); set.resolved_at = before.resolved_at ?? new Date(); }
        if (OPEN.includes(b.status)) { set.closed_at = null; set.resolved_at = null; }
      }
      const [t] = await tx.update(tickets).set(set).where(eq(tickets.id, id)).returning();
      for (const e of events) await addEvent(tx, id, `${e} by ${u.name}`, u.id, u.name);
      await audit(req, { action: 'update', entity: 'ticket', entityId: id, summary: `${before.number}: ${events.join('; ') || 'updated'}`, changes: b }, tx);
      return t;
    });
    return { ticket: (await decorate([out]))[0] };
  });

  app.post('/api/tickets/:id/messages', async (req) => {
    const u = requireLevel(req, 'tickets', 'edit');
    const { id } = z.object({ id: z.coerce.number().int().positive() }).parse(req.params);
    const b = ticketMessageSchema.parse(req.body);
    const msg = await db().transaction(async (tx) => {
      const [t] = await tx.select().from(tickets).where(eq(tickets.id, id)).for('update');
      if (!t) throw notFound('Ticket not found');
      const [m] = await tx.insert(ticketMessages).values({ ticket_id: id, kind: b.kind, body: b.body, author_user_id: u.id, author_name: u.name, via: 'web' }).returning();
      const set: Partial<typeof tickets.$inferInsert> = { updated_at: new Date() };
      if (b.kind === 'reply') {
        if (!t.first_response_at) set.first_response_at = new Date();
        if (t.status === 'New') set.status = 'Open';
      }
      if (!t.assigned_to) { set.assigned_to = u.id; await addEvent(tx, id, `Assigned to ${u.name}`, u.id, u.name); }
      await tx.update(tickets).set(set).where(eq(tickets.id, id));
      if (b.minutes > 0) {
        await tx.insert(ticketTime).values({ ticket_id: id, user_id: u.id, minutes: b.minutes, billable: b.billable, description: b.body.slice(0, 500), work_date: new Date().toISOString().slice(0, 10) });
      }
      await audit(req, { action: b.kind === 'reply' ? 'reply' : 'note', entity: 'ticket', entityId: id, summary: `${b.kind === 'reply' ? 'Replied on' : 'Added note to'} ${t.number}` }, tx);
      return m;
    });
    return { message: msg };
  });

  app.post('/api/tickets/:id/time', async (req) => {
    const u = requireLevel(req, 'tickets', 'edit');
    const { id } = z.object({ id: z.coerce.number().int().positive() }).parse(req.params);
    const b = timeEntrySchema.parse(req.body);
    const entry = await db().transaction(async (tx) => {
      const [t] = await tx.select({ id: tickets.id, number: tickets.number }).from(tickets).where(eq(tickets.id, id));
      if (!t) throw notFound('Ticket not found');
      const [e] = await tx.insert(ticketTime).values({ ticket_id: id, user_id: u.id, minutes: b.minutes, work_type: b.work_type, description: b.description, billable: b.billable, work_date: b.date ?? new Date().toISOString().slice(0, 10) }).returning();
      await addEvent(tx, id, `${u.name} logged ${b.minutes} min${b.billable ? ' · billable' : ''}`, u.id, u.name);
      await tx.update(tickets).set({ updated_at: new Date() }).where(eq(tickets.id, id));
      await audit(req, { action: 'time', entity: 'ticket', entityId: id, summary: `Logged ${b.minutes} min on ${t.number}` }, tx);
      return e;
    });
    return { entry };
  });
}
