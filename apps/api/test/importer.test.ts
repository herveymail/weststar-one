/**
 * Importer test against a real MariaDB holding the OLD schema, filled by test/fixtures/legacy-seed.php
 * (which uses the old app's own encryption functions). Runs when LEGACY_MYSQL_URL is set, e.g.
 *   LEGACY_MYSQL_URL=mysql://legacy:legacy@127.0.0.1:3306/legacy pnpm test
 */
import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { execFileSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';
import path from 'node:path';
import { authenticator } from 'otplib';
import type { FastifyInstance } from 'fastify';
import { resetDb, makeApp, done, signIn, agentFrom, ORIGIN } from './helpers';
import { runImport } from '../src/importer/run';
import { db } from '../src/db';
import { tickets, ticketMessages, users } from '../src/db/schema';
import { setSetting } from '../src/lib/util';
import { count, eq } from 'drizzle-orm';

const URL_ = process.env.LEGACY_MYSQL_URL;
const APP_KEY = 'old-app-key-from-config-php-0123456789abcdef';
const ENC_KEY = randomBytes(32).toString('hex');
let app: FastifyInstance;

describe.skipIf(!URL_)('import from the old Weststar One', () => {
  beforeAll(async () => {
    execFileSync('php', [path.resolve(__dirname, 'fixtures/legacy-seed.php')], { env: { ...process.env, OLD_APP_KEY: APP_KEY, OLD_ENCRYPTION_KEY: ENC_KEY, LEGACY_DB: new URL(URL_!).pathname.slice(1) } });
    await resetDb(); app = await makeApp();
    await setSetting('security.require_mfa', 'nobody', false, null);
  });
  afterAll(async () => { if (app) await done(app); });

  it('dry run changes nothing', async () => {
    await runImport({ mysqlUrl: URL_!, appKey: APP_KEY, encryptionKey: ENC_KEY, dryRun: true, log: () => {} });
    expect((await db().select({ n: count() }).from(tickets))[0].n).toBe(0);
  });

  it('imports everything, twice, without duplicates or decryption warnings', async () => {
    const a = await runImport({ mysqlUrl: URL_!, appKey: APP_KEY, encryptionKey: ENC_KEY, log: () => {} });
    const b = await runImport({ mysqlUrl: URL_!, appKey: APP_KEY, encryptionKey: ENC_KEY, log: () => {} });
    expect(a.steps.flatMap((s) => s.warnings)).toEqual([]);
    expect(b.steps.find((s) => s.name === 'tickets')!.imported).toBe(3);
    expect((await db().select({ n: count() }).from(tickets))[0].n).toBe(3);
    expect((await db().select({ n: count() }).from(ticketMessages))[0].n).toBe(3);
  });

  it('keeps ticket numbers and continues numbering after them', async () => {
    const nums = (await db().select({ n: tickets.number }).from(tickets)).map((x) => x.n).sort();
    expect(nums).toEqual(['T-10476', 'T-10482', 'ZOHO-555']);
    await db().update(users).set({ mfa_enabled: false }).where(eq(users.email, 'casey@weststarmsp.com'));
    const a = await signIn(app, 'casey@weststarmsp.com', 'Old-Password-123!');
    const t = await a.send('POST', '/api/tickets', { subject: 'first new ticket' });
    expect(t.body.ticket.number).toBe('T-10483');
  });

  it('old passwords keep working and are upgraded to argon2id', async () => {
    const [u] = await db().select({ h: users.password_hash }).from(users).where(eq(users.email, 'casey@weststarmsp.com'));
    expect(u.h.startsWith('$argon2id$')).toBe(true);
  });

  it('two-factor seeds from both old formats still produce valid codes', async () => {
    const r = await app.inject({ method: 'POST', url: '/api/auth/login', headers: { origin: ORIGIN }, payload: { email: 'tech1@weststarmsp.com', password: 'Tech-Password-456!' } });
    expect(r.json().mfaRequired).toBe(true);
    const a = await agentFrom(app, String(r.headers['set-cookie']).split(';')[0]);
    expect((await a.send('POST', '/api/auth/mfa', { code: authenticator.generate('KRSXG5CTMVRXEZLU') })).status).toBe(200);
  });

  it('Wi-Fi passwords, ISP accounts and HR secrets decrypt with the new key', async () => {
    const a = await signIn(app, 'casey@weststarmsp.com', 'Old-Password-123!');
    const nets = (await a.get('/api/r/networks')).body.rows;
    const ftc = nets.find((n: any) => n.name === 'franklin.local');
    expect((await a.send('POST', `/api/r/networks/${ftc.id}/reveal/wifi_password`)).body.value).toBe('Wifi-Pass-2026!');
    expect((await a.send('POST', `/api/r/networks/${ftc.id}/reveal/isp_account`)).body.value).toBe('ACCT-778899');
    const drd = nets.find((n: any) => n.name === 'drd.local');
    expect((await a.send('POST', `/api/r/networks/${drd.id}/reveal/wifi_password`)).body.value).toBe('plaintext-old-wifi');
    const emp = (await a.get('/api/r/employees')).body.rows[0];
    expect((await a.send('POST', `/api/r/employees/${emp.id}/reveal/ssn`)).body.value).toBe('123-45-6789');
    expect((await a.send('POST', `/api/r/employees/${emp.id}/reveal/bank_account`)).body.value).toBe('000123456789');
  });

  it('archived users cannot sign in', async () => {
    const r = await app.inject({ method: 'POST', url: '/api/auth/login', headers: { origin: ORIGIN }, payload: { email: 'old@weststarmsp.com', password: 'whatever-789' } });
    expect(r.statusCode).toBe(401);
  });

  it('carries over line items, time and client alerts', async () => {
    const a = await signIn(app, 'casey@weststarmsp.com', 'Old-Password-123!');
    const inv = (await a.get('/api/r/invoices')).body.rows.find((x: any) => x.number === 'INV-2291');
    expect(inv.status).toBe('Overdue');
    expect((await a.get(`/api/r/invoices/${inv.id}`)).body.items).toHaveLength(1);
    const t = (await a.get('/api/tickets?filter=all')).body.rows.find((x: any) => x.number === 'T-10476');
    const d = await a.get(`/api/tickets/${t.id}`);
    expect(d.body.minutes).toBe(105); // 1.5 h entry + 0.25 h on a reply
    expect(d.body.client.account_alert).toBe('Call Maria before any on-site visit');
    expect(d.body.messages.map((m: any) => m.kind)).toEqual(['reply', 'reply', 'note']);
  });
});
