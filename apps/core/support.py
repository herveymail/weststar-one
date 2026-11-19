"""Settings › System support — a screen for the people who look after Weststar ONE.

How big the database is and what's taking the room, file storage, versions, pending database updates, background
jobs, recent crashes, safe clean-up buttons and a support report to download (no passwords, keys or customer data).

Who can see it: only staff with "System support" turned on (and the admin role). People who already have it choose
who else gets it, on this screen. If nobody has it yet, any admin can claim it once.
"""
import hashlib
import os
import platform
import shutil
import sys
import traceback
from datetime import timedelta
from pathlib import Path

import django
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from .audit import audit
from .models import AuditLog, BackupRun, ErrorEvent, JobRun, OutboxEmail, SlowRequest
from .permissions import can

START = timezone.now()   # when this copy of the app started

# Plain names for the tables people ask about.
TABLE_NAMES = {
    "helpdesk_ticket": "Tickets", "helpdesk_ticketmessage": "Ticket messages", "helpdesk_timeentry": "Time entries",
    "files_upload": "File records (the files themselves are on disk)", "core_auditlog": "Audit log", "core_outboxemail": "Email outbox",
    "billing_invoice": "Invoices", "billing_invoiceline": "Invoice lines", "billing_payment": "Payments", "crm_client": "Clients",
    "crm_contact": "Contacts", "accounts_loginattempt": "Sign-in attempts", "django_session": "Sign-in sessions",
    "core_slowrequest": "Slow page log", "core_errorevent": "Crash log", "billing_quote": "Quotes", "core_setting": "Settings",
}
KEEP = {"slow": 30, "attempts": 180, "outbox": 90, "errors": 90}   # days kept by "Trim old logs"


# ── who may see it ──
def anyone_has_access() -> bool:
    from apps.accounts.models import User
    return User.objects.filter(is_active=True, support_access=True).exists()


def allowed(user) -> bool:
    return bool(user.is_authenticated and can(user, "admin") and getattr(user, "support_access", False))


def can_claim(user) -> bool:
    return bool(user.is_authenticated and can(user, "admin", "manage") and not anyone_has_access())


def tile_visible(user) -> bool:
    return allowed(user) or can_claim(user)


# ── crash capture ──
def record_exception(sender=None, request=None, **kw):
    """Called by Django whenever a page crashes. Must never raise."""
    try:
        etype, exc, tb = sys.exc_info()
        if etype is None:
            return
        frames = traceback.extract_tb(tb)
        base = str(settings.BASE_DIR)
        ours = [f for f in frames if f.filename.startswith(base) and "/.venv/" not in f.filename and "site-packages" not in f.filename] or frames[-1:]
        last = ours[-1]
        rel = last.filename.replace(base, "").lstrip("/")
        where = f"{rel}:{last.lineno} in {last.name}"
        fp = hashlib.sha1(f"{etype.__name__}|{where}".encode(), usedforsecurity=False).hexdigest()
        trace = "\n".join(f"{f.filename.replace(base, '').lstrip('/')}:{f.lineno} in {f.name}" for f in frames[-14:])
        user = getattr(getattr(request, "user", None), "email", "") or ""
        path = (getattr(request, "path", "") or "")[:300]
        obj, created = ErrorEvent.objects.get_or_create(fingerprint=fp, defaults={
            "kind": etype.__name__[:120], "message": str(exc)[:500], "where": where[:300], "path": path,
            "method": (getattr(request, "method", "") or "")[:8], "trace": trace[:6000], "last_user": user[:254]})
        if not created:
            ErrorEvent.objects.filter(pk=obj.pk).update(count=obj.count + 1, message=str(exc)[:500], path=path, last_user=user[:254], last_seen=timezone.now())
    except Exception:  # noqa: BLE001, S110 — recording a crash must not cause another one
        pass


