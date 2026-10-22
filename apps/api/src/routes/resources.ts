import type { FastifyInstance, FastifyRequest } from 'fastify';
import { z } from 'zod';
import { and, asc, count, desc, eq, ilike, inArray, isNotNull, isNull, or, sql, type SQL } from 'drizzle-orm';
import { RES, RESOURCES, atLeast, canUse, lineItemSchema, resourceSchema, type Field, type Resource } from '@ws/shared';
import { db, type Tx } from '../db';
import { resourceTables, users } from '../db/schema';
import { decrypt, encrypt } from '../lib/crypto';
import { audit, bad, forbidden, HttpError, nextNumber, notFound } from '../lib/util';
import { levelOf, requireUser, type SessionUser } from '../auth/session';

const visible = (r: Resource) => !r.hidden;
export function resourceOr404(id: string): Resource {
  const r = RES[id];
  if (!r) throw notFound('Unknown module');
  return r;
}

/** The field used as a row's display name (for pickers and ref labels). */
export function labelKey(r: Resource): string {
  if (r.number) return r.number.key;
  return (r.fields.find((f) => f.required && (f.type === 'text')) ?? r.fields.find((f) => f.type === 'text') ?? r.fields[0]).key;
}

const isManager = (u: SessionUser, r: Resource) => atLeast(levelOf(u, r.area), 'manage');

function guard(req: FastifyRequest, r: Resource, need: 'view' | 'edit' | 'manage'): SessionUser {
  const u = requireUser(req);
  if (!canUse(u.role, r, need, u.hr_access)) throw forbidden();
  return u;
}

/** Owner-scoped modules: non-managers only ever touch their own rows. */
function scope(u: SessionUser, r: Resource): SQL | undefined {
  if (!r.ownerScoped || isManager(u, r)) return undefined;
  return eq(resourceTables[r.id].user_id, u.id);
}

/** Turn validated form input into column values (encrypt secrets, keep everything else). */
function toColumns(r: Resource, input: Record<string, unknown>) {
  const out: Record<string, unknown> = {};
  for (const f of r.fields) {
    if (!(f.key in input) || f.readOnly) continue;
    const v = input[f.key];
    if (f.type === 'secret') { out[f.key] = v == null || v === '' ? null : encrypt(String(v)); continue; }
    if ((f.type === 'decimal' || f.type === 'money') && v != null) { out[f.key] = String(v); continue; }
    if (f.type === 'datetime' && v != null) { out[f.key] = new Date(String(v)); continue; }
    out[f.key] = v;
  }
  return out;
}

/** Rows as sent to the browser: secrets are replaced by "is it set?" flags. */
function present(r: Resource, row: Record<string, unknown>) {
  const out: Record<string, unknown> = { ...row };
  for (const f of r.fields) if (f.type === 'secret') { out[f.key] = null; out[`${f.key}__set`] = !!row[f.key]; }
  return out;
}

/** Look up display names for every ref column in a page of rows, in one query per referenced table. */
async function refLabels(r: Resource, rows: Record<string, unknown>[]) {
  const labels: Record<string, Record<number, string>> = {};
  const refs = r.fields.filter((f) => f.type === 'ref');
  for (const f of refs) {
    const ids = [...new Set(rows.map((x) => x[f.key]).filter((v): v is number => typeof v === 'number'))];
    if (!ids.length) continue;
    labels[f.key] = await labelsFor(f.ref!, ids);
  }
  return labels;
}

export async function labelsFor(ref: string, ids: number[]): Promise<Record<number, string>> {
  if (!ids.length) return {};
  if (ref === 'users') {
    const rows = await db().select({ id: users.id, label: users.name }).from(users).where(inArray(users.id, ids));
    return Object.fromEntries(rows.map((x) => [x.id, x.label]));
  }
  const rr = RES[ref]; const t = resourceTables[ref];
  const rows = await db().select({ id: t.id, label: t[labelKey(rr)] }).from(t).where(inArray(t.id, ids));
  return Object.fromEntries(rows.map((x: any) => [x.id, String(x.label ?? '')]));
}

function money(n: number) { return Math.round(n * 100) / 100; }

