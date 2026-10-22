import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { authenticator } from 'otplib';
import { eq } from 'drizzle-orm';
import type { FastifyInstance } from 'fastify';
import { resetDb, makeApp, done, addUser, signIn, agentFrom, ORIGIN } from './helpers';
import { db } from '../src/db';
import { users, sessions, auditLog } from '../src/db/schema';
import { setSetting } from '../src/lib/util';

let app: FastifyInstance;
beforeAll(async () => { await resetDb(); app = await makeApp(); await setSetting('security.require_mfa', 'nobody', false, null); });
afterAll(async () => { await done(app); });

const login = (email: string, password: string, headers: Record<string, string> = { origin: ORIGIN }) =>
  app.inject({ method: 'POST', url: '/api/auth/login', headers, payload: { email, password } });

describe('sign in', () => {
  it('signs in with the right password and stores only a hash of the session token', async () => {
    await addUser('tech@x.com', 'tech');
    const r = await login('TECH@x.com', 'a-long-test-password');
    expect(r.statusCode).toBe(200);
    const cookie = String(r.headers['set-cookie']);
    expect(cookie).toMatch(/HttpOnly/i);
    expect(cookie).toMatch(/SameSite=Lax/i);
    const token = cookie.split(';')[0].split('=')[1];
    const rows = await db().select().from(sessions);
    expect(rows.some((s) => s.id === token)).toBe(false); // raw token never stored
  });

  it('gives the same answer for a wrong password and an unknown email', async () => {
    const a = await login('tech@x.com', 'wrong-password-123');
    const b = await login('nobody@x.com', 'wrong-password-123');
    expect(a.statusCode).toBe(401); expect(b.statusCode).toBe(401);
    expect(a.json().error).toBe(b.json().error);
  });

  it('locks an account after 5 wrong passwords', async () => {
    await addUser('lockme@x.com', 'tech');
    for (let i = 0; i < 5; i++) await login('lockme@x.com', 'nope-nope-nope');
    const r = await login('lockme@x.com', 'a-long-test-password');
    expect(r.statusCode).toBe(423);
  });

  it('blocks writes from another website (Origin check) and without the CSRF token', async () => {
    const a = await signIn(app, 'tech@x.com');
    const evil = await app.inject({ method: 'POST', url: '/api/tickets', headers: { cookie: a.cookie, origin: 'https://evil.example', 'x-csrf-token': a.csrf }, payload: { subject: 'x' } });
    expect(evil.statusCode).toBe(403);
    const noToken = await app.inject({ method: 'POST', url: '/api/tickets', headers: { cookie: a.cookie, origin: ORIGIN }, payload: { subject: 'x' } });
    expect(noToken.statusCode).toBe(403);
    const ok = await a.send('POST', '/api/tickets', { subject: 'x' });
    expect(ok.status).toBe(200);
  });

  it('a login form posted from another site is refused', async () => {
    const r = await login('tech@x.com', 'a-long-test-password', { origin: 'https://evil.example' });
    expect(r.statusCode).toBe(403);
  });

  it('logout revokes the session', async () => {
    const a = await signIn(app, 'tech@x.com');
    await a.send('POST', '/api/auth/logout');
    const r = await a.get('/api/tickets');
    expect(r.status).toBe(401);
  });
});

describe('two-factor', () => {
  it('enrolls, then requires a code at sign in, and refuses a reused code', async () => {
    await addUser('mfa@x.com', 'tech');
    const a = await signIn(app, 'mfa@x.com');
    const setup = await a.send('POST', '/api/auth/mfa/setup');
    expect(setup.status).toBe(200);
    expect(setup.body.qr).toMatch(/^data:image\/png;base64,/);
    const secret = setup.body.secret as string;
    const enable = await a.send('POST', '/api/auth/mfa/enable', { code: authenticator.generate(secret) });
    expect(enable.status).toBe(200);
    expect(enable.body.recoveryCodes).toHaveLength(10);
    const [u] = await db().select().from(users).where(eq(users.email, 'mfa@x.com'));
    expect(u.totp_secret_enc).toMatch(/^v1:/);
    expect(u.totp_secret_enc).not.toContain(secret);

    // New sign-in: password alone is not enough.
    const step1 = await login('mfa@x.com', 'a-long-test-password');
    expect(step1.json().mfaRequired).toBe(true);
    const b = await agentFrom(app, String(step1.headers['set-cookie']).split(';')[0]);
    expect((await b.get('/api/tickets')).status).toBe(401);
    // The code used for enrolment cannot be replayed.
    const replay = await b.send('POST', '/api/auth/mfa', { code: authenticator.generate(secret) });
    expect(replay.status).toBe(401);

    // A recovery code works once.
    const step1b = await login('mfa@x.com', 'a-long-test-password');
    const c = await agentFrom(app, String(step1b.headers['set-cookie']).split(';')[0]);
    const rc = enable.body.recoveryCodes[0];
    const ok = await c.send('POST', '/api/auth/mfa', { code: rc });
    expect(ok.status).toBe(200);
    expect(ok.body.usedRecovery).toBe(true);
    const step1c = await login('mfa@x.com', 'a-long-test-password');
    const d = await agentFrom(app, String(step1c.headers['set-cookie']).split(';')[0]);
    expect((await d.send('POST', '/api/auth/mfa', { code: rc })).status).toBe(401);
  });

  it('forces admins to set up two-factor when the policy says so', async () => {
    await setSetting('security.require_mfa', 'admins', false, null);
    await addUser('boss@x.com', 'admin');
    const a = await signIn(app, 'boss@x.com');
    const me = await a.get('/api/auth/me');
    expect(me.body.mfaSetupRequired).toBe(true);
    expect((await a.get('/api/tickets')).status).toBe(403);
    await setSetting('security.require_mfa', 'nobody', false, null);
  });
});

describe('passwords', () => {
  it('changing your password signs out your other sessions', async () => {
    await addUser('pw@x.com', 'tech');
    const a = await signIn(app, 'pw@x.com');
    const b = await signIn(app, 'pw@x.com');
    const r = await a.send('POST', '/api/auth/password', { current: 'a-long-test-password', next: 'another-long-password-2' });
    expect(r.status).toBe(200);
    expect((await b.get('/api/tickets')).status).toBe(401);
    expect((await a.get('/api/tickets')).status).toBe(200);
  });

  it('rejects short passwords', async () => {
    const a = await signIn(app, 'pw@x.com', 'another-long-password-2');
    const r = await a.send('POST', '/api/auth/password', { current: 'another-long-password-2', next: 'short' });
    expect(r.status).toBe(400);
  });

  it('a user with a forced password change cannot use the app until they change it', async () => {
    await addUser('fresh@x.com', 'tech', 'a-long-test-password', { must_change_password: true });
    const a = await signIn(app, 'fresh@x.com');
    expect((await a.get('/api/tickets')).status).toBe(403);
    await a.send('POST', '/api/auth/password', { current: 'a-long-test-password', next: 'brand-new-password-9' });
    expect((await a.get('/api/tickets')).status).toBe(200);
  });

  it('writes sign-ins and password changes to the audit log', async () => {
    const rows = await db().select().from(auditLog);
    expect(rows.some((r) => r.action === 'login')).toBe(true);
    expect(rows.some((r) => r.action === 'password_change')).toBe(true);
    expect(JSON.stringify(rows)).not.toContain('brand-new-password-9');
  });
});
