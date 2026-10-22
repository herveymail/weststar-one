import { z } from 'zod';

/**
 * All configuration comes from environment variables (see .env.example).
 * The app refuses to start with a missing or weak secret instead of falling back to a default —
 * the old app silently used 'myflow_default_key' when APP_KEY was unset.
 */
const schema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),
  PORT: z.coerce.number().int().default(3000),
  HOST: z.string().default('127.0.0.1'),
  DATABASE_URL: z.string().url(),
  /** Public URL people use, e.g. https://one.weststarmsp.com — used for the Origin check and cookies. */
  APP_URL: z.string().url(),
  /** 32 random bytes, base64. Generate with: openssl rand -base64 32 */
  APP_ENCRYPTION_KEY: z.string().refine((v) => Buffer.from(v, 'base64').length === 32, 'APP_ENCRYPTION_KEY must be 32 bytes, base64 encoded (openssl rand -base64 32)'),
  /** Optional older keys (comma separated) still accepted for decryption during a key rotation. */
  APP_ENCRYPTION_KEYS_OLD: z.string().optional().default(''),
  /** Serve the built web app from apps/web/dist. */
  SERVE_WEB: z.enum(['true', 'false']).default('true'),
  TRUST_PROXY: z.enum(['true', 'false']).default('false'),
  LOG_LEVEL: z.enum(['fatal', 'error', 'warn', 'info', 'debug', 'trace', 'silent']).default('info'),
});

export type Config = z.infer<typeof schema>;

let cached: Config | null = null;
export function config(): Config {
  if (cached) return cached;
  const parsed = schema.safeParse(process.env);
  if (!parsed.success) {
    const msg = parsed.error.issues.map((i) => `  ${i.path.join('.')}: ${i.message}`).join('\n');
    throw new Error(`Configuration problem — fix these environment variables:\n${msg}`);
  }
  cached = parsed.data;
  return cached;
}

export const isProd = () => config().NODE_ENV === 'production';
