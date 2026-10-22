import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { and, asc, count, desc, eq, gte, ilike, inArray, isNull, lt, or, sql } from 'drizzle-orm';
import { ALL_SETTING_FIELDS, OPEN_STATUSES, ROLES, SECRET_SETTING_KEYS, passwordRule } from '@ws/shared';
import { db } from '../db';
import { auditLog, invoices, loginAttempts, mfaRecoveryCodes, resourceTables, settings, tickets, users, importRuns } from '../db/schema';
import { hashPassword } from '../lib/passwords';
import { audit, bad, forbidden, getSetting, HttpError, notFound, setSetting } from '../lib/util';
import { levelOf, requireLevel, requireUser, revokeAllSessions } from '../auth/session';
import { publicUser } from '../auth/routes';

const escapeLike = (s: string) => s.replace(/[\\%_]/g, (c) => '\\' + c);

export async function adminRoutes(app: FastifyInstance) {
  // ───────── Staff users (admin only) ─────────
  app.get('/api/users', async (req) => {
    requireLevel(req, 'admin', 'view');
    const rows = await db().select().from(users).orderBy(asc(users.archived_at), asc(users.name));
    return rows.map(publicUser).map((u, i) => ({ ...u, archived: !!rows[i].archived_at, locked: !!rows[i].locked_until && rows[i].locked_until! > new Date() }));
  });

  const userBody = z.object({
    name: z.string().trim().min(1).max(200), email: z.string().trim().toLowerCase().email().max(254),
    role: z.enum(ROLES), hr_access: z.boolean().default(false), title: z.string().max(100).nullable().optional(),
    phone: z.string().max(50).nullable().optional(),
  }).strict();

  app.post('/api/users', async (req) => {
    requireLevel(req, 'admin', 'manage');
    const b = userBody.extend({ password: passwordRule }).parse(req.body);
    const exists = await db().select({ id: users.id }).from(users).where(sql`lower(${users.email}) = ${b.email}`);
    if (exists.length) throw bad('Someone already uses that email address.');
    const [u] = await db().insert(users).values({ ...b, password_hash: await hashPassword(b.password), must_change_password: true }).returning();
    await audit(req, { action: 'create', entity: 'user', entityId: u.id, summary: `Added user ${u.email} (${u.role})` });
    return publicUser(u);
  });

  app.patch('/api/users/:id', async (req) => {
    const me = requireLevel(req, 'admin', 'manage');
    const { id } = z.object({ id: z.coerce.number().int().positive() }).parse(req.params);
    const b = userBody.partial().parse(req.body);
    if (id === me.id && b.role && b.role !== 'admin') throw bad('You cannot remove your own admin role.');
    if (b.email) {
      const clash = await db().select({ id: users.id }).from(users).where(and(sql`lower(${users.email}) = ${b.email}`, sql`${users.id} <> ${id}`));
      if (clash.length) throw bad('Someone already uses that email address.');
    }
    const [u] = await db().update(users).set({ ...b, updated_at: new Date() }).where(eq(users.id, id)).returning();
    if (!u) throw notFound();
    if (b.role || b.hr_access !== undefined) await revokeAllSessions(id); // permissions changed: sign them in again
    await audit(req, { action: 'update', entity: 'user', entityId: id, summary: `Updated user ${u.email}`, changes: b });
    return publicUser(u);
  });

  app.post('/api/users/:id/:action', async (req) => {
    const me = requireLevel(req, 'admin', 'manage');
    const { id, action } = z.object({ id: z.coerce.number().int().positive(), action: z.enum(['reset-password', 'reset-mfa', 'unlock', 'archive', 'restore', 'sign-out']) }).parse(req.params);
    const [u] = await db().select().from(users).where(eq(users.id, id));
    if (!u) throw notFound();
    if (id === me.id && (action === 'archive' || action === 'reset-mfa')) throw bad('Use your own security page for that.');
    let result: Record<string, unknown> = { ok: true };
    switch (action) {
      case 'reset-password': {
        const { password } = z.object({ password: passwordRule }).parse(req.body);
        await db().update(users).set({ password_hash: await hashPassword(password), must_change_password: true, failed_logins: 0, locked_until: null }).where(eq(users.id, id));
        await revokeAllSessions(id); break;
      }
      case 'reset-mfa':
        await db().update(users).set({ mfa_enabled: false, totp_secret_enc: null, totp_pending_enc: null, totp_last_step: null }).where(eq(users.id, id));
        await db().delete(mfaRecoveryCodes).where(eq(mfaRecoveryCodes.user_id, id));
        await revokeAllSessions(id); break;
      case 'unlock': await db().update(users).set({ failed_logins: 0, locked_until: null }).where(eq(users.id, id)); break;
      case 'archive': await db().update(users).set({ archived_at: new Date() }).where(eq(users.id, id)); await revokeAllSessions(id); break;
      case 'restore': await db().update(users).set({ archived_at: null }).where(eq(users.id, id)); break;
      case 'sign-out': await revokeAllSessions(id); break;
    }
    await audit(req, { action: `user_${action.replace('-', '_')}`, entity: 'user', entityId: id, summary: `${action.replace('-', ' ')} for ${u.email}` });
    return result;
  });

  // ───────── Settings ─────────
  app.get('/api/settings', async (req) => {
    requireLevel(req, 'admin', 'view');
    const rows = await db().select().from(settings);
    const out: Record<string, string | { set: boolean }> = {};
    for (const r of rows) out[r.key] = r.is_secret ? { set: r.value !== '' } : r.value;
    return out;
  });

  app.put('/api/settings', async (req) => {
    const u = requireLevel(req, 'admin', 'manage');
    const body = z.record(z.string().max(120), z.union([z.string().max(20000), z.boolean(), z.number()])).parse(req.body);
    const known = new Map(ALL_SETTING_FIELDS.map((f) => [f.key, f]));
    const changed: string[] = [];
    await db().transaction(async (tx) => {
      for (const [k, raw] of Object.entries(body)) {
        const f = known.get(k);
        if (!f) throw bad(`Unknown setting ${k}`);
        let v = String(raw);
        if (f.type === 'int' && v !== '' && !/^-?\d+$/.test(v)) throw bad(`${f.label} must be a whole number`);
        if (f.type === 'select' && v !== '' && !f.options!.includes(v)) throw bad(`${f.label}: pick one of the options`);
        if (f.type === 'bool') v = v === 'true' ? 'true' : 'false';
        const secret = SECRET_SETTING_KEYS.has(k);
        if (secret && v === '') continue; // blank secret = keep the saved one
        await setSetting(k, v, secret, u.id, tx);
        changed.push(k);
      }
      await audit(req, { action: 'settings', entity: 'settings', summary: `Changed ${changed.join(', ')}`, changes: Object.fromEntries(changed.map((k) => [k, SECRET_SETTING_KEYS.has(k) ? '[secret changed]' : body[k]])) }, tx);
    });
    return { ok: true, changed };
  });

  // ───────── Audit + security logs ─────────
  app.get('/api/audit', async (req) => {
    requireLevel(req, 'admin', 'view');
    const q = z.object({ q: z.string().max(200).optional(), entity: z.string().max(60).optional(), page: z.coerce.number().int().min(1).default(1) }).parse(req.query);
    const conds = [q.entity ? eq(auditLog.entity, q.entity) : undefined, q.q ? ilike(auditLog.summary, `%${escapeLike(q.q)}%`) : undefined].filter(Boolean);
    const rows = await db().select({ a: auditLog, user_name: users.name }).from(auditLog).leftJoin(users, eq(users.id, auditLog.user_id))
      .where(and(...conds)).orderBy(desc(auditLog.created_at), desc(auditLog.id)).limit(100).offset((q.page - 1) * 100);
    return rows.map((r) => ({ ...r.a, user_name: r.user_name }));
  });

  app.get('/api/security-log', async (req) => {
    requireLevel(req, 'admin', 'view');
    return db().select().from(loginAttempts).orderBy(desc(loginAttempts.created_at)).limit(200);
  });

  app.get('/api/import-runs', async (req) => {
    requireLevel(req, 'admin', 'view');
    return db().select().from(importRuns).orderBy(desc(importRuns.started_at)).limit(20);
  });

  app.get('/api/jobs', async (req) => {
    requireLevel(req, 'admin', 'view');
    const { TASKS } = await import('../jobs/tasks');
    return Promise.all(Object.entries(TASKS).map(async ([name, t]) => {
      const raw = await getSetting(`jobs.last.${name}`, '');
      let last: unknown = null; try { last = raw ? JSON.parse(raw) : null; } catch { /* ignore */ }
      return { name, label: t.label, cron: t.cron, last };
    }));
  });

  // ───────── Dashboard ─────────
  app.get('/api/dashboard', async (req) => {
    const u = requireUser(req);
    const can = (a: Parameters<typeof levelOf>[1]) => levelOf(u, a) !== 'none';
    const out: Record<string, unknown> = {};
    if (can('tickets')) {
      const open = inArray(tickets.status, [...OPEN_STATUSES]);
      const [[o], [mine], [un], [risk]] = await Promise.all([
        db().select({ n: count() }).from(tickets).where(open),
        db().select({ n: count() }).from(tickets).where(and(open, eq(tickets.assigned_to, u.id))),
        db().select({ n: count() }).from(tickets).where(and(open, isNull(tickets.assigned_to))),
        db().select({ n: count() }).from(tickets).where(and(inArray(tickets.status, ['New', 'Open', 'Scheduled']), isNull(tickets.first_response_at), lt(tickets.response_due_at, new Date(Date.now() + 3600_000)))),
      ]);
      out.tickets = { open: Number(o.n), mine: Number(mine.n), unassigned: Number(un.n), risk: Number(risk.n) };
      out.attention = await db().select({ id: tickets.id, number: tickets.number, subject: tickets.subject, priority: tickets.priority, status: tickets.status, response_due_at: tickets.response_due_at })
        .from(tickets).where(and(open, or(eq(tickets.priority, 'Critical'), lt(tickets.response_due_at, new Date(Date.now() + 3600_000))))).orderBy(asc(tickets.response_due_at)).limit(8);
    }
    if (can('billing')) {
      const today = new Date().toISOString().slice(0, 10);
      const [[unpaid], [overdue]] = await Promise.all([
        db().select({ n: count(), sum: sql<string>`coalesce(sum(${invoices.total} - coalesce(${invoices.amount_paid},0)),0)` }).from(invoices).where(and(isNull(invoices.archived_at), inArray(invoices.status, ['Sent', 'Viewed', 'Partial', 'Overdue']))),
        db().select({ n: count() }).from(invoices).where(and(isNull(invoices.archived_at), inArray(invoices.status, ['Sent', 'Viewed', 'Partial', 'Overdue']), lt(invoices.due_date, today))),
      ]);
      out.billing = { unpaid: Number(unpaid.n), unpaidAmount: unpaid.sum, overdue: Number(overdue.n) };
    }
    if (can('tools')) {
      const b = resourceTables.backups; const d = resourceTables.domains;
      const soon = new Date(Date.now() + 30 * 86400_000).toISOString().slice(0, 10);
      const [[bf], [de]] = await Promise.all([
        db().select({ n: count() }).from(b).where(and(isNull(b.archived_at), eq(b.last_result, 'Failed'))),
        db().select({ n: count() }).from(d).where(and(isNull(d.archived_at), lt(d.expires_on, soon), gte(d.expires_on, new Date().toISOString().slice(0, 10)))),
      ]);
      out.tools = { backupFailures: Number(bf.n), domainsExpiring: Number(de.n) };
    }
    out.welcome = await getSetting('brand.welcome', '');
    return out;
  });

  void forbidden; void HttpError;
}
