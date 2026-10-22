import fs from 'node:fs';
import path from 'node:path';
// Load apps/api/.env.test (CI writes its own).
const p = path.resolve(__dirname, '../.env.test');
if (fs.existsSync(p)) for (const line of fs.readFileSync(p, 'utf8').split('\n')) {
  const m = line.match(/^([A-Z0-9_]+)=(.*)$/);
  if (m && process.env[m[1]] === undefined) process.env[m[1]] = m[2];
}
