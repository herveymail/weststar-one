import { migrate } from 'drizzle-orm/postgres-js/migrator';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { db, closeDb } from '../db';

/** Applies the SQL migrations in apps/api/migrations. Safe to run on every deploy. */
export async function runMigrations() {
  const here = path.dirname(fileURLToPath(import.meta.url));
  await migrate(db(), { migrationsFolder: path.resolve(here, '../../migrations') });
}

if (process.argv[1] && fileURLToPath(import.meta.url) === path.resolve(process.argv[1])) {
  runMigrations().then(async () => { console.log('Database is up to date.'); await closeDb(); })
    .catch(async (e) => { console.error(e); await closeDb(); process.exit(1); });
}
