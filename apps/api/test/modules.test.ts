import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { RESOURCES } from '@ws/shared';
import { resetDb, makeApp, done, addUser, signIn, type Agent } from './helpers';
import { db } from '../src/db';
import { auditLog, resourceTables } from '../src/db/schema';
import { setSetting } from '../src/lib/util';

let app: FastifyInstance;
let admin: Agent, tech: Agent, viewer: Agent, hr: Agent;
let clientId: number;

beforeAll(async () => {
  await resetDb(); app = await makeApp();
  await setSetting('security.require_mfa', 'nobody', false, null);
  await addUser('admin@x.com', 'admin'); await addUser('tech@x.com', 'tech'); await addUser('viewer@x.com', 'viewer');
  await addUser('hr@x.com', 'tech', 'a-long-test-password', { hr_access: true });
  admin = await signIn(app, 'admin@x.com'); tech = await signIn(app, 'tech@x.com'); viewer = await signIn(app, 'viewer@x.com'); hr = await signIn(app, 'hr@x.com');
  clientId = (await admin.send('POST', '/api/r/clients', { data: { name: 'Franklin Title Co.' } })).body.row.id;
});
afterAll(async () => { await done(app); });

describe('every module in the menu has a working API', () => {
  for (const r of RESOURCES.filter((x) => !x.hidden)) {
    it(`${r.label}: list loads for an admin`, async () => {
      const res = await admin.get(`/api/r/${r.id}`);
      expect(res.status).toBe(200);
      expect(Array.isArray(res.body.rows)).toBe(true);
    });
  }
});

describe('create / edit / archive', () => {
  it('validates input and returns field errors', async () => {
    const r = await admin.send('POST', '/api/r/contacts', { data: { client_id: clientId, name: 'Maria', email: 'not-an-email' } });
    expect(r.status).toBe(400);
    expect(r.body.details[0].field).toContain('email');
  });

  it('rejects fields the module does not have', async () => {
    const r = await admin.send('POST', '/api/r/clients', { data: { name: 'x', is_admin: true } });
    expect(r.status).toBe(400);
  });

  it('ignores a malicious sort parameter', async () => {
    const r = await admin.get('/api/r/clients?sort=name;DROP TABLE clients&dir=asc');
    expect(r.status).toBe(200);
    expect((await admin.get('/api/r/clients')).body.total).toBeGreaterThan(0);
  });

  it('treats search text literally', async () => {
    const r = await admin.get(`/api/r/clients?q=${encodeURIComponent("%' OR 1=1 --")}`);
    expect(r.status).toBe(200);
    expect(r.body.total).toBe(0);
  });

  it('edits and records what changed in the audit log', async () => {
    const r = await admin.send('PATCH', `/api/r/clients/${clientId}`, { data: { city: 'El Paso' } });
    expect(r.status).toBe(200);
    const rows = await db().select().from(auditLog);
    const entry = rows.find((x) => x.entity === 'clients' && x.action === 'update');
    expect((entry!.changes as any).city.to).toBe('El Paso');
  });

  it('archives instead of deleting, and only managers may archive', async () => {
    const c = (await admin.send('POST', '/api/r/vendors', { data: { name: 'Pax8' } })).body.row;
    expect((await tech.send('DELETE', `/api/r/vendors/${c.id}`)).status).toBe(403);
    expect((await admin.send('DELETE', `/api/r/vendors/${c.id}`)).status).toBe(200);
    expect((await admin.get('/api/r/vendors')).body.rows.find((x: any) => x.id === c.id)).toBeUndefined();
    expect((await admin.get('/api/r/vendors?archived=1')).body.rows.find((x: any) => x.id === c.id)).toBeDefined();
  });

  it('numbers invoices and computes totals from line items', async () => {
    const r = await admin.send('POST', '/api/r/invoices', {
      data: { client_id: clientId, invoice_date: '2026-10-01', due_date: '2026-10-31', tax_rate: 8.25 },
      items: [{ description: 'Managed', qty: 1, rate: 2000 }, { description: 'Labor', qty: 2, rate: 75, taxable: false }],
    });
    expect(r.status).toBe(200);
    expect(r.body.row.number).toBe('INV-1001');
    const d = await admin.get(`/api/r/invoices/${r.body.row.id}`);
    expect(d.body.row.subtotal).toBe('2150.00');
    expect(d.body.row.tax_amount).toBe('165.00');
    expect(d.body.row.total).toBe('2315.00');
    // The browser cannot set the total itself.
    const forged = await admin.send('PATCH', `/api/r/invoices/${r.body.row.id}`, { data: { total: 1 } });
    expect(forged.status).toBe(400);
  });
});

