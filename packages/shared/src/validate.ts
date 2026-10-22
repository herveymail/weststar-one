import { z } from 'zod';
import type { Field, Resource } from './modules';

const DATE = /^\d{4}-\d{2}-\d{2}$/;

/** zod schema for one field's value as sent by a form (strings for most things, '' = empty). */
export function fieldSchema(f: Field): z.ZodTypeAny {
  const max = f.max ?? (f.type === 'textarea' || f.type === 'secret' ? 20000 : 500);
  let s: z.ZodTypeAny;
  switch (f.type) {
    case 'int': s = z.coerce.number().int().min(-1_000_000_000).max(1_000_000_000); break;
    case 'decimal': case 'money': s = z.coerce.number().finite().min(-1e11).max(1e11); break;
    case 'bool': s = z.union([z.boolean(), z.enum(['true', 'false']).transform((v) => v === 'true')]); break;
    case 'date': s = z.string().regex(DATE, 'Use the format YYYY-MM-DD'); break;
    case 'datetime': s = z.string().max(40).refine((v) => !Number.isNaN(Date.parse(v)), 'Not a valid date and time'); break;
    case 'ref': s = z.coerce.number().int().positive(); break;
    case 'email': s = z.string().trim().max(254).email('Not a valid email address'); break;
    case 'url': s = z.string().trim().max(500).url('Not a valid web address').refine((v) => /^https?:\/\//i.test(v), 'Must start with http:// or https://'); break;
    case 'select': s = z.enum((f.options ?? ['']) as [string, ...string[]]); break;
    default: s = z.string().max(max);
  }
  const empty = z.union([z.literal(''), z.null(), z.undefined()]).transform(() => null);
  return f.required ? s : z.union([empty, s]);
}

/** Schema for creating (all required fields present) or updating (everything optional). */
export function resourceSchema(r: Resource, mode: 'create' | 'update') {
  const shape: Record<string, z.ZodTypeAny> = {};
  for (const f of r.fields) {
    if (f.readOnly) continue;
    const fs = fieldSchema(f);
    shape[f.key] = mode === 'update' || !f.required ? fs.optional() : fs;
  }
  return z.object(shape).strict();
}

export const lineItemSchema = z.object({
  description: z.string().trim().min(1).max(500),
  qty: z.coerce.number().finite().min(-1e6).max(1e6).default(1),
  rate: z.coerce.number().finite().min(-1e9).max(1e9).default(0),
  taxable: z.boolean().default(true),
}).strict();

export const passwordRule = z.string().min(12, 'Use at least 12 characters').max(200);
