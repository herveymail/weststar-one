import postgres from 'postgres';
import { drizzle, type PostgresJsDatabase } from 'drizzle-orm/postgres-js';
import * as schema from './schema';
import { config } from '../config';

let client: ReturnType<typeof postgres> | null = null;
let instance: PostgresJsDatabase<typeof schema> | null = null;

export function db(): PostgresJsDatabase<typeof schema> {
  if (!instance) {
    client = postgres(config().DATABASE_URL, { max: 10, idle_timeout: 30, prepare: true, onnotice: () => {} });
    instance = drizzle(client, { schema });
  }
  return instance;
}
export type DB = PostgresJsDatabase<typeof schema>;
export type Tx = Parameters<Parameters<DB['transaction']>[0]>[0];

export async function closeDb() {
  if (client) await client.end({ timeout: 5 });
  client = null; instance = null;
}