/** Recalculate line totals and the parent's subtotal / tax / total from its line items. */
async function saveLineItems(tx: Tx, r: Resource, parentId: number, items: z.infer<typeof lineItemSchema>[], taxRate: number) {
  const li = r.lineItems!; const lt = resourceTables[li.resource];
  await tx.delete(lt).where(eq(lt[li.fk], parentId));
  let subtotal = 0, taxable = 0;
  const rows = items.map((it, i) => {
    const line = money(it.qty * it.rate);
    subtotal += line; if (it.taxable) taxable += line;
    return { [li.fk]: parentId, description: it.description, qty: String(it.qty), rate: String(it.rate), taxable: it.taxable, line_total: String(line), sort_order: i };
  });
  if (rows.length) await tx.insert(lt).values(rows);
  const tax = money(taxable * (taxRate || 0) / 100);
  const pt = resourceTables[r.id];
  const set: Record<string, unknown> = { total: String(money(subtotal + tax)), updated_at: new Date() };
  if (r.fields.some((f) => f.key === 'subtotal')) { set.subtotal = String(money(subtotal)); set.tax_amount = String(tax); }
  await tx.update(pt).set(set).where(eq(pt.id, parentId));
}

const listQuery = z.object({
  q: z.string().max(200).optional(),
  status: z.string().max(60).optional(),
  sort: z.string().max(60).optional(),
  dir: z.enum(['asc', 'desc']).optional(),
  page: z.coerce.number().int().min(1).max(100000).default(1),
  limit: z.coerce.number().int().min(1).max(200).default(50),
  archived: z.enum(['0', '1']).default('0'),
}).passthrough();

const escapeLike = (s: string) => s.replace(/[\\%_]/g, (c) => '\\' + c);

