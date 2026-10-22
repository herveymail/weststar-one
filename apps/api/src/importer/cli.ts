/**
 * Import everything from the old PHP Weststar One.
 *
 *   pnpm import:legacy --old-config /var/www/myflow/config/config.php [--dry-run]
 *   pnpm import:legacy --mysql mysql://user:pass@host:3306/myflow --app-key '…' --encryption-key '…' [--dry-run]
 *
 * --old-config reads DB_HOST / DB_USER / DB_PASS / DB_NAME / APP_KEY / ENCRYPTION_KEY straight from the
 * old config file, so you don't have to copy secrets onto the command line (where they'd land in shell history).
 */
import fs from 'node:fs';
import { runImport } from './run';
import { parseOldConfig } from './legacy-crypto';
import { runMigrations } from '../scripts/migrate';
import { closeDb } from '../db';

const arg = (n: string) => { const i = process.argv.indexOf('--' + n); return i > 0 ? process.argv[i + 1] : undefined; };
const flag = (n: string) => process.argv.includes('--' + n);

async function main() {
  let mysqlUrl = arg('mysql'), appKey = arg('app-key') ?? process.env.OLD_APP_KEY, encKey = arg('encryption-key') ?? process.env.OLD_ENCRYPTION_KEY;
  const cfgPath = arg('old-config');
  if (cfgPath) {
    const c = parseOldConfig(fs.readFileSync(cfgPath, 'utf8'));
    const host = c.DB_HOST ?? 'localhost';
    mysqlUrl ??= `mysql://${encodeURIComponent(c.DB_USER ?? '')}:${encodeURIComponent(c.DB_PASS ?? '')}@${host.includes(':') ? host : host + ':3306'}/${encodeURIComponent(c.DB_NAME ?? '')}`;
    appKey ??= c.APP_KEY; encKey ??= c.ENCRYPTION_KEY;
  }
  if (!mysqlUrl) throw new Error('Pass --old-config /path/to/old/config/config.php, or --mysql mysql://user:pass@host/db');
  if (!appKey || !encKey) console.warn('⚠  Old APP_KEY / ENCRYPTION_KEY not given — 2FA seeds, Wi-Fi passwords and HR secrets will be skipped.');
  await runMigrations();
  const dryRun = flag('dry-run');
  const res = await runImport({ mysqlUrl, appKey: appKey ?? '', encryptionKey: encKey ?? '', dryRun });
  const warnings = res.steps.flatMap((s) => s.warnings.map((w) => `${s.name}: ${w}`));
  console.log(`\n${dryRun ? 'DRY RUN — nothing was saved.' : 'Import finished.'} Run #${res.runId}`);
  if (warnings.length) { console.log(`\n${warnings.length} warning(s):`); for (const w of warnings.slice(0, 50)) console.log('  - ' + w); if (warnings.length > 50) console.log(`  … and ${warnings.length - 50} more (see Settings › Import)`); }
  await closeDb();
}
main().catch(async (e) => { console.error('\nImport failed:', e.message ?? e); await closeDb(); process.exit(1); });
