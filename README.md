# Weststar ONE

The Weststar MSP platform: tickets, clients, projects, sales, billing, tools and H/R in one place.
This replaces the old PHP app (myflow). It has the same menus and features, a cleaner screen, and much
tighter security, and everything from the old app is imported.

**Stack:** Python 3.13 · Django 5.2 LTS · PostgreSQL 17 · HTMX (screens are rendered by the server, with no
front-end build step) · gunicorn · Caddy (automatic HTTPS) · Docker.

The earlier TypeScript version, with the same look, is kept on the `typescript-reference` branch.

---

## What's in it

| Area | Screens |
|---|---|
| Tickets | Inbox with reading pane, Board, My queue, SLA timers, replies and internal notes, time logging, file attachments |
| Clients | Client page with 16 tabs (contacts, tickets, assets, network, contracts, invoices, quotes, projects, notes, domains, policies, training, files…) |
| Sales | Leads, Marketing campaigns |
| Billing | Invoices and quotes with line items, Recurring invoices (generated automatically), Banking, Contracts, Policies, Security training, Renewals, Expenses, Vendors |
| Tools | Calendar, Inventory, Mileage, Secure messages, Domains & SSL, Backups, RMM, Knowledge base, Workflows |
| H/R | My HR (time off, timeclock, mileage), H/R Admin (employees, approvals) |
| Settings | Every setting from the old app, Staff users, Security log, Audit log, Background jobs, Import |

There are two looks, and each person picks theirs under *Profile & look*:
- **Look 1 Indigo** is light, with a full sidebar.
- **Look 2 Graphite** is dark, with an icon bar and pop-out menus.

## Security

- **Passwords** are hashed with Argon2. Old PHP bcrypt hashes still work and are upgraded the first time
  each person signs in, so nobody has to reset.
- **Sign in with Google Workspace** for staff. Only people added in Staff users, on your company domain(s),
  can get in. Google's 2-Step Verification counts as the second factor, and passwords can be limited to
  admins as a backup.
- **Two-factor sign-in** uses authenticator apps, with one-time recovery codes. It's required for admins,
  managers and anyone with H/R access (changeable in Settings). Codes can't be reused.
- **Lockout** starts after 5 failed attempts and doubles on repeat lockouts. Password and 2FA failures are
  counted separately, every count is race-safe, and there's also a limit per IP address.
- **Sessions:** each sign-in gets a fresh session ID. Sessions end after idle time. You can see and end your
  sessions, and changing your password signs out every other browser.
- **Secrets** (2FA seeds, Wi-Fi passwords, ISP accounts, SSN and bank fields, vendor account numbers, secure
  messages) are encrypted with AES-256-GCM using `APP_ENCRYPTION_KEY`. They're never shown in lists.
  Revealing one requires the right permission, is rate-limited and is always written to the audit log.
- **Roles:** Admin, Manager, Help desk, Tech, Sales/CRM, Accounting and Viewer, plus a separate H/R switch.
  Each area has none / view / edit / manage levels. Private records (time off, timeclock) are visible only
  to their owner and H/R, and nobody can approve their own.
- **Files** are stored under random names, outside the web root. Every download checks access first, and
  only safe file types are allowed.
- **Browser protection:** a strict Content-Security-Policy with no inline scripts, CSRF protection on every
  form, HSTS, and clickjacking protection.
- **Audit log** of every change, filtered so people only see entries for areas they can access.

## Install: the setup wizard

You need a fresh Linux server (Ubuntu 24.04/26.04 LTS or Debian 12/13, 2 CPU / 4 GB RAM is plenty) and a
DNS name pointing at it, for example `one.weststarmsp.com`.

```sh
git clone https://github.com/herveymail/weststar-one.git /opt/weststar-one   # GitHub asks for your username + a token
sudo bash /opt/weststar-one/install.sh
```

The wizard works like the old Weststar One installer:

| Step | What it does |
|---|---|
| 1. Configuration | Domain, company name, time zone, first admin, Google sign-in, Gmail sending, Wasabi backups, AI, update branch |
| 2. Install packages | Docker (official repository), firewall (SSH, 80, 443 only); offers to stop an old web server holding ports 80/443 |
| 3. Database & keys | Generates the database password, app secret and encryption key, and asks you to save the key |
| 4. Build & start | Builds and starts PostgreSQL, the app and the background jobs |
| 5. Configure | Creates your admin account and saves your settings (secrets encrypted) |
| 6. Import | If the old app is on the same server, reads its `config/config.php`, copies its database read-only, and imports everything including uploads. Otherwise, point it at a dump file. It always does a practice run first. |
| 7. HTTPS & finish | Gets the certificate automatically, schedules nightly backups, and prints your login |

Run it again later to update, or to import again.

> **Back up `APP_ENCRYPTION_KEY` offline** (the wizard shows it once), in a password manager or printed and
> kept in the safe. Without it, the encrypted fields in the database and backups can't be read.

