import { eq, sql } from 'drizzle-orm';
import type { FastifyReply, FastifyRequest } from 'fastify';
import { db, type Tx, type DB } from '../db';
import { auditLog, counters, settings } from '../db/schema';
import { decrypt, encrypt } from './crypto';

export class HttpError extends Error {
  constructor(public status: number, message: string, public details?: unknown) { super(message); }
}
export const notFound = (what = 'Not found') => new HttpError(404, what);
export const forbidden = (what = 'You do not have permission to do that.') => new HttpError(403, what);
export const bad = (what: string, details?: unknown) => new HttpError(400, what, details);

/** Next number in a sequence, e.g. nextNumber(tx, 'ticket', 10001) → 10001, 10002 … */
export async function nextNumber(tx: Tx | DB, name: string, start: number): Promise<number> {
  const rows = await tx.execute<{ value: number }>(sql`
    INSERT INTO ${counters} (name, value) VALUES (${name}, ${start})
    ON CONFLICT (name) DO UPDATE SET value = ${counters.value} + 1
    RETURNING value`);
  return Number(rows[0].value);
}

/** Make sure a sequence is at least `atLeast` (used after importing old numbers). */
export async function bumpCounter(tx: Tx | DB, name: string, atLeast: number) {
  await tx.execute(sql`
    INSERT INTO ${counters} (name, value) VALUES (${name}, ${atLeast})
    ON CONFLICT (name) DO UPDATE SET value = GREATEST(${counters.value}, ${atLeast})`);
}

export interface AuditEntry { action: string; entity: string; entityId?: string | number | null; summary?: string; changes?: unknown }
export async function audit(req: FastifyRequest | null, e: AuditEntry, tx: Tx | DB = db()) {
  await tx.insert(auditLog).values({
    user_id: req?.user?.id ?? null,
    action: e.action, entity: e.entity,
    entity_id: e.entityId == null ? null : String(e.entityId),
    summary: e.summary?.slice(0, 500) ?? null,
    changes: (e.changes ?? null) as never,
    ip: req?.ip ?? null,
  });
}

// ── settings (small key/value store; secrets encrypted) ──
export async function getSetting(key: string, fallback = ''): Promise<string> {
  const [row] = await db().select().from(settings).where(eq(settings.key, key)).limit(1);
  if (!row) return fallback;
  if (!row.is_secret) return row.value;
  try { return decrypt(row.value); } catch { return fallback; }
}
export async function setSetting(key: string, value: string, secret: boolean, userId: number | null, tx: Tx | DB = db()) {
  const stored = secret ? encrypt(value) : value;
  await tx.insert(settings).values({ key, value: stored, is_secret: secret, updated_by: userId })
    .onConflictDoUpdate({ target: settings.key, set: { value: stored, is_secret: secret, updated_by: userId, updated_at: new Date() } });
}

export const sendError = (reply: FastifyReply, status: number, message: string, details?: unknown) =>
  reply.code(status).send({ error: message, ...(details ? { details } : {}) });
