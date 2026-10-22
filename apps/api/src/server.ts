import { buildApp } from './app';
import { config } from './config';
import { runMigrations } from './scripts/migrate';
import { closeDb } from './db';

async function main() {
  const c = config();
  await runMigrations();
  const app = await buildApp();
  const stop = async () => { await app.close(); await closeDb(); process.exit(0); };
  process.on('SIGINT', stop); process.on('SIGTERM', stop);
  await app.listen({ port: c.PORT, host: c.HOST });
}
main().catch((e) => { console.error(e); process.exit(1); });