### Google sign-in: one-time setup in Google Cloud

1. Go to https://console.cloud.google.com and create a project (e.g. "Weststar ONE") under your Workspace
   organization.
2. Under **APIs & Services › OAuth consent screen**, choose **Internal**. This means only your Workspace
   users can use it, and no Google review is needed. App name: Weststar ONE.
3. Under **APIs & Services › Credentials › Create credentials › OAuth client ID**:
   - Type: **Web application**
   - Authorized redirect URI: `https://YOUR-DOMAIN/login/google/callback/`
4. Copy the **client ID** and **client secret** into the wizard, or later into Settings › Sign-in & 2FA.
5. Recommended: in Google Admin › Security › 2-Step Verification, turn on **enforcement** for your staff.
   Google sign-in then counts as two-factor.

Staff still need an account in **Settings › Staff users** (same email as their Google login) before they
can sign in. That's how you control who gets in and what role they have.

### Manual install (without the wizard)

```sh
cp .env.example .env && nano .env     # fill in DOMAIN, SECRET_KEY, DB_PASSWORD, APP_ENCRYPTION_KEY
docker compose up -d --build
docker compose exec app python manage.py create_admin --email you@weststarmsp.com --name "Your Name"   # prints a temporary password
```

## Bring over the old Weststar One

The importer reads a copy of the old database and never writes to the old server. It's safe to run as many
times as you like: it updates records instead of duplicating them, and it never overwrites anything you've
changed in the new app.

The easiest way is the wizard (`sudo bash install.sh`, option 2 when it's already installed). To do it by
hand:

1. Put the old app's `APP_KEY` and `ENCRYPTION_KEY` (from its `config/config.php`) into `.env` as
   `OLD_APP_KEY` and `OLD_ENCRYPTION_KEY`. These unlock 2FA setups, Wi-Fi passwords and H/R fields.
2. Copy a database dump and the old `uploads/` folder to the server, then run the commands below. The old
   dump is loaded into a temporary MariaDB container just for the import, and removed afterwards.

```sh
./deploy/import-old.sh /path/to/db_dump.sql.gz /path/to/old/uploads --dry-run   # practice run, saves nothing
./deploy/import-old.sh /path/to/db_dump.sql.gz /path/to/old/uploads             # the real import
```

What comes across:
- Staff keep their **passwords** and **2FA**.
- **Ticket, invoice, quote and contract numbers** are kept, and new numbers continue the old sequence with
  the same prefix (for example `ITDS-00918`).
- Ticket **replies, notes, time entries and attachments**, client and project files.
- Every client, contact, asset, network, invoice (with line items), recurring invoice, quote, contract,
  policy, lead, campaign, KB article, inventory item, domain, employee, time off and timeclock entry.

The result is shown under **Settings › Import**, with a warning for anything that needs a look.

**Cutover day:** run the import one last time, then turn the old app off. You can run both side by side
before that. Re-running the import picks up whatever changed in the old app in the meantime.

## Everyday operations

| Task | Command |
|---|---|
| Update to the latest version (backs up first, rolls back if the build fails) | `sudo ./update.sh` |
| Backup now (the wizard schedules it nightly at 2:30 AM; optional Wasabi copy) | `./deploy/backup.sh` |
| Restore a backup | `./deploy/restore.sh backups/db_….dump backups/media_….tar.gz` |
| Make another admin | `docker compose exec app python manage.py create_admin --email … --name "…"` |
| See logs | `docker compose logs -f app jobs` |
| Run background jobs now | `docker compose exec jobs python manage.py run_jobs --force` |

Copy the backups off the server as well, to another site or a cloud bucket.

## Developing

```sh
python3.13 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env    # set DEBUG=true, APP_URL=http://localhost:8000 and local DB_* values
python manage.py migrate && python manage.py createcachetable
python manage.py create_admin --email you@example.com --name You
python manage.py runserver
python -m pytest        # tests: a test_ database on PostgreSQL; importer tests also use a MariaDB `legacy` db
```

How the code is laid out:

- `apps/core`: permissions, the module registry (menus and generic list/edit screens), settings, audit,
  encryption, background jobs
- `apps/accounts`: sign-in, 2FA, sessions, staff users
- `apps/helpdesk`: tickets; `apps/crm`: clients, contacts, assets, networks, projects
- `apps/sales`, `apps/billing`, `apps/tools`, `apps/hr`: the rest of the modules
- `apps/files`: attachments and file storage
- `apps/legacy`: the importer for the old PHP app

Most new list-style features take a model, a `register(Module(...))` line and a migration. The menu, list,
search, filters, add/edit drawer, permissions and audit log all come from the registry.

## Next rounds

- Email-to-ticket and replies through Google Workspace (Gmail)
- Client portal
- Stripe payments and QuickBooks sync
- Dispatch board
- Datto RMM and MSP360 sync
- Reports