export async function resourceRoutes(app: FastifyInstance) {
  /** Module list for the web app (only modules this user may open). */
  app.get('/api/modules', async (req) => {
    const u = requireUser(req);
    return RESOURCES.filter((r) => canUse(u.role, r, 'view', u.hr_access)).map((r) => ({ id: r.id, level: levelOf(u, r.area), ownerScoped: !!r.ownerScoped }));
  });

  app.get('/api/r/:res', async (req) => {
    const r = resourceOr404((req.params as { res: string }).res);
    const u = guard(req, r, 'view');
    const qp = listQuery.parse(req.query);
    const t = resourceTables[r.id];
    const conds: (SQL | undefined)[] = [qp.archived === '1' ? isNotNull(t.archived_at) : isNull(t.archived_at), scope(u, r)];
    if (qp.q && r.search.length) {
      const like = `%${escapeLike(qp.q)}%`;
      conds.push(or(...r.search.map((k) => ilike(sql`${t[k]}::text`, like))));
    }
    if (qp.status && r.statusField) conds.push(eq(t[r.statusField], qp.status));
    // Filter by any ref column: ?client_id=5
    for (const f of r.fields.filter((x) => x.type === 'ref')) {
      const v = (qp as Record<string, unknown>)[f.key];
      if (v !== undefined && v !== '') {
        const id = Number(v);
        if (!Number.isInteger(id) || id <= 0) throw bad(`Bad filter for ${f.label}`);
        conds.push(eq(t[f.key], id));
      }
    }
    const where = and(...conds.filter(Boolean));
    const sortable = new Set([...r.fields.filter((f) => f.type !== 'secret').map((f) => f.key), 'created_at', 'updated_at', 'id']);
    const sortKey = qp.sort && sortable.has(qp.sort) ? qp.sort : r.defaultSort?.key ?? 'id';
    const dir = qp.dir ?? r.defaultSort?.dir ?? (sortKey === 'id' ? 'desc' : 'asc');
    const [rows, [{ total }]] = await Promise.all([
      db().select().from(t).where(where).orderBy(dir === 'asc' ? asc(t[sortKey]) : desc(t[sortKey]), desc(t.id))
        .limit(qp.limit).offset((qp.page - 1) * qp.limit),
      db().select({ total: count() }).from(t).where(where),
    ]);
    let counts: Record<string, number> | undefined;
    if (r.statusField) {
      const base = and(...[isNull(t.archived_at), scope(u, r)].filter(Boolean));
      const c = await db().select({ k: t[r.statusField], n: count() }).from(t).where(base).groupBy(t[r.statusField]);
      counts = Object.fromEntries(c.map((x: any) => [x.k ?? '', Number(x.n)]));
    }
    return { rows: rows.map((x) => present(r, x)), total: Number(total), page: qp.page, limit: qp.limit, labels: await refLabels(r, rows), counts };
  });

  app.get('/api/r/:res/:id', async (req) => {
    const { res, id } = z.object({ res: z.string(), id: z.coerce.number().int().positive() }).parse(req.params);
    const r = resourceOr404(res);
    const u = guard(req, r, 'view');
    const t = resourceTables[r.id];
    const [row] = await db().select().from(t).where(and(eq(t.id, id), scope(u, r))).limit(1);
    if (!row) throw notFound();
    let items: Record<string, unknown>[] | undefined;
    if (r.lineItems) {
      const lt = resourceTables[r.lineItems.resource];
      items = await db().select().from(lt).where(eq(lt[r.lineItems.fk], id)).orderBy(asc(lt.sort_order), asc(lt.id));
    }
    return { row: present(r, row), items, labels: await refLabels(r, [row]) };
  });

  const writeBody = (r: Resource, mode: 'create' | 'update') => z.object({
    data: resourceSchema(r, mode),
    items: z.array(lineItemSchema).max(500).optional(),
  }).strict();

  app.post('/api/r/:res', async (req) => {
    const r = resourceOr404((req.params as { res: string }).res);
    if (r.hidden) throw notFound();
    const u = guard(req, r, 'edit');
    const body = writeBody(r, 'create').parse(req.body);
    const data = body.data as Record<string, unknown>;
    if (r.ownerScoped && !isManager(u, r) && r.statusField) delete data[r.statusField];
    const t = resourceTables[r.id];
    const created = await db().transaction(async (tx) => {
      const cols = toColumns(r, data);
      if (r.number) cols[r.number.key] = r.number.prefix + (await nextNumber(tx, r.id, r.number.start));
      if (r.ownerScoped) cols.user_id = u.id;
      cols.created_by = u.id;
      const [row] = await tx.insert(t).values(cols).returning();
      if (r.lineItems) await saveLineItems(tx, r, row.id, body.items ?? [], Number(data.tax_rate ?? 0));
      await audit(req, { action: 'create', entity: r.id, entityId: row.id, summary: `Created ${r.singular.toLowerCase()} ${String(row[labelKey(r)] ?? row.id)}`, changes: redact(r, data) }, tx);
      return row;
    });
    return { row: present(r, created) };
  });

  app.patch('/api/r/:res/:id', async (req) => {
    const { res, id } = z.object({ res: z.string(), id: z.coerce.number().int().positive() }).parse(req.params);
    const r = resourceOr404(res);
    if (r.hidden) throw notFound();
    const u = guard(req, r, 'edit');
    const body = writeBody(r, 'update').parse(req.body);
    const data = body.data as Record<string, unknown>;
    if (r.ownerScoped && !isManager(u, r) && r.statusField) delete data[r.statusField];
    const t = resourceTables[r.id];
    const updated = await db().transaction(async (tx) => {
      const [before] = await tx.select().from(t).where(and(eq(t.id, id), scope(u, r))).for('update').limit(1);
      if (!before) throw notFound();
      if (before.archived_at) throw bad('This record is archived. Restore it before editing.');
      const cols = toColumns(r, data);
      // Secrets: an empty value in an edit means "leave as is", not "erase".
      for (const f of r.fields) if (f.type === 'secret' && cols[f.key] == null) delete cols[f.key];
      const [row] = await tx.update(t).set({ ...cols, updated_at: new Date() }).where(eq(t.id, id)).returning();
      if (r.lineItems && body.items) await saveLineItems(tx, r, id, body.items, Number(row.tax_rate ?? 0));
      await audit(req, { action: 'update', entity: r.id, entityId: id, summary: `Updated ${r.singular.toLowerCase()} ${String(row[labelKey(r)] ?? id)}`, changes: diff(r, before, data) }, tx);
      return row;
    });
    return { row: present(r, updated) };
  });

  /** Archive (soft delete) — nothing is ever hard-deleted from the UI. */
  app.delete('/api/r/:res/:id', async (req) => {
    const { res, id } = z.object({ res: z.string(), id: z.coerce.number().int().positive() }).parse(req.params);
    const r = resourceOr404(res);
    if (r.hidden) throw notFound();
    const u = guard(req, r, 'manage');
    const t = resourceTables[r.id];
    const [row] = await db().update(t).set({ archived_at: new Date() }).where(and(eq(t.id, id), isNull(t.archived_at), scope(u, r))).returning();
    if (!row) throw notFound();
    await audit(req, { action: 'archive', entity: r.id, entityId: id, summary: `Archived ${r.singular.toLowerCase()} ${String(row[labelKey(r)] ?? id)}` });
    return { ok: true };
  });

  app.post('/api/r/:res/:id/restore', async (req) => {
    const { res, id } = z.object({ res: z.string(), id: z.coerce.number().int().positive() }).parse(req.params);
    const r = resourceOr404(res);
    const u = guard(req, r, 'manage');
    const t = resourceTables[r.id];
    const [row] = await db().update(t).set({ archived_at: null }).where(and(eq(t.id, id), scope(u, r))).returning();
    if (!row) throw notFound();
    await audit(req, { action: 'restore', entity: r.id, entityId: id, summary: `Restored ${r.singular.toLowerCase()}` });
    return { ok: true };
  });

  /** Show one encrypted value. Needs manage-level access to the module and is always written to the audit log. */
  app.post('/api/r/:res/:id/reveal/:field', { config: { rateLimit: { max: 20, timeWindow: '1 minute' } } }, async (req) => {
    const { res, id, field } = z.object({ res: z.string(), id: z.coerce.number().int().positive(), field: z.string().max(60) }).parse(req.params);
    const r = resourceOr404(res);
    const f = r.fields.find((x) => x.key === field && x.type === 'secret');
    if (!f) throw notFound();
    const u = requireUser(req);
    const need = r.area === 'hr' ? 'manage' : 'edit';
    if (!atLeast(levelOf(u, r.area), need)) throw forbidden('You do not have permission to see this.');
    const t = resourceTables[r.id];
    const [row] = await db().select({ v: t[field], label: t[labelKey(r)] }).from(t).where(eq(t.id, id)).limit(1);
    if (!row) throw notFound();
    await audit(req, { action: 'reveal', entity: r.id, entityId: id, summary: `Viewed ${f.label} on ${String(row.label)}` });
    let value = '';
    try { value = decrypt(row.v as string); } catch { throw new HttpError(500, 'This value could not be decrypted. Check APP_ENCRYPTION_KEY.'); }
    return { value };
  });

  /** Options for pickers: GET /api/options/clients?q=fra */
  app.get('/api/options/:res', async (req) => {
    const { res } = z.object({ res: z.string() }).parse(req.params);
    const { q, ids } = z.object({ q: z.string().max(100).optional(), ids: z.string().max(2000).optional() }).parse(req.query);
    const u = requireUser(req);
    const idList = ids ? ids.split(',').map(Number).filter((n) => Number.isInteger(n) && n > 0).slice(0, 200) : [];
    if (res === 'users') {
      const conds = [isNull(users.archived_at)] as SQL[];
      if (q) conds.push(ilike(users.name, `%${escapeLike(q)}%`));
      if (idList.length) conds.push(inArray(users.id, idList));
      const rows = await db().select({ id: users.id, label: users.name }).from(users).where(and(...conds)).orderBy(asc(users.name)).limit(50);
      return rows;
    }
    const r = resourceOr404(res);
    if (!canUse(u.role, r, 'view', u.hr_access)) throw forbidden();
    const t = resourceTables[r.id]; const lk = labelKey(r);
    const conds: (SQL | undefined)[] = [isNull(t.archived_at), scope(u, r)];
    if (q) conds.push(ilike(sql`${t[lk]}::text`, `%${escapeLike(q)}%`));
    if (idList.length) conds.push(inArray(t.id, idList));
    const extra = (req.query as Record<string, string>).client_id;
    if (extra && r.fields.some((f) => f.key === 'client_id')) conds.push(eq(t.client_id, Number(extra) || 0));
    const rows = await db().select({ id: t.id, label: t[lk] }).from(t).where(and(...conds.filter(Boolean))).orderBy(asc(t[lk])).limit(50);
    return rows.map((x: any) => ({ id: x.id, label: String(x.label ?? '') }));
  });

  void visible;
}

function redact(r: Resource, data: Record<string, unknown>) {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    const f = r.fields.find((x) => x.key === k);
    out[k] = f?.type === 'secret' ? (v ? '[set]' : '[cleared]') : v;
  }
  return out;
}

function diff(r: Resource, before: Record<string, unknown>, data: Record<string, unknown>) {
  const out: Record<string, { from: unknown; to: unknown }> = {};
  for (const [k, v] of Object.entries(data)) {
    const f: Field | undefined = r.fields.find((x) => x.key === k);
    if (!f) continue;
    if (f.type === 'secret') { if (v) out[k] = { from: '[hidden]', to: '[changed]' }; continue; }
    const prev = before[k] instanceof Date ? (before[k] as Date).toISOString() : before[k];
    const norm = (x: unknown) => (x == null ? null : String(x));
    if (norm(prev) !== norm(v)) out[k] = { from: prev ?? null, to: v ?? null };
  }
  return out;
}