describe('permissions', () => {
  it('techs cannot see billing; viewers cannot edit', async () => {
    expect((await tech.get('/api/r/invoices')).status).toBe(403);
    expect((await viewer.get('/api/r/clients')).status).toBe(200);
    expect((await viewer.send('POST', '/api/r/clients', { data: { name: 'nope' } })).status).toBe(403);
  });

  it('H/R needs HR access, regardless of role', async () => {
    expect((await tech.get('/api/r/employees')).status).toBe(403);
    expect((await hr.get('/api/r/employees')).status).toBe(200);
  });

  it('time off is private: techs only see their own requests and cannot approve them', async () => {
    const mine = await tech.send('POST', '/api/r/pto', { data: { starts_on: '2026-12-22', ends_on: '2026-12-26', hours: 24, status: 'Approved' } });
    expect(mine.status).toBe(200);
    expect(mine.body.row.status).toBe('Pending');
    const other = await viewer.get('/api/r/pto');
    expect(other.body.rows).toHaveLength(0);
    expect((await viewer.get(`/api/r/pto/${mine.body.row.id}`)).status).toBe(404);
    expect((await hr.get('/api/r/pto')).body.rows).toHaveLength(1);
  });
});

describe('encrypted fields', () => {
  it('never returns secrets in lists, stores them encrypted, and logs every reveal', async () => {
    const n = await admin.send('POST', '/api/r/networks', { data: { client_id: clientId, name: 'Office', wifi_password: 'Wifi-Pass-2026!' } });
    expect(n.body.row.wifi_password).toBeNull();
    expect(n.body.row.wifi_password__set).toBe(true);
    const list = await admin.get('/api/r/networks');
    expect(JSON.stringify(list.body)).not.toContain('Wifi-Pass-2026!');
    const t = resourceTables.networks;
    const raw = await db().select({ v: t.wifi_password }).from(t);
    expect(String(raw[0].v)).toMatch(/^v1:/);
    expect((await viewer.send('POST', `/api/r/networks/${n.body.row.id}/reveal/wifi_password`)).status).toBe(403);
    const shown = await tech.send('POST', `/api/r/networks/${n.body.row.id}/reveal/wifi_password`);
    expect(shown.body.value).toBe('Wifi-Pass-2026!');
    const audits = await db().select().from(auditLog);
    expect(audits.some((a) => a.action === 'reveal')).toBe(true);
    expect(JSON.stringify(audits)).not.toContain('Wifi-Pass-2026!');
  });

  it('a blank secret in an edit keeps the saved one', async () => {
    const n = (await admin.get('/api/r/networks')).body.rows[0];
    await admin.send('PATCH', `/api/r/networks/${n.id}`, { data: { wifi_password: '', notes: 'x' } });
    const shown = await admin.send('POST', `/api/r/networks/${n.id}/reveal/wifi_password`);
    expect(shown.body.value).toBe('Wifi-Pass-2026!');
  });

  it('HR secrets need HR manage access to reveal', async () => {
    const e = await hr.send('POST', '/api/r/employees', { data: { name: 'Tech One', ssn: '123-45-6789' } });
    expect(e.status).toBe(200);
    expect((await tech.send('POST', `/api/r/employees/${e.body.row.id}/reveal/ssn`)).status).toBe(403);
    expect((await hr.send('POST', `/api/r/employees/${e.body.row.id}/reveal/ssn`)).body.value).toBe('123-45-6789');
  });
});

describe('settings', () => {
  it('only accepts known settings and never sends secrets back', async () => {
    expect((await admin.send('PUT', '/api/settings', { 'made.up': 'x' })).status).toBe(400);
    expect((await admin.send('PUT', '/api/settings', { 'stripe.secret_key': 'sk_live_abc', 'company.name': 'Weststar MSP' })).status).toBe(200);
    const s = await admin.get('/api/settings');
    expect(s.body['company.name']).toBe('Weststar MSP');
    expect(s.body['stripe.secret_key']).toEqual({ set: true });
    expect(JSON.stringify(s.body)).not.toContain('sk_live_abc');
    expect((await tech.get('/api/settings')).status).toBe(403);
  });
});
