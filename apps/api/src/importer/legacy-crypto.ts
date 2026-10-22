import { createDecipheriv, createHash } from 'node:crypto';

/**
 * Node ports of the old PHP app's three decryption routines, so the importer can read secrets
 * that were encrypted with the old APP_KEY / ENCRYPTION_KEY and re-encrypt them with the new key.
 *
 *  decryptValue()   includes/functions.php decrypt_value — AES-256-CBC, key = hex2bin(ENCRYPTION_KEY),
 *                   stored as base64( iv(16 raw bytes) . "::" . base64(ciphertext) ). Used for HR fields
 *                   and (with a "nenc:" prefix) client network Wi-Fi passwords / ISP accounts.
 *  decryptSetting() includes/security.php decrypt_setting —
 *                   "v2:" base64(iv12 . tag16 . ct), AES-256-GCM, key = sha256(APP_KEY) (raw)
 *                   legacy (no prefix): AES-256-CBC, key = APP_KEY string, iv = first 16 chars of sha256hex(APP_KEY)
 *                   Used for TOTP seeds and secret settings ("enc1:" prefix in the settings table).
 */

/** PHP's openssl_* functions NUL-pad a short key and cut a long one to the cipher's key length. */
function phpKey(raw: Buffer, len = 32): Buffer {
  if (raw.length === len) return raw;
  const out = Buffer.alloc(len);
  raw.copy(out, 0, 0, Math.min(len, raw.length));
  return out;
}

export function decryptValue(stored: string, encryptionKeyHex: string): string {
  if (!stored) return '';
  const data = Buffer.from(stored, 'base64');
  const sep = data.indexOf('::');
  if (sep < 0) throw new Error('not a decrypt_value payload');
  const iv = data.subarray(0, sep);
  const ct = Buffer.from(data.subarray(sep + 2).toString('latin1'), 'base64');
  if (iv.length !== 16) throw new Error('bad IV length');
  const key = phpKey(Buffer.from(encryptionKeyHex, 'hex'));
  const d = createDecipheriv('aes-256-cbc', key, iv);
  return Buffer.concat([d.update(ct), d.final()]).toString('utf8');
}

export function decryptNetSecret(stored: string | null | undefined, encryptionKeyHex: string): string {
  const s = String(stored ?? '');
  if (s === '') return '';
  if (!s.startsWith('nenc:')) return s; // old rows were plaintext
  return decryptValue(s.slice(5), encryptionKeyHex);
}

export function decryptSetting(stored: string, appKey: string): string {
  if (!stored) return '';
  if (stored.startsWith('v2:')) {
    const raw = Buffer.from(stored.slice(3), 'base64');
    if (raw.length < 29) throw new Error('short v2 payload');
    const key = createHash('sha256').update(appKey, 'utf8').digest();
    const d = createDecipheriv('aes-256-gcm', key, raw.subarray(0, 12));
    d.setAuthTag(raw.subarray(12, 28));
    return Buffer.concat([d.update(raw.subarray(28)), d.final()]).toString('utf8');
  }
  const iv = Buffer.from(createHash('sha256').update(appKey, 'utf8').digest('hex').slice(0, 16), 'latin1');
  const d = createDecipheriv('aes-256-cbc', phpKey(Buffer.from(appKey, 'utf8')), iv);
  return Buffer.concat([d.update(Buffer.from(stored, 'base64')), d.final()]).toString('utf8');
}

/** settings.setting_value may be "enc1:<encrypt_setting output>". */
export function decryptSettingValue(v: string, appKey: string): string {
  return v.startsWith('enc1:') ? decryptSetting(v.slice(5), appKey) : v;
}

/** Read APP_KEY, ENCRYPTION_KEY and DB_* from the old config/config.php. */
export function parseOldConfig(php: string): Record<string, string> {
  const out: Record<string, string> = {};
  const re = /define\(\s*['"]([A-Z_]+)['"]\s*,\s*(['"])((?:\\.|(?!\2).)*)\2\s*\)/g;
  for (const m of php.matchAll(re)) out[m[1]] = m[3].replace(/\\(['"\\])/g, '$1');
  return out;
}
