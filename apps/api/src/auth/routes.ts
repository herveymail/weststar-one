import type { FastifyInstance } from 'fastify';
import { z } from 'zod';
import { and, desc, eq, gt, isNull, sql, count } from 'drizzle-orm';
import { authenticator } from 'otplib';
import QRCode from 'qrcode';
import { passwordRule, levelFor, type PermArea, type Role } from '@ws/shared';
import { db } from '../db';
import { loginAttempts, mfaRecoveryCodes, sessions, users } from '../db/schema';
import { dummyVerify, hashPassword, verifyPassword } from '../lib/passwords';
import { decrypt, encrypt, keyedHash, randomToken, sha256 } from '../lib/crypto';
import { audit, bad, getSetting, HttpError } from '../lib/util';
import { config } from '../config';
import { endSession, mfaRequiredFor, revokeAllSessions, startSession, cookieName } from './session';

authenticator.options = { window: 1, step: 30 };

const LOCK_AFTER = 5;           // failed attempts on one account …
const LOCK_MINUTES = 15;        // … lock it this long (doubles each time it happens again)
const IP_WINDOW_MIN = 15;
const IP_MAX_FAILS = 30;        // failed attempts from one IP in the window before it is blocked

const AREAS: PermArea[] = ['tickets', 'clients', 'projects', 'sales', 'billing', 'tools', 'hr', 'admin'];

export function publicUser(u: typeof users.$inferSelect) {
  return {
    id: u.id, email: u.email, name: u.name, role: u.role, hr_access: u.hr_access, look: u.look, title: u.title, phone: u.phone,
    mfa_enabled: u.mfa_enabled, must_change_password: u.must_change_password, last_login_at: u.last_login_at,
  };
}

async function recordAttempt(email: string | null, ip: string, success: boolean, reason: string) {
  await db().insert(loginAttempts).values({ email: email?.slice(0, 254) ?? null, ip: ip.slice(0, 64), success, reason });
}

/** Checks a TOTP code and refuses to accept the same 30-second code twice. */
async function checkTotp(userId: number, secret: string, code: string): Promise<boolean> {
  const clean = code.replace(/\s+/g, '');
  if (!/^\d{6}$/.test(clean)) return false;
  const delta = authenticator.checkDelta(clean, secret);
  if (delta === null) return false;
  const step = Math.floor(Date.now() / 30_000) + delta;
  const [u] = await db().select({ last: users.totp_last_step }).from(users).where(eq(users.id, userId));
  if (u?.last != null && step <= u.last) return false;
  await db().update(users).set({ totp_last_step: step }).where(eq(users.id, userId));
  return true;
}

async function useRecoveryCode(userId: number, code: string): Promise<boolean> {
  const clean = code.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (clean.length < 8) return false;
  const res = await db().update(mfaRecoveryCodes).set({ used_at: new Date() })
    .where(and(eq(mfaRecoveryCodes.user_id, userId), eq(mfaRecoveryCodes.code_hash, keyedHash(clean)), isNull(mfaRecoveryCodes.used_at)))
    .returning({ id: mfaRecoveryCodes.id });
  return res.length > 0;
}

function makeRecoveryCodes(): string[] {
  const alphabet = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789';
  return Array.from({ length: 10 }, () => {
    const bytes = randomToken(16);
    let s = '';
    for (let i = 0; i < 10; i++) s += alphabet[bytes.charCodeAt(i) % alphabet.length];
    return s.slice(0, 5) + '-' + s.slice(5);
  });
}

