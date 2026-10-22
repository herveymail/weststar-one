import { createCipheriv, createDecipheriv, createHash, createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { config } from '../config';

/**
 * Secrets at rest: AES-256-GCM with a random 96-bit IV.
 * Format: "v1:<base64(iv | tag | ciphertext)>". The key comes from APP_ENCRYPTION_KEY; keys listed in
 * APP_ENCRYPTION_KEYS_OLD still decrypt so the key can be rotated (re-save to re-encrypt).
 */
function keys(): Buffer[] {
  const c = config();
  const old = c.APP_ENCRYPTION_KEYS_OLD.split(',').map((s) => s.trim()).filter(Boolean);
  return [c.APP_ENCRYPTION_KEY, ...old].map((k) => Buffer.from(k, 'base64'));
}

export function encrypt(plain: string): string {
  if (plain === '') return '';
  const iv = randomBytes(12);
  const cipher = createCipheriv('aes-256-gcm', keys()[0], iv);
  const ct = Buffer.concat([cipher.update(plain, 'utf8'), cipher.final()]);
  return 'v1:' + Buffer.concat([iv, cipher.getAuthTag(), ct]).toString('base64');
}

export function decrypt(stored: string | null | undefined): string {
  if (!stored) return '';
  if (!stored.startsWith('v1:')) throw new Error('Unknown ciphertext format');
  const raw = Buffer.from(stored.slice(3), 'base64');
  const iv = raw.subarray(0, 12), tag = raw.subarray(12, 28), ct = raw.subarray(28);
  for (const key of keys()) {
    try {
      const d = createDecipheriv('aes-256-gcm', key, iv);
      d.setAuthTag(tag);
      return Buffer.concat([d.update(ct), d.final()]).toString('utf8');
    } catch { /* try the next key */ }
  }
  throw new Error('Could not decrypt value with any configured key');
}

export const randomToken = (bytes = 32) => randomBytes(bytes).toString('base64url');
export const sha256 = (s: string) => createHash('sha256').update(s).digest('hex');

/** Keyed hash for things like recovery codes, so a database dump alone can't be brute-forced. */
export const keyedHash = (s: string) => createHmac('sha256', keys()[0]).update(s).digest('hex');

export function safeEqual(a: string, b: string): boolean {
  const ab = Buffer.from(a), bb = Buffer.from(b);
  return ab.length === bb.length && timingSafeEqual(ab, bb);
}
