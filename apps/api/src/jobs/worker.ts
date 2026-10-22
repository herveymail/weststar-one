/**
 * Background worker — replaces the old app's 42 separate cron scripts with one process.
 * Uses pg-boss (a job queue stored in Postgres): each job is scheduled, retried on failure and
 * logged in one place. Run it next to the web server:  pnpm --filter @ws/api worker
 */
import PgBoss from 'pg-boss';
import { config } from '../config';
import { TASKS } from './tasks';
import { closeDb } from '../db';
import { setSetting } from '../lib/util';

async function main() {
  const boss = new PgBoss({ connectionString: config().DATABASE_URL, schema: 'pgboss' });
  boss.on('error', (e) => console.error('[worker]', e));
  await boss.start();
  for (const [name, t] of Object.entries(TASKS)) {
    await boss.createQueue(name, { name, retryLimit: 3, retryDelay: 60, retryBackoff: true });
    await boss.schedule(name, t.cron, {}, { tz: 'America/Denver' });
    await boss.work(name, async () => {
      const started = Date.now();
      const result = await t.run();
      await setSetting(`jobs.last.${name}`, JSON.stringify({ at: new Date().toISOString(), ms: Date.now() - started, result }), false, null);
      console.log(`[worker] ${name}`, JSON.stringify(result));
    });
  }
  console.log('[worker] running:', Object.keys(TASKS).join(', '));
  const stop = async () => { await boss.stop({ graceful: true }); await closeDb(); process.exit(0); };
  process.on('SIGINT', stop); process.on('SIGTERM', stop);
}
main().catch((e) => { console.error(e); process.exit(1); });
