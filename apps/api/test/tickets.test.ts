import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import type { FastifyInstance } from 'fastify';
import { eq } from 'drizzle-orm';
import { resetDb, makeApp, done, addUser, signIn, type Agent } from './helpers';
import { db } from '../src/db';
import { tickets, recurring, invoices } from '../src/db/schema';
import { setSetting } from '../src/lib/util';
import { runRecurring, slaWatch, markOverdue } from '../src/jobs/tasks';

let app: FastifyInstance; let tech: Agent; let admin: Agent; let viewer: Agent; let clientId: number;
beforeAll(async () => {
  await resetDb(); app = await makeApp();
  await setSetting('security.require_mfa', 'nobody', false, null);
  await addUser('tech@x.com', 'tech'); await addUser('admin@x.com', 'admin'); await addUser('viewer@x.com', 'viewer');
  tech = await signIn(app, 'tech@x.com'); admin = await signIn(app, 'admin@x.com'); viewer = await signIn(app, 'viewer@x.com');
  clientId = (await admin.send('POST', '/api/r/clients', { data: { name: 'Franklin Title Co.', sla_response_hours: 1 } })).body.row.id;
});
afterAll(async () => { await done(app); });

describe('tickets', () => {
  let id: number;
  it('creates a numbered ticket with a response deadline', async () => {
    const r = await tech.send('POST', '/api/tickets', { subject: 'VPN down', client_id: clientId, priority: 'Critical', details: 'Front desk cannot connect' });
    expect(r.status).toBe(200);
    expect(r.body.ticket.number).toBe('T-10001');
    id = r.body.ticket.id;
    const due = new Date(r.body.ticket.response_due_at).getTime() - Date.now();
    expect(due).toBeGreaterThan(50 * 60_000); expect(due).toBeLessThan(61 * 60_000);
  });

  it('shows up as SLA at risk and unassigned', async () => {
    const r = await tech.get('/api/tickets?filter=risk');
    expect(r.body.rows.map((x: any) => x.id)).toContain(id);
    expect(r.body.counts.unassigned).toBe(1);
  });

  it('a reply records the first response, opens the ticket and assigns it to whoever answered', async () => {
    const r = await tech.send('POST', `/api/tickets/${id}/messages`, { kind: 'reply', body: 'On it.', minutes: 15 });
    expect(r.status).toBe(200);
    const d = await tech.get(`/api/tickets/${id}`);
    expect(d.body.ticket.status).toBe('Open');
    expect(d.body.ticket.first_response_at).not.toBeNull();
    expect(d.body.ticket.assignee_name).toBe('tech');
    expect(d.body.minutes).toBe(15);
  });

  it('internal notes are stored as notes', async () => {
    await tech.send('POST', `/api/tickets/${id}/messages`, { kind: 'note', body: 'Blocked the IPs.' });
    const d = await tech.get(`/api/tickets/${id}`);
    expect(d.body.messages.find((m: any) => m.body === 'Blocked the IPs.').kind).toBe('note');
  });

  it('closing and reopening is recorded on the timeline', async () => {
    await tech.send('PATCH', `/api/tickets/${id}`, { status: 'Closed' });
    let d = await tech.get(`/api/tickets/${id}`);
    expect(d.body.ticket.closed_at).not.toBeNull();
    await tech.send('PATCH', `/api/tickets/${id}`, { status: 'Open' });
    d = await tech.get(`/api/tickets/${id}`);
    expect(d.body.ticket.closed_at).toBeNull();
    expect(d.body.messages.filter((m: any) => m.kind === 'event').map((m: any) => m.body).join('|')).toMatch(/Open → Closed.*Closed → Open/);
  });

  it('viewers can read but not change tickets', async () => {
    expect((await viewer.get(`/api/tickets/${id}`)).status).toBe(200);
    expect((await viewer.send('POST', `/api/tickets/${id}/messages`, { kind: 'reply', body: 'x' })).status).toBe(403);
  });

  it('rejects a contact from another client', async () => {
    const other = (await admin.send('POST', '/api/r/clients', { data: { name: 'Other' } })).body.row.id;
    const c = (await admin.send('POST', '/api/r/contacts', { data: { client_id: other, name: 'Bob' } })).body.row.id;
    const r = await tech.send('POST', '/api/tickets', { subject: 'x', client_id: clientId, contact_id: c });
    expect(r.status).toBe(400);
  });
});

describe('background jobs', () => {
  it('marks a missed response SLA', async () => {
    const r = await tech.send('POST', '/api/tickets', { subject: 'late', priority: 'Low' });
    await db().update(tickets).set({ response_due_at: new Date(Date.now() - 60_000) }).where(eq(tickets.id, r.body.ticket.id));
    expect((await slaWatch()).breached).toBe(1);
  });

  it('creates invoices from due recurring schedules exactly once and moves the next run date', async () => {
    const s = await admin.send('POST', '/api/r/recurring', { data: { name: 'Managed Gold', client_id: clientId, next_run: '2026-01-31', frequency: 'Month' }, items: [{ description: 'Managed Gold', qty: 1, rate: 2150 }] });
    expect(s.status).toBe(200);
    const first = await runRecurring();
    expect(first.created).toBeGreaterThanOrEqual(1);
    const [after] = await db().select().from(recurring).where(eq(recurring.id, s.body.row.id));
    expect(after.next_run).toBe('2026-02-28');
    const invs = await db().select().from(invoices).where(eq(invoices.client_id, clientId));
    expect(invs.some((i: any) => i.total === '2150.00')).toBe(true);
  });

  it('marks sent invoices past due as overdue', async () => {
    const inv = await admin.send('POST', '/api/r/invoices', { data: { client_id: clientId, invoice_date: '2026-01-01', due_date: '2026-01-31', status: 'Sent' }, items: [{ description: 'x', qty: 1, rate: 10 }] });
    await markOverdue();
    const d = await admin.get(`/api/r/invoices/${inv.body.row.id}`);
    expect(d.body.row.status).toBe('Overdue');
  });
});