export async function authRoutes(app: FastifyInstance) {
  // 10 sign-in attempts per minute per IP (raised only for the automated test suite).
  const strict = { config: { rateLimit: { max: config().NODE_ENV === 'test' ? 10_000 : 10, timeWindow: '1 minute' } } };

  // ── Sign in ──
  app.post('/api/auth/login', strict, async (req, reply) => {
    const body = z.object({ email: z.string().trim().toLowerCase().email().max(254), password: z.string().min(1).max(200) }).parse(req.body);
    const ip = req.ip;

    const since = new Date(Date.now() - IP_WINDOW_MIN * 60_000);
    const [{ n }] = await db().select({ n: count() }).from(loginAttempts)
      .where(and(eq(loginAttempts.ip, ip), eq(loginAttempts.success, false), gt(loginAttempts.created_at, since)));
    if (n >= IP_MAX_FAILS) throw new HttpError(429, 'Too many failed sign-ins from this network. Try again in 15 minutes.');

    const [u] = await db().select().from(users).where(and(sql`lower(${users.email}) = ${body.email}`, isNull(users.archived_at))).limit(1);
    const generic = new HttpError(401, 'That email and password do not match.');
    if (!u) { await dummyVerify(body.password); await recordAttempt(body.email, ip, false, 'unknown_email'); throw generic; }
    if (u.locked_until && u.locked_until > new Date()) {
      await recordAttempt(body.email, ip, false, 'locked');
      throw new HttpError(423, 'This account is locked after too many failed sign-ins. Try again later or ask an admin to unlock it.');
    }

    const { ok, upgrade } = await verifyPassword(u.password_hash, body.password);
    if (!ok) {
      const fails = u.failed_logins + 1;
      const lockTimes = Math.floor(fails / LOCK_AFTER);
      const lockedUntil = fails % LOCK_AFTER === 0 ? new Date(Date.now() + LOCK_MINUTES * 60_000 * 2 ** Math.min(lockTimes - 1, 6)) : u.locked_until;
      await db().update(users).set({ failed_logins: fails, locked_until: lockedUntil }).where(eq(users.id, u.id));
      await recordAttempt(body.email, ip, false, 'bad_password');
      throw generic;
    }

    await db().update(users).set({
      failed_logins: 0, locked_until: null, last_login_at: new Date(),
      ...(upgrade ? { password_hash: await hashPassword(body.password) } : {}),
    }).where(eq(users.id, u.id));
    await recordAttempt(body.email, ip, true, upgrade ? 'ok_upgraded_hash' : 'ok');

    // Session fixation: drop any session that came with the request before issuing a new one.
    if (req.sess) await endSession(req, reply);
    await startSession(req, reply, u.id, !u.mfa_enabled);
    await audit(null, { action: 'login', entity: 'user', entityId: u.id, summary: `${u.email} signed in${u.mfa_enabled ? ' (password step)' : ''}` });
    return { ok: true, mfaRequired: u.mfa_enabled, mfaSetupRequired: !u.mfa_enabled && (await mfaRequiredFor(u.role as Role)), mustChangePassword: u.must_change_password };
  });

  // ── Second step: authenticator code or recovery code ──
  app.post('/api/auth/mfa', strict, async (req, reply) => {
    if (!req.user || !req.sess) throw new HttpError(401, 'Sign in first.');
    if (req.sess.mfaPassed) return { ok: true };
    const body = z.object({ code: z.string().trim().min(6).max(20) }).parse(req.body);
    const [u] = await db().select().from(users).where(eq(users.id, req.user.id));
    let ok = false, usedRecovery = false;
    if (u.totp_secret_enc) ok = await checkTotp(u.id, decrypt(u.totp_secret_enc), body.code);
    if (!ok) { ok = await useRecoveryCode(u.id, body.code); usedRecovery = ok; }
    if (!ok) {
      await recordAttempt(u.email, req.ip, false, 'bad_mfa');
      const fails = u.failed_logins + 1;
      await db().update(users).set({ failed_logins: fails, locked_until: fails >= LOCK_AFTER ? new Date(Date.now() + LOCK_MINUTES * 60_000) : u.locked_until }).where(eq(users.id, u.id));
      if (fails >= LOCK_AFTER) await endSession(req, reply);
      throw new HttpError(401, 'That code is not right. Codes change every 30 seconds.');
    }
    await db().update(users).set({ failed_logins: 0 }).where(eq(users.id, u.id));
    // New session id once fully signed in.
    await endSession(req, reply);
    await startSession(req, reply, u.id, true);
    await audit(null, { action: 'login_mfa', entity: 'user', entityId: u.id, summary: usedRecovery ? 'Signed in with a recovery code' : 'Two-factor code accepted' });
    return { ok: true, usedRecovery };
  });

  app.post('/api/auth/logout', async (req, reply) => {
    if (req.user) await audit(req, { action: 'logout', entity: 'user', entityId: req.user.id });
    await endSession(req, reply);
    return { ok: true };
  });

  // ── Who am I (also hands the browser its CSRF token) ──
  app.get('/api/auth/me', async (req) => {
    if (!req.user || !req.sess) return { user: null };
    const perms = Object.fromEntries(AREAS.map((a) => [a, levelFor(req.user!.role, a, req.user!.hr_access)]));
    return {
      user: req.user, csrfToken: req.sess.csrf, mfaPassed: req.sess.mfaPassed, mfaSetupRequired: req.sess.mfaSetupRequired, perms,
      app: { name: await getSetting('brand.app_name', 'Weststar ONE') },
    };
  });

  const signedIn = (req: { user: unknown; sess: { mfaPassed: boolean } | null }) => {
    if (!req.user || !req.sess?.mfaPassed) throw new HttpError(401, 'Please sign in.');
  };

  // ── Profile & password ──
  app.patch('/api/auth/profile', async (req) => {
    signedIn(req);
    const body = z.object({
      name: z.string().trim().min(1).max(200).optional(), title: z.string().max(100).nullable().optional(),
      phone: z.string().max(50).nullable().optional(), look: z.enum(['indigo', 'graphite']).optional(),
    }).strict().parse(req.body);
    await db().update(users).set({ ...body, updated_at: new Date() }).where(eq(users.id, req.user!.id));
    await audit(req, { action: 'update', entity: 'user', entityId: req.user!.id, summary: 'Updated own profile', changes: body });
    return { ok: true };
  });

  app.post('/api/auth/password', strict, async (req) => {
    signedIn(req);
    const body = z.object({ current: z.string().min(1).max(200), next: passwordRule }).strict().parse(req.body);
    const [u] = await db().select().from(users).where(eq(users.id, req.user!.id));
    const { ok } = await verifyPassword(u.password_hash, body.current);
    if (!ok) throw new HttpError(400, 'Your current password is not right.');
    if (body.next.toLowerCase().includes(u.email.split('@')[0].toLowerCase())) throw bad('Pick a password that does not contain your email name.');
    await db().update(users).set({ password_hash: await hashPassword(body.next), password_changed_at: new Date(), must_change_password: false }).where(eq(users.id, u.id));
    await revokeAllSessions(u.id, req.sess!.id);
    await audit(req, { action: 'password_change', entity: 'user', entityId: u.id, summary: 'Changed password; other sessions signed out' });
    return { ok: true };
  });

  // ── Two-factor setup ──
  app.post('/api/auth/mfa/setup', strict, async (req) => {
    signedIn(req);
    const secret = authenticator.generateSecret(20);
    await db().update(users).set({ totp_pending_enc: encrypt(secret) }).where(eq(users.id, req.user!.id));
    const issuer = await getSetting('brand.app_name', 'Weststar ONE');
    const uri = authenticator.keyuri(req.user!.email, issuer, secret);
    return { secret, uri, qr: await QRCode.toDataURL(uri, { margin: 1, width: 220 }) };
  });

  app.post('/api/auth/mfa/enable', strict, async (req) => {
    signedIn(req);
    const { code } = z.object({ code: z.string().trim().min(6).max(10) }).parse(req.body);
    const [u] = await db().select().from(users).where(eq(users.id, req.user!.id));
    if (!u.totp_pending_enc) throw bad('Start two-factor setup first.');
    const secret = decrypt(u.totp_pending_enc);
    if (!(await checkTotp(u.id, secret, code))) throw bad('That code is not right. Check the time on your phone and try the newest code.');
    const codes = makeRecoveryCodes();
    await db().transaction(async (tx) => {
      await tx.update(users).set({ totp_secret_enc: encrypt(secret), totp_pending_enc: null, mfa_enabled: true }).where(eq(users.id, u.id));
      await tx.delete(mfaRecoveryCodes).where(eq(mfaRecoveryCodes.user_id, u.id));
      await tx.insert(mfaRecoveryCodes).values(codes.map((c) => ({ user_id: u.id, code_hash: keyedHash(c.replace('-', '')) })));
      await tx.update(sessions).set({ mfa_passed: true }).where(eq(sessions.id, req.sess!.id));
    });
    await audit(req, { action: 'mfa_enable', entity: 'user', entityId: u.id, summary: 'Turned on two-factor sign-in' });
    return { ok: true, recoveryCodes: codes };
  });

  app.post('/api/auth/mfa/disable', strict, async (req) => {
    signedIn(req);
    const { password } = z.object({ password: z.string().min(1).max(200) }).parse(req.body);
    const [u] = await db().select().from(users).where(eq(users.id, req.user!.id));
    if (await mfaRequiredFor(u.role as Role)) throw new HttpError(403, 'Two-factor sign-in is required for your account and cannot be turned off.');
    if (!(await verifyPassword(u.password_hash, password)).ok) throw bad('Your password is not right.');
    await db().update(users).set({ mfa_enabled: false, totp_secret_enc: null, totp_pending_enc: null }).where(eq(users.id, u.id));
    await db().delete(mfaRecoveryCodes).where(eq(mfaRecoveryCodes.user_id, u.id));
    await audit(req, { action: 'mfa_disable', entity: 'user', entityId: u.id, summary: 'Turned off two-factor sign-in' });
    return { ok: true };
  });

  // ── My sessions ──
  app.get('/api/auth/sessions', async (req) => {
    signedIn(req);
    const rows = await db().select({ id: sessions.id, ip: sessions.ip, user_agent: sessions.user_agent, created_at: sessions.created_at, last_seen_at: sessions.last_seen_at })
      .from(sessions).where(and(eq(sessions.user_id, req.user!.id), isNull(sessions.revoked_at), gt(sessions.expires_at, new Date())))
      .orderBy(desc(sessions.last_seen_at));
    // Never hand out the real session id — use a short fingerprint instead.
    return rows.map((r) => ({ ...r, id: sha256(r.id).slice(0, 16), current: r.id === req.sess!.id }));
  });

  app.delete('/api/auth/sessions/:fp', async (req) => {
    signedIn(req);
    const { fp } = z.object({ fp: z.string().regex(/^[a-f0-9]{16}$/) }).parse(req.params);
    const rows = await db().select({ id: sessions.id }).from(sessions).where(and(eq(sessions.user_id, req.user!.id), isNull(sessions.revoked_at)));
    const match = rows.find((r) => sha256(r.id).slice(0, 16) === fp);
    if (!match) throw new HttpError(404, 'Session not found.');
    await db().update(sessions).set({ revoked_at: new Date() }).where(eq(sessions.id, match.id));
    await audit(req, { action: 'session_revoke', entity: 'user', entityId: req.user!.id, summary: 'Signed out another session' });
    return { ok: true };
  });

  void cookieName;
}
