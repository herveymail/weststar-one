import Fastify, { type FastifyInstance } from 'fastify';
import cookie from '@fastify/cookie';
import helmet from '@fastify/helmet';
import rateLimit from '@fastify/rate-limit';
import fastifyStatic from '@fastify/static';
import { ZodError } from 'zod';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { config, isProd } from './config';
import { HttpError } from './lib/util';
import { sessionPlugin } from './auth/session';
import { authRoutes } from './auth/routes';
import { resourceRoutes } from './routes/resources';
import { ticketRoutes } from './routes/tickets';
import { adminRoutes } from './routes/admin';

export async function buildApp(opts: { logger?: boolean } = {}): Promise<FastifyInstance> {
  const c = config();
  const app = Fastify({
    logger: opts.logger === false ? false : {
      level: c.LOG_LEVEL,
      // Never write cookies, auth headers or passwords to the logs.
      redact: { paths: ['req.headers.cookie', 'req.headers.authorization', 'req.headers["x-csrf-token"]', 'body.password', 'body.current', 'body.next'], remove: true },
    },
    trustProxy: c.TRUST_PROXY === 'true',
    bodyLimit: 2 * 1024 * 1024,
    disableRequestLogging: false,
  });

  await app.register(helmet, {
    contentSecurityPolicy: {
      directives: {
        defaultSrc: ["'self'"],
        scriptSrc: ["'self'"],
        styleSrc: ["'self'", "'unsafe-inline'", 'https://fonts.googleapis.com'],
        fontSrc: ["'self'", 'https://fonts.gstatic.com'],
        imgSrc: ["'self'", 'data:'],
        connectSrc: ["'self'"],
        frameAncestors: ["'none'"],
        formAction: ["'self'"],
        baseUri: ["'self'"],
        objectSrc: ["'none'"],
        upgradeInsecureRequests: isProd() ? [] : null,
      },
    },
    hsts: isProd() ? { maxAge: 31536000, includeSubDomains: true } : false,
    referrerPolicy: { policy: 'same-origin' },
    crossOriginEmbedderPolicy: false,
  });
  await app.register(cookie);
  await app.register(rateLimit, { global: true, max: 600, timeWindow: '1 minute', allowList: [] });
  await app.register(sessionPlugin);

  app.setErrorHandler((err, req, reply) => {
    if (err instanceof ZodError) {
      return reply.code(400).send({ error: 'Some fields need attention.', details: err.issues.map((i) => ({ field: i.path.join('.'), message: i.message })) });
    }
    if (err instanceof HttpError) return reply.code(err.status).send({ error: err.message, ...(err.details ? { details: err.details } : {}) });
    const status = (err as { statusCode?: number }).statusCode;
    if (status && status < 500) return reply.code(status).send({ error: status === 429 ? 'Too many requests. Slow down and try again in a minute.' : (err as Error).message });
    // Postgres constraint errors → friendly messages, no internals.
    const code = (err as { code?: string }).code;
    if (code === '23503') return reply.code(400).send({ error: 'This record is linked to other records and cannot be changed that way.' });
    if (code === '23505') return reply.code(400).send({ error: 'That value is already used by another record.' });
    req.log.error(err);
    return reply.code(500).send({ error: 'Something went wrong on our side. It has been logged.' });
  });

  app.get('/api/health', async () => ({ ok: true }));
  await app.register(authRoutes);
  await app.register(resourceRoutes);
  await app.register(ticketRoutes);
  await app.register(adminRoutes);

  app.setNotFoundHandler((req, reply) => {
    if (req.url.startsWith('/api/') || req.url.startsWith('/assets/')) return reply.code(404).send({ error: 'Not found' });
    if (webRoot) return reply.header('Cache-Control', 'no-cache').type('text/html').sendFile('index.html');
    return reply.code(404).send('Not found');
  });

  // Serve the built React app.
  const here = path.dirname(fileURLToPath(import.meta.url));
  const candidate = path.resolve(here, '../../web/dist');
  const webRoot = c.SERVE_WEB === 'true' && fs.existsSync(path.join(candidate, 'index.html')) ? candidate : null;
  if (webRoot) {
    await app.register(fastifyStatic, {
      root: webRoot, prefix: '/', wildcard: true, index: ['index.html'], cacheControl: false,
      // Hashed build files can be cached forever; index.html must always be re-checked so a deploy shows up at once.
      setHeaders: (res, filePath) => res.header('Cache-Control', filePath.includes(`${path.sep}assets${path.sep}`) ? 'public, max-age=31536000, immutable' : 'no-cache'),
    });
  }

  return app;
}
