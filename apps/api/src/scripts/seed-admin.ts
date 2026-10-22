/**
 * Create (or reset) the first admin account:
 *   pnpm seed:admin --email casey@weststarmsp.com --name "Casey"
 * A random password is printed once; you must change it at first sign-in.
 */
import { sql, eq } from 'drizzle-orm';
import { randomBytes } from 'node:crypto';
import { db, closeDb } from '../db';
import { users } from '../db/schema';
import { hashPassword } from '../lib/passwords';
import { runMigrations } from './migrate';

function arg(name: string) { const i = process.argv.indexOf('--' + name); return i > 0 ? process.argv[i + 1] : undefined; }

async function main() {
  const email = (arg('email') ?? '').trim().toLowerCase();
  const name = arg('name') ?? 'Administrator';
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) throw new Error('Pass --email you@company.com');
  await runMigrations();
  const password = randomBytes(12).toString('base64url');
  const hash = await hashPassword(password);
  const [existing] = await db().select().from(users).where(sql`lower(${users.email}) = ${email}`);
  if (existing) {
    await db().update(users).set({ password_hash: hash, role: 'admin', must_change_password: true, archived_at: null, failed_logins: 0, locked_until: null }).where(eq(users.id, existing.id));
  } else {
    await db().insert(users).values({ email, name, role: 'admin', hr_access: true, password_hash: hash, must_change_password: true });
  }
  console.log(`\nAdmin ready: ${email}\nTemporary password (shown once): ${password}\nYou will be asked to choose a new password and set up two-factor sign-in.\n`);
  await closeDb();
}
main().catch(async (e) => { console.error(e.message ?? e); await closeDb(); process.exit(1); });
