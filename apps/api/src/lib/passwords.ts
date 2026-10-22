import { hash, verify } from '@node-rs/argon2';
import bcrypt from 'bcryptjs';

// OWASP-recommended argon2id parameters (19 MiB, 2 passes).
const OPTS = { memoryCost: 19456, timeCost: 2, parallelism: 1, outputLen: 32 } as const;

export const hashPassword = (pw: string) => hash(pw, { ...OPTS, algorithm: 2 /* Argon2id */ });

/** Returns { ok, upgrade } — upgrade is true for bcrypt hashes imported from the old PHP app. */
export async function verifyPassword(stored: string, pw: string): Promise<{ ok: boolean; upgrade: boolean }> {
  if (stored.startsWith('$argon2')) {
    try { return { ok: await verify(stored, pw), upgrade: false }; } catch { return { ok: false, upgrade: false }; }
  }
  if (/^\$2[aby]\$/.test(stored)) {
    // PHP writes $2y$; bcryptjs understands it as $2b$.
    const ok = await bcrypt.compare(pw, stored.replace(/^\$2y\$/, '$2b$'));
    return { ok, upgrade: ok };
  }
  return { ok: false, upgrade: false };
}

/** A hash to compare against when the email doesn't exist, so timing doesn't reveal valid accounts. */
let dummy: string | null = null;
export async function dummyVerify(pw: string) {
  dummy ??= await hashPassword('not-a-real-password-' + Math.random());
  try { await verify(dummy, pw); } catch { /* ignore */ }
}
