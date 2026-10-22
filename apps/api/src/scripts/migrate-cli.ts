import { runMigrations } from './migrate';
import { closeDb } from '../db';

runMigrations()
  .then(async () => { console.log('Database is up to date.'); await closeDb(); })
  .catch(async (e) => { console.error(e); await closeDb(); process.exit(1); });
