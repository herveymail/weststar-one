# Weststar ONE 3.0

The rebuild of Weststar ONE (formerly *myflow*) — same modules and menus, new look, no PHP.

- **Stack:** TypeScript everywhere. Node 22 + Fastify API, PostgreSQL 16 (Drizzle ORM), React 19 web app, pg-boss background worker.
- **Looks:** each person picks *Look 1 · Indigo Clean* (light, full sidebar) or *Look 2 · Graphite* (dark, icon bar) under **Profile**.
- **Your data comes with you:** the importer copies everything from the old MariaDB database, keeps ticket/invoice/quote numbers, and keeps old passwords and two-factor working.

---

## Contents

1. [Install on a server](#install-on-a-server)
2. [Move your data from the old Weststar One](#move-your-data-from-the-old-weststar-one)
3. [Cutover plan](#cutover-plan)
4. [Security](#security)
5. [What's in 3.0 and what's next](#whats-in-30-and-whats-next)
6. [Day-to-day operations](#day-to-day-operations)
7. [Development](#development)
8. [How the code is organised](#how-the-code-is-organised)

---

## Install on a server

Any Linux server with Docker works (Ubuntu 24.04/26.04, Debian 12/13). DNS for your chosen name (e.g. `one.weststarmsp.com`) must point at the server; ports 80 and 443 must be open. Caddy gets the HTTPS certificate automatically.

```bash
git clone https://github.com/herveymail/weststar-one.git /opt/weststar-one
cd /opt/weststar-one
cp .env.example .env
nano .env        # set DOMAIN, POSTGRES_PASSWORD (openssl rand -base64 24), APP_ENCRYPTION_KEY (openssl rand -base64 32)
docker compose up -d --build
docker compose exec app node dist/scripts/seed-admin.js --email casey@weststarmsp.com --name "Casey Hervey"
```

The last command prints a one-time temporary password. Sign in at `https://<DOMAIN>`; you will be asked to choose a new password and set up two-factor sign-in.

> **Back up `APP_ENCRYPTION_KEY` offline** (password manager + printed copy). Two-factor seeds, Wi-Fi passwords, ISP accounts, vendor account numbers, secure messages and H/R SSN/bank fields are encrypted with it. Without it those fields cannot be read — including from backups.

Updating later:

```bash
cd /opt/weststar-one && git pull && docker compose up -d --build
```

Database changes run automatically when the app starts.

---

## Move your data from the old Weststar One

The importer runs on the server from the command line, so the old database password and the old encryption keys never pass through a browser. It reads everything it needs from the old app's `config/config.php`.

```bash
# Copy the old config next to the new app (read-only), then:
docker compose run --rm -v /var/www/myflow/config/config.php:/old/config.php:ro app \
  node dist/importer/cli.js --old-config /old/config.php --dry-run      # practice run: counts only, saves nothing

docker compose run --rm -v /var/www/myflow/config/config.php:/old/config.php:ro app \
  node dist/importer/cli.js --old-config /old/config.php                # real import
```

If the old MariaDB is on another machine, make sure the new server can reach it (or pass `--mysql mysql://user:pass@host:3306/myflow --app-key … --encryption-key …` instead of `--old-config`).

**What it does**

| | |
|---|---|
| Safe to repeat | Every record keeps its old id; running again **updates** instead of duplicating. Run it nightly during the side-by-side period. |
| Numbers kept | `T-10476` stays `T-10476` (Zoho-era numbers too). New tickets continue after the highest old number. Same for invoices, quotes, projects and contracts. |
| Passwords | Old bcrypt hashes are carried over. Each person's password is upgraded to Argon2id the first time they sign in. Nobody has to reset. |
| Two-factor | Authenticator seeds (both the old `v2:` and the older format) are decrypted with the old `APP_KEY` and re-encrypted. Existing phone apps keep working. Old recovery codes cannot be carried over — people can make new ones under *My sign-in & 2FA*. |
| Secrets | Wi-Fi passwords and ISP accounts (`nenc:`), H/R SSN and bank fields are decrypted with the old `ENCRYPTION_KEY` and re-encrypted with the new key. |
| Covered | Users, clients, contacts, assets, networks, client notes, vendors, projects, leads, campaigns, invoices + lines, recurring invoices + lines, quotes + lines, contracts, client policies, training enrollments, warranties → renewals, expenses, bank transactions, calendar, inventory, mileage, secure messages, domains + SSL, knowledge base, workflows (imported paused), employees, time off, timeclock, tickets + replies + notes + time. |
| Not yet | Uploaded files/attachments (they stay on the old server for now), old workflow logic (imported as paused descriptions to rebuild), settings and integration keys (re-enter them in *Settings*; they are encrypted when saved). |

Every run is listed under **Settings › Import from old Weststar One**, with warnings (for example a value that couldn't be decrypted because a key was wrong).

---

## Cutover plan

1. **Install** the new app on a new server (or the same droplet on another hostname).
2. **Practice import** with `--dry-run`, then a real import. Click through clients, tickets and invoices you know.
3. **Side by side, one to two weeks.** Keep working in the old app; re-run the import nightly (`crontab`: `30 2 * * * cd /opt/weststar-one && docker compose run --rm … --old-config /old/config.php`).
4. **Cutover day:** put the old app in read-only/maintenance, run the import one last time, point people at the new address.
5. Keep the old server (powered off) for 90 days, then archive its database dump with its `config.php` keys.

---

## Security

What changed compared with the PHP app:

- **No default secrets.** The app refuses to start without a 32-byte `APP_ENCRYPTION_KEY` (the old app silently fell back to `myflow_default_key`).
- **Passwords:** Argon2id (OWASP parameters). Minimum 12 characters. Account lockout after 5 failures with doubling lock time; per-IP throttling; the same answer for "wrong password" and "no such user".
- **Two-factor:** TOTP with replay protection (a code can be used once), 10 one-time recovery codes stored as keyed hashes. Admins can be required to use it (*Settings › Sign-in & MFA*; default: required for admins).
- **Sessions:** random 256-bit token in an `HttpOnly`, `Secure`, `SameSite=Lax` cookie (`__Host-` prefixed over HTTPS). The database stores only a SHA-256 of the token. New session id after sign-in and after two-factor. Idle timeout (default 30 min) and 12-hour absolute limit. Changing a password or a role signs out other sessions. People can see and end their own sessions.
- **Forged requests:** every write must come from the app's own origin **and** carry the per-session CSRF token.
- **Permissions:** roles (admin, manager, tech, viewer) per area plus a separate H/R switch, enforced on the server for every request. Time off, timeclock and mileage are private to each person. Encrypted fields are never sent in lists; showing one requires edit rights (manage for H/R) and is written to the audit log.
- **Encryption at rest:** AES-256-GCM for secrets with key rotation support (`APP_ENCRYPTION_KEYS_OLD`).
- **Audit log:** every create/edit/archive, sign-in, password change, two-factor change, secret reveal and import, with before/after values (secrets redacted).
- **Input:** every request body is validated (zod) against the module definition; unknown fields are rejected; sort/filter columns are whitelisted; all SQL is parameterised.
- **Headers:** strict Content-Security-Policy (no inline scripts), HSTS, `frame-ancestors 'none'`, no `X-Powered-By`.
- **Containers:** the app and worker run as a non-root user on a read-only filesystem with all Linux capabilities dropped; the database is not exposed to the internet.
- **Supply chain:** pinned dependency versions, lockfile, `pnpm audit` in CI.

---

## What's in 3.0 and what's next

**Complete and tested**

- Sign-in, two-factor, password changes, sessions, staff users and roles, audit and security logs.
- Every one of the 27 menu items from the old sidebar, in the same order: list, search, status tabs, add, edit, archive/restore for each.
- **Tickets:** inbox / board / my queue, filters (open, unassigned, SLA at risk, closed), replies and internal notes, assign, status and priority, time logging, response SLA from client or defaults, timeline of every change, SLA-breach marking.
- **Clients:** full client page with the old tabs (contacts, tickets, assets, network, contracts, invoices, quotes, projects, notes, domains, policies, training), account alert on every ticket, open balance.
- **Invoices, quotes, recurring schedules** with line items and server-calculated totals; recurring invoices generated automatically; overdue marking.
- **H/R:** employees with encrypted SSN/bank fields, time-off requests (people request, H/R approves), timeclock with Clock in/out in the top bar, mileage.
- **Settings:** all seven groups from the old Settings home, searchable; secret settings encrypted.
- **Importer** from the old database (see above). 74 automated tests, including the importer against real PHP-encrypted data.

**Next rounds** (planned, not in this build)

1. Microsoft 365 email: email-to-ticket and sending replies, invoices and quotes by email (replies are saved on the ticket today but not emailed).
2. Stripe card/ACH payments, payment links, AutoPay, invoice/quote PDFs and e-signature for quotes and contracts.
3. Client portal (tickets, invoices, KB, secure messages, policy acknowledgement).
4. File attachments (with per-client encryption) and copying old uploads.
5. Datto RMM, MSP360, Yeastar and Google Chat syncs; workflow engine; AI ticket assistant.
6. Reports, the training course player, campaign sending.

---

## Day-to-day operations

| Task | How |
|---|---|
| Back up the database | `deploy/backup.sh` (nightly from cron). Copy the dumps off the server. |
| Restore | `docker compose exec -T db pg_restore -U weststar -d weststar --clean < backups/weststar-….dump` |
| See background jobs | *Settings › Scheduled jobs* (SLA watch, recurring invoices, overdue invoices, auto-close, cleanup) |
| Unlock someone / reset 2FA | *Settings › Staff users* → click the person |
| Rotate the encryption key | Put the current key in `APP_ENCRYPTION_KEYS_OLD`, set a new `APP_ENCRYPTION_KEY`, restart. Old values still decrypt; they are re-encrypted with the new key whenever they're saved again. |
| Logs | `docker compose logs -f app worker` (cookies, CSRF tokens and passwords are never logged) |

---

## Development

Needs Node 22, pnpm 10 and PostgreSQL 16.

```bash
pnpm install
createdb weststar && createdb weststar_test
cp .env.example .env              # DATABASE_URL, APP_URL=http://localhost:3000, APP_ENCRYPTION_KEY …
pnpm db:migrate
pnpm seed:admin --email you@example.com --name "You"
pnpm --filter @ws/api dev         # API on :3000
pnpm --filter @ws/web dev         # web on :5173 (proxies /api to :3000)
```

Tests (`apps/api/.env.test` points at `weststar_test`, which the tests wipe):

```bash
pnpm --filter @ws/api test
# include the importer test against a MariaDB loaded with the old schema:
LEGACY_MYSQL_URL=mysql://user:pass@127.0.0.1:3306/legacy pnpm --filter @ws/api test
```

The importer test fills the old database using `apps/api/test/fixtures/legacy-seed.php`, a copy of the old app's own encryption functions, so it checks against exactly the ciphertext production holds. That file is test tooling only. It is never deployed and the app contains no PHP.

---

## How the code is organised

```
packages/shared/src/modules.ts   ← every module: fields, menu, permissions (single source of truth)
packages/shared/src/settings.ts  ← settings pages
apps/api/src/db/schema.ts        ← core tables + tables generated from modules.ts
apps/api/src/routes/resources.ts ← list/create/edit/archive/reveal for every module
apps/api/src/routes/tickets.ts   ← helpdesk
apps/api/src/auth/*              ← sessions, sign-in, two-factor, CSRF/Origin checks
apps/api/src/importer/*          ← import from the old MariaDB
apps/api/src/jobs/*              ← background jobs (replaces the old cron scripts)
apps/web/src                     ← React app (pages/, components/, styles.css with both looks)
```

**Adding a field:** add it to the module in `packages/shared/src/modules.ts`, run `pnpm db:generate`, commit the new file in `apps/api/migrations/`. The API validation, the list column and the form field all pick it up.
