import fp from 'fastify-plugin';
import { and, eq, isNull, gt, sql } from 'drizzle-orm';
import type { FastifyReply, FastifyRequest } from 'fastify';
import { levelFor, atLeast, type Level, type PermArea, type Role } from '@ws/shared';
import { db } from '../db';
import { sessions, users } from '../db/schema';
import { randomToken, sha256, safeEqual } from '../lib/crypto';
import { config } from '../config';
import { getSetting, HttpError } from '../lib/util';

export interface SessionUser {
  id: number; email: string; name: string; role: Role; hr_access: boolean; look: string;
  mfa_enabled: boolean; must_change_password: boolean; title: string | null; phone: string | null;
}
export interface SessionInfo { id: string; csrf: string; mfaPassed: boolean; mfaSetupRequired: boolean }

declare module 'fastify' {
  interface FastifyRequest {
    user: SessionUser | null;
    sess: SessionInfo | null;
  }
}

const ABSOLUTE_HOURS = 12;
export const cookieName = () => (config().APP_URL.startsWith('https://') ? '__Host-ws_sid' : 'ws_sid');
const secureCookie = () => config().APP_URL.startsWith('https://');

export async function mfaRequiredFor(role: Role): Promise<boolean> {
  const policy = await getSetting('security.require_mfa', 'admins');
  return policy === 'everyone' || (policy === 'admins' && role === 'admin');
}

export async function idleMinutes(): Promise<number> {
  const v = parseInt(await getSetting('security.idle_minutes', '30'), 10);
  return Number.isFinite(v) && v >= 5 && v <= 24 * 60 ? v : 30;
}

/** Create a session and set the cookie. The token lives only in the cookie; the DB keeps its sha256. */
export async function startSession(req: FastifyRequest, reply: FastifyReply, userId: number, mfaPassed: boolean) {
  const token = randomToken(32);
  const id = sha256(token);
  await db().insert(sessions).values({
    id, user_id: userId, csrf_token: randomToken(24), mfa_passed: mfaPassed,
    ip: req.ip?.slice(0, 64) ?? null, user_agent: (req.headers['user-agent'] ?? '').slice(0, 300),
    expires_at: new Date(Date.now() + ABSOLUTE_HOURS * 3600_000),
  });
  reply.setCookie(cookieName(), token, {
    httpOnly: true, secure: secureCookie(), sameSite: 'lax', path: '/', maxAge: ABSOLUTE_HOURS * 3600,
  });
  return id;
}

export async function endSession(req: FastifyRequest, reply: FastifyReply) {
  if (req.sess) await db().update(sessions).set({ revoked_at: new Date() }).where(eq(sessions.id, req.sess.id));
  reply.clearCookie(cookieName(), { path: '/', secure: secureCookie(), httpOnly: true, sameSite: 'lax' });
}

export async function revokeAllSessions(userId: number, exceptId?: string) {
  const cond = exceptId
    ? and(eq(sessions.user_id, userId), isNull(sessions.revoked_at), sql`${sessions.id} <> ${exceptId}`)
    : and(eq(sessions.user_id, userId), isNull(sessions.revoked_at));
  await db().update(sessions).set({ revoked_at: new Date() }).where(cond);
}

const UNSAFE = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

/** Loads the session for /api requests and enforces the CSRF + Origin rules on writes. */
export const sessionPlugin = fp(async (app) => {
  app.decorateRequest('user', null);
  app.decorateRequest('sess', null);

  app.addHook('onRequest', async (req) => {
    if (!req.url.startsWith('/api/')) return;

    // 1) Origin check on every write: the request must come from our own site.
    if (UNSAFE.has(req.method) && !req.url.startsWith('/api/webhooks/')) {
      const expected = new URL(config().APP_URL).origin;
      const origin = req.headers.origin ?? (req.headers.referer ? safeOrigin(req.headers.referer) : undefined);
      if (origin !== expected) throw new HttpError(403, 'Request blocked: it did not come from this site.');
    }

    // 2) Session.
    const token = req.cookies?.[cookieName()];
    if (!token) return;
    const id = sha256(token);
    const now = new Date();
    const [row] = await db().select({ s: sessions, u: users }).from(sessions)
      .innerJoin(users, eq(users.id, sessions.user_id))
      .where(and(eq(sessions.id, id), isNull(sessions.revoked_at), gt(sessions.expires_at, now), isNull(users.archived_at)))
      .limit(1);
    if (!row) return;
    const idle = await idleMinutes();
    if (now.getTime() - row.s.last_seen_at.getTime() > idle * 60_000) {
      await db().update(sessions).set({ revoked_at: now }).where(eq(sessions.id, id));
      return;
    }
    if (now.getTime() - row.s.last_seen_at.getTime() > 60_000) {
      await db().update(sessions).set({ last_seen_at: now }).where(eq(sessions.id, id));
    }
    const u = row.u;
    req.user = {
      id: u.id, email: u.email, name: u.name, role: u.role as Role, hr_access: u.hr_access, look: u.look,
      mfa_enabled: u.mfa_enabled, must_change_password: u.must_change_password, title: u.title, phone: u.phone,
    };
    req.sess = {
      id, csrf: row.s.csrf_token, mfaPassed: row.s.mfa_passed,
      mfaSetupRequired: !u.mfa_enabled && (await mfaRequiredFor(u.role as Role)),
    };

    // 3) CSRF token on every authenticated write (double check on top of the Origin rule).
    if (UNSAFE.has(req.method)) {
      const sent = String(req.headers['x-csrf-token'] ?? '');
      if (!sent || !safeEqual(sent, row.s.csrf_token)) throw new HttpError(403, 'Request blocked: missing or wrong security token. Reload the page.');
    }
  });
});

function safeOrigin(u: string): string | undefined { try { return new URL(u).origin; } catch { return undefined; } }

/**
 * Guard for normal app routes: signed in, two-factor done, two-factor set up when required,
 * and no forced password change pending.
 */
export function requireUser(req: FastifyRequest): SessionUser {
  if (!req.user || !req.sess) throw new HttpError(401, 'Please sign in.');
  if (!req.sess.mfaPassed) throw new HttpError(401, 'Enter your two-factor code to continue.');
  if (req.sess.mfaSetupRequired) throw new HttpError(403, 'Set up two-factor sign-in before continuing.');
  if (req.user.must_change_password) throw new HttpError(403, 'Choose a new password before continuing.');
  return req.user;
}

export function levelOf(u: SessionUser, area: PermArea): Level {
  return levelFor(u.role, area, u.hr_access);
}

export function requireLevel(req: FastifyRequest, area: PermArea, need: Level): SessionUser {
  const u = requireUser(req);
  if (!atLeast(levelOf(u, area), need)) throw new HttpError(403, 'You do not have permission to do that.');
  return u;
}