# ── facts ──
def _size(n) -> str:
    if n is None:
        return "—"
    for unit in ("bytes", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{n:.0f} {unit}" if unit in ("bytes", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def _dir_size(path) -> tuple[int, int]:
    total = files = 0
    try:
        for root, _dirs, names in os.walk(path):
            for n in names:
                try:
                    total += os.path.getsize(os.path.join(root, n))
                    files += 1
                except OSError:
                    pass
    except OSError:
        pass
    return total, files


def database() -> dict:
    out = {"tables": [], "size": None, "version": "", "connections": None}
    try:
        with connection.cursor() as c:
            c.execute("SELECT pg_database_size(current_database()), current_setting('server_version'), "
                      "(SELECT count(*) FROM pg_stat_activity WHERE datname = current_database())")
            out["size"], out["version"], out["connections"] = c.fetchone()
            c.execute("""SELECT c.relname, pg_total_relation_size(c.oid), pg_relation_size(c.oid), GREATEST(c.reltuples, 0)::bigint,
                                COALESCE(s.n_dead_tup, 0), s.last_autovacuum
                         FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                         LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
                         WHERE c.relkind = 'r' AND n.nspname = 'public' ORDER BY 2 DESC""")
            rows = c.fetchall()
        out["table_count"] = len(rows)
        biggest = rows[0][1] if rows else 0
        for name, total, data, est, dead, vac in rows[:15]:
            out["tables"].append({"name": name, "label": TABLE_NAMES.get(name, ""), "total": _size(total), "bytes": total, "data": _size(data),
                                  "indexes": _size(total - data), "rows": est, "dead": dead, "vacuumed": vac,
                                  "pct": round(total * 100 / biggest) if biggest else 0, "share": round(total * 100 / out["size"], 1) if out["size"] else 0})
        out["rest"] = _size(sum(r[1] for r in rows[15:])) if len(rows) > 15 else ""
    except Exception as e:  # noqa: BLE001
        out["error"] = str(e)[:200]
    return out


def counts() -> list[tuple[str, int]]:
    from apps.accounts.models import User
    from apps.billing.models import Invoice
    from apps.crm.models import Client
    from apps.files.models import Upload
    from apps.helpdesk.models import Ticket, TicketMessage
    return [("Tickets", Ticket.objects.count()), ("Ticket messages", TicketMessage.objects.count()), ("Clients", Client.objects.count()),
            ("Invoices", Invoice.objects.count()), ("Uploaded files", Upload.objects.count()), ("Staff users", User.objects.filter(is_active=True).count()),
            ("Audit log entries", AuditLog.objects.count())]


def pending_migrations() -> list[str]:
    from django.db.migrations.executor import MigrationExecutor
    try:
        ex = MigrationExecutor(connection)
        return [f"{m.app_label}.{m.name}" for m, _ in ex.migration_plan(ex.loader.graph.leaf_nodes())]
    except Exception as e:  # noqa: BLE001
        return [f"(couldn't check: {str(e)[:120]})"]


def storage() -> dict:
    from . import backups
    media = Path(settings.MEDIA_ROOT)
    msize, mfiles = _dir_size(media)
    try:
        broot = backups.root()
        bsize, bfiles = _dir_size(broot)
    except Exception:  # noqa: BLE001
        broot, bsize, bfiles = "", 0, 0
    try:
        disk = shutil.disk_usage(media if media.exists() else "/")
    except OSError:
        disk = None
    return {"media": _size(msize), "media_files": mfiles, "media_bytes": msize, "backups": _size(bsize), "backup_files": bfiles,
            "backups_bytes": bsize, "disk_free": _size(disk.free) if disk else "—", "disk_total": _size(disk.total) if disk else "—",
            "disk_pct": round((disk.total - disk.free) * 100 / disk.total) if disk else 0, "media_path": str(media), "backup_path": str(broot)}


def system() -> list[tuple[str, str]]:
    from . import mail
    up = timezone.now() - START
    last_backup = BackupRun.objects.filter(kind="backup", status="done").first()
    return [
        ("Weststar ONE version", settings.APP_VERSION), ("Running since", f"{timezone.localtime(START):%b %-d, %-I:%M %p} ({up.days}d {up.seconds // 3600}h)"),
        ("Python", platform.python_version()), ("Django", django.get_version()), ("Web address", settings.APP_URL),
        ("Time zone", settings.TIME_ZONE), ("Debug mode", "ON — turn this off on a live server" if settings.DEBUG else "Off (correct)"),
        ("Email sending", "Set up" if mail.configured() else "Not set up"),
        ("Last backup", f"{timezone.localtime(last_backup.created_at):%b %-d, %-I:%M %p}" if last_backup else "None made from the Backups page yet"),
        ("Web workers", os.environ.get("WEB_WORKERS", "3")), ("Cloudflare-only lock", os.environ.get("CLOUDFLARE_ONLY", "off")),
    ]


def jobs() -> list[dict]:
    from .jobs import JOBS
    runs = {r.name: r for r in JobRun.objects.all()}
    now = timezone.now()
    out = []
    for name, j in JOBS.items():
        r = runs.get(name)
        late = bool(r and r.last_run_at and now - r.last_run_at > timedelta(minutes=max(j["every_minutes"] * 3, 15)))
        out.append({"name": name, "label": j["label"], "every": j["every_minutes"], "run": r, "late": late or r is None,
                    "bad": bool(r and not r.last_ok)})
    return out


def trim_counts() -> dict:
    from django.contrib.sessions.models import Session

    from apps.accounts.models import LoginAttempt
    now = timezone.now()
    return {
        "sessions": Session.objects.filter(expire_date__lt=now).count(),
        "slow": SlowRequest.objects.filter(created_at__lt=now - timedelta(days=KEEP["slow"])).count(),
        "attempts": LoginAttempt.objects.filter(created_at__lt=now - timedelta(days=KEEP["attempts"])).count(),
        "outbox": OutboxEmail.objects.filter(status="sent", created_at__lt=now - timedelta(days=KEEP["outbox"])).count(),
        "errors": ErrorEvent.objects.filter(last_seen__lt=now - timedelta(days=KEEP["errors"])).count(),
    }


def trim() -> int:
    from django.contrib.sessions.models import Session

    from apps.accounts.models import LoginAttempt
    now = timezone.now()
    n = Session.objects.filter(expire_date__lt=now).delete()[0]
    n += SlowRequest.objects.filter(created_at__lt=now - timedelta(days=KEEP["slow"])).delete()[0]
    n += LoginAttempt.objects.filter(created_at__lt=now - timedelta(days=KEEP["attempts"])).delete()[0]
    n += OutboxEmail.objects.filter(status="sent", created_at__lt=now - timedelta(days=KEEP["outbox"])).delete()[0]
    n += ErrorEvent.objects.filter(last_seen__lt=now - timedelta(days=KEEP["errors"])).delete()[0]
    return n


def tidy_database() -> str:
    """VACUUM ANALYZE: hands back space from deleted rows and refreshes the planner's statistics. Safe while people work."""
    before = database()["size"] or 0
    with connection.cursor() as c:   # autocommit is on outside a transaction, which VACUUM needs
        c.execute("VACUUM (ANALYZE)")
    after = database()["size"] or 0
    return f"Database tidied. Size: {_size(before)} → {_size(after)}."


def report(user) -> str:
    """Plain-text support report. No passwords, keys, settings values or customer data — sizes, versions and counts only."""
    db, st = database(), storage()
    lines = ["WESTSTAR ONE — SUPPORT REPORT", f"Made {timezone.localtime():%Y-%m-%d %H:%M %Z} by {user.email}", ""]
    lines += ["== System =="] + [f"{k}: {v}" for k, v in system()]
    lines += ["", "== Database ==", f"Size: {_size(db['size'])}   PostgreSQL {db['version']}   connections: {db['connections']}   tables: {db.get('table_count', '?')}"]
    lines += [f"  {t['name']:<34} {t['total']:>10}  ~{t['rows']:>9} rows  dead {t['dead']}" for t in db["tables"]]
    pend = pending_migrations()
    lines += ["", "== Database updates waiting ==", *(pend or ["none"])]
    lines += ["", "== Storage ==", f"Uploaded files: {st['media']} in {st['media_files']} files", f"Backups: {st['backups']} in {st['backup_files']} files",
              f"Disk: {st['disk_free']} free of {st['disk_total']} ({st['disk_pct']}% used)"]
    lines += ["", "== Records =="] + [f"{k}: {v}" for k, v in counts()]
    lines += ["", "== Background jobs =="]
    for j in jobs():
        r = j["run"]
        lines.append(f"{j['name']:<22} every {j['every']:>4} min  last {timezone.localtime(r.last_run_at):%m-%d %H:%M}  {'OK' if r.last_ok else 'FAILED'}  {r.last_result[:120]}" if r and r.last_run_at
                     else f"{j['name']:<22} every {j['every']:>4} min  never ran")
    lines += ["", "== Email outbox ==", f"waiting: {OutboxEmail.objects.filter(status='pending').count()}   failed: {OutboxEmail.objects.filter(status='failed').count()}"]
    lines += ["", "== Crashes (most recent first) =="]
    for e in ErrorEvent.objects.all()[:25]:
        lines += [f"[{e.count}x, last {timezone.localtime(e.last_seen):%m-%d %H:%M}] {e.kind}: {e.message}", f"   at {e.where}  ({e.method} {e.path})", *("      " + ln for ln in e.trace.splitlines()), ""]
    if not ErrorEvent.objects.exists():
        lines.append("none recorded")
    lines += ["", "== Slow pages, last 24h =="]
    since = timezone.now() - timedelta(hours=24)
    lines += [f"{s.total_ms:>6.0f} ms  db {s.db_ms:>6.0f} ms  {s.method} {s.path}" for s in SlowRequest.objects.filter(created_at__gte=since)[:30]] or ["none"]
    return "\n".join(lines) + "\n"


# ── the page ──
@login_required
def support_page(request):
    from apps.accounts.models import User
    if can_claim(request.user):
        if request.method == "POST" and request.POST.get("action") == "claim":
            User.objects.filter(pk=request.user.pk).update(support_access=True)
            audit(request, "grant", "user", request.user.pk, "Took System support access (nobody had it yet)", area="admin")
            messages.success(request, "You now have System support access. Choose who else gets it at the bottom of this page.")
            return redirect("/settings/support/")
        return render(request, "core/support_claim.html", {})
    if not allowed(request.user):
        raise PermissionDenied
    if request.method == "POST":
        a = request.POST.get("action")
        if a == "tidy":
            try:
                messages.success(request, tidy_database())
                audit(request, "maintain", "system", None, "Tidied the database (VACUUM ANALYZE)", area="admin")
            except Exception as e:  # noqa: BLE001
                messages.error(request, f"Couldn't tidy the database: {str(e)[:200]}")
        elif a == "trim":
            n = trim()
            audit(request, "maintain", "system", None, f"Trimmed {n} old log rows", area="admin")
            messages.success(request, f"Removed {n} old log entr{'ies' if n != 1 else 'y'}. The audit log is never trimmed.")
        elif a == "clear_errors":
            n = ErrorEvent.objects.all().delete()[0]
            audit(request, "maintain", "system", None, f"Cleared {n} crash records", area="admin")
            messages.success(request, "Crash log cleared.")
        elif a == "access":
            ids = {int(x) for x in request.POST.getlist("user") if x.isdigit()} | {request.user.pk}   # you can't remove yourself by accident
            for u in User.objects.filter(is_active=True, role="admin"):
                want = u.pk in ids
                if u.support_access != want:
                    User.objects.filter(pk=u.pk).update(support_access=want)
                    audit(request, "grant" if want else "revoke", "user", u.pk, f"System support access {'given to' if want else 'removed from'} {u.email}", area="admin")
            User.objects.filter(support_access=True).exclude(is_active=True, role="admin").update(support_access=False)
            messages.success(request, "Saved who can see System support.")
        return redirect("/settings/support/")
    if request.GET.get("report"):
        audit(request, "download", "system", None, "Downloaded the support report", area="admin")
        r = HttpResponse(report(request.user), content_type="text/plain; charset=utf-8")
        r["Content-Disposition"] = f'attachment; filename="weststar-one-support-{timezone.localtime():%Y%m%d-%H%M}.txt"'
        r["Cache-Control"] = "private, no-store"
        return r
    db = database()
    pend = pending_migrations()
    js = jobs()
    notes = []
    if pend:
        notes.append(("bad", f"{len(pend)} database update{'s are' if len(pend) != 1 else ' is'} waiting. Run the updater on the server: sudo ./update.sh"))
    if any(j["bad"] for j in js):
        notes.append(("bad", "A background job failed last time it ran: " + ", ".join(j["label"] for j in js if j["bad"])))
    stuck = [j["label"] for j in js if j["late"] and not j["bad"]]
    if stuck:
        notes.append(("warn", "These background jobs haven't run when expected (is the jobs container up?): " + ", ".join(stuck[:6])))
    st = storage()
    if st["disk_pct"] >= 90:
        notes.append(("bad", f"The disk is {st['disk_pct']}% full ({st['disk_free']} free)."))
    if settings.DEBUG:
        notes.append(("bad", "Debug mode is on. It must be off on a live server."))
    errs = list(ErrorEvent.objects.all()[:20])
    day = timezone.now() - timedelta(hours=24)
    recent = sum(1 for e in errs if e.last_seen >= day)
    if recent:
        notes.append(("warn", f"{recent} kind{'s' if recent != 1 else ''} of crash in the last 24 hours — see Crashes below."))
    if not notes:
        notes.append(("good", "Nothing needs attention."))
    return render(request, "core/support.html", {
        "db": db, "db_size": _size(db["size"]), "storage": st, "system": system(), "counts": counts(), "pending": pend, "jobs": js,
        "notes": notes, "errors": errs, "trim": trim_counts(), "keep": KEEP,
        "outbox": {"pending": OutboxEmail.objects.filter(status="pending").count(), "failed": OutboxEmail.objects.filter(status="failed").count()},
        "admins": User.objects.filter(is_active=True, role="admin").order_by("name"),
    })
