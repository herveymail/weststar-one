import { migrate } from 'drizzle-orm/postgres-js/migrator';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import fs from 'node:fs';
import { db, closeDb } from '../db';

/** Applies the SQL migrations in apps/api/migrations. Safe to run on every deploy. */
export async function runMigrations() {
  // Works from src/scripts (tsx) and from the bundled dist/ files.
  const here = path.dirname(fileURLToPath(import.meta.url));
  const folder = ['../../migrations', '../migrations', './migrations'].map((p) => path.resolve(here, p)).find((p) => fs.existsSync(path.join(p, 'meta', '_journal.json')));
  if (!folder) throw new Error('Could not find the migrations folder');
  await migrate(db(), { migrationsFolder: folder });
}
