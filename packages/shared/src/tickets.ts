import { z } from 'zod';

export const TICKET_PRIORITIES = ['Critical', 'High', 'Medium', 'Low'] as const;
export const TICKET_STATUSES = ['New', 'Open', 'Waiting on client', 'Waiting on vendor', 'Scheduled', 'Resolved', 'Closed'] as const;
export const OPEN_STATUSES = ['New', 'Open', 'Waiting on client', 'Waiting on vendor', 'Scheduled'] as const;
/** SLA clock is paused while we wait on someone else. */
export const PAUSED_STATUSES = ['Waiting on client', 'Waiting on vendor'] as const;
export const TICKET_SOURCES = ['Manual', 'Email', 'Portal', 'Phone', 'Alert', 'Import'] as const;
export const MESSAGE_KINDS = ['reply', 'note', 'event'] as const;

export type TicketPriority = (typeof TICKET_PRIORITIES)[number];
export type TicketStatus = (typeof TICKET_STATUSES)[number];

/** Default response targets in minutes when the client has none of its own. */
export const DEFAULT_RESPONSE_MINUTES: Record<TicketPriority, number> = { Critical: 60, High: 240, Medium: 1440, Low: 4320 };

const opt = (s: z.ZodTypeAny) => z.union([z.literal('').transform(() => null), z.null(), s]).optional();

export const ticketCreateSchema = z.object({
  subject: z.string().trim().min(1, 'Add a subject').max(255),
  details: z.string().max(50000).optional().default(''),
  client_id: opt(z.coerce.number().int().positive()),
  contact_id: opt(z.coerce.number().int().positive()),
  contact_name: z.string().max(150).optional(),
  contact_email: opt(z.string().trim().email().max(254)),
  priority: z.enum(TICKET_PRIORITIES).default('Medium'),
  category: z.string().max(100).optional(),
  assigned_to: opt(z.coerce.number().int().positive()),
  source: z.enum(TICKET_SOURCES).default('Manual'),
  billable: z.boolean().default(true),
}).strict();

export const ticketUpdateSchema = z.object({
  subject: z.string().trim().min(1).max(255).optional(),
  priority: z.enum(TICKET_PRIORITIES).optional(),
  status: z.enum(TICKET_STATUSES).optional(),
  category: z.string().max(100).nullable().optional(),
  client_id: opt(z.coerce.number().int().positive()),
  contact_id: opt(z.coerce.number().int().positive()),
  assigned_to: opt(z.coerce.number().int().positive()),
  billable: z.boolean().optional(),
  due_date: opt(z.string().regex(/^\d{4}-\d{2}-\d{2}$/)),
}).strict();

export const ticketMessageSchema = z.object({
  kind: z.enum(['reply', 'note']),
  body: z.string().trim().min(1, 'Write something first').max(50000),
  minutes: z.coerce.number().int().min(0).max(24 * 60).optional().default(0),
  billable: z.boolean().optional().default(true),
}).strict();

export const timeEntrySchema = z.object({
  minutes: z.coerce.number().int().min(1).max(24 * 60),
  work_type: z.enum(['Remote', 'On-site', 'Phone', 'Travel', 'Project']).default('Remote'),
  description: z.string().max(2000).optional().default(''),
  billable: z.boolean().default(true),
  date: z.string().regex(/^\d{4}-\d{2}-\d{2}$/).optional(),
}).strict();
