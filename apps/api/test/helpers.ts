import type { FastifyInstance } from 'fastify';
import postgres from 'postgres';
import { buildApp } from '../src/app';
import { db, closeDb } from '../src/db';
import { users } from '../src/db/schema';
import { hashPassword } from '../src/lib/passwords';
import { runMigrations } from '../src/scripts/migrate';

export const ORIGIN = 'http://localhost:3000';

/** Fresh empty database (drops and re-creates the public schema of the TEST database). */
export async function resetDb() {
  const url = process.env.DATABASE_URL!;
  if (!/_test\b/.test(url)) throw new Error('Refusing to reset a database whose name does not end in _test');
  const sql = postgres(url, { max: 1, onnotice: () => {} });
  await sql.unsafe('DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS drizzle CASCADE;');
  await sql.end();
  await closeDb();
  await runMigrations();
}

export async function makeApp(): Promise<FastifyInstance> { return buildApp({ logger: false }); }
export async function done(app: FastifyInstance) { await app.close(); await closeDb(); }

export async function addUser(email: string, role: 'admin' | 'manager' | 'tech' | 'viewer', password = 'a-long-test-password', extra: Partial<typeof users.$inferInsert> = {}) {
  const [u] = await db().insert(users).values({ email, name: email.split('@')[0], role, password_hash: await hashPassword(password), ...extra }).returning();
  return u;
}

export interface Agent { cookie: string; csrf: string; get: (url: string) => Promise<any>; send: (method: string, url: string, payload?: unknown) => Promise<any> }

/** Sign in and return a tiny client that carries the cookie + CSRF token like the browser does. */
export async function signIn(app: FastifyInstance, email: string, password = 'a-long-test-password'): Promise<Agent> {
  const r = await app.inject({ method: 'POST', url: '/api/auth/login', headers: { origin: ORIGIN }, payload: { email, password } });
  if (r.statusCode !== 200) throw new Error(`login failed ${r.statusCode} ${r.body}`);
  return agentFrom(app, String(r.headers['set-cookie']).split(';')[0]);
}

export async function agentFrom(app: FastifyInstance, cookie: string): Promise<Agent> {
  const me = (await app.inject({ method: 'GET', url: '/api/auth/me', headers: { cookie } })).json();
  const a: Agent = {
    cookie, csrf: me.csrfToken,
    get: async (url) => { const r = await app.inject({ method: 'GET', url, headers: { cookie } }); return { status: r.statusCode, body: safeJson(r.body) }; },
    send: async (method, url, payload) => {
      const r = await app.inject({ method: method as never, url, headers: { cookie, origin: ORIGIN, 'x-csrf-token': a.csrf }, payload: payload as never });
      return { status: r.statusCode, body: safeJson(r.body), headers: r.headers };
    },
  };
  return a;
}
const safeJson = (s: string) => { try { return JSON.parse(s); } catch { return s; } };
