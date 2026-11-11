"""Settings › Backups: one-click backup and restore, nightly backups, and the off-site copy (Wasabi / any S3).

A backup is two files in the backups folder (BACKUP_ROOT, /data/backups in Docker):
    ws_<date>_<time>.dump            the whole database (pg_dump custom format)
    ws_<date>_<time>_files.tar.gz    uploaded files (ticket attachments, logos…)

The work happens in the background jobs container, so a big backup never ties up the website:
the page queues a BackupRun and the jobs loop picks it up within a minute.

Restore replaces everything with the chosen backup. A fresh backup is always taken first, so a restore can be undone.
Encrypted fields (2FA seeds, Wi-Fi passwords, H/R fields) can only be read with the same APP_ENCRYPTION_KEY.
"""
import datetime as dt
import hashlib
import hmac
import os
import re
import subprocess
import tarfile
import urllib.parse
import urllib.request
from pathlib import Path

from django.conf import settings
from django.utils import timezone

from .models import BackupRun, Setting

NAME_RE = re.compile(r"^ws_\d{4}-\d{2}-\d{2}_\d{4}(_\d+)?$")


def root() -> Path:
    p = Path(getattr(settings, "BACKUP_ROOT", "") or os.environ.get("BACKUP_ROOT", "") or Path(settings.MEDIA_ROOT).parent / "backups")
    p.mkdir(parents=True, exist_ok=True)
    return p


def keep_days() -> int:
    try:
        return max(1, min(int(Setting.get("backup.keep_days", "14") or 14), 365))
    except ValueError:
        return 14


def _db_env():
    db = settings.DATABASES["default"]
    env = {**os.environ, "PGPASSWORD": db["PASSWORD"] or "", "PGSSLMODE": db.get("OPTIONS", {}).get("sslmode", "prefer")}
    args = ["-h", db["HOST"] or "127.0.0.1", "-p", str(db["PORT"] or 5432), "-U", db["USER"], "-d", db["NAME"]]
    return env, args


def listing() -> list[dict]:
    """Backups in the folder, newest first (including ones made by the server's nightly script, db_*.dump)."""
    out = {}
    for f in root().iterdir():
        m = re.match(r"^(ws_.+?)(_files\.tar\.gz|\.dump)$", f.name) or re.match(r"^(db|media)_(.+?)\.(dump|tar\.gz)$", f.name)
        if not m:
            continue
        if f.name.startswith(("db_", "media_")):
            key, part = "srv_" + m.group(2), ("db" if m.group(1) == "db" else "files")
        else:
            key, part = m.group(1), ("files" if m.group(2).startswith("_files") else "db")
        try:
            st = f.stat()
        except OSError:
            continue
        b = out.setdefault(key, {"name": key, "db": None, "files": None, "db_bytes": 0, "files_bytes": 0, "when": None, "server": key.startswith("srv_")})
        b[part], b[f"{part}_bytes"] = f.name, st.st_size
        when = dt.datetime.fromtimestamp(st.st_mtime, tz=dt.UTC)
        b["when"] = max(b["when"], when) if b["when"] else when
    return sorted((b for b in out.values() if b["db"]), key=lambda b: b["when"], reverse=True)


def find(name: str) -> dict | None:
    return next((b for b in listing() if b["name"] == name), None)


def queue(kind="backup", trigger="manual", user=None, name="") -> BackupRun:
    return BackupRun.objects.create(kind=kind, trigger=trigger, requested_by=user, name=name)


def busy() -> bool:
    return BackupRun.objects.filter(status__in=["queued", "running"]).exists()


# ── doing the work (jobs container) ──
def make_backup(run: BackupRun) -> BackupRun:
    stamp = timezone.localtime().strftime("%Y-%m-%d_%H%M")
    name, n = f"ws_{stamp}", 1
    while (root() / f"{name}.dump").exists():
        n += 1
        name = f"ws_{stamp}_{n}"
    dump, files = root() / f"{name}.dump", root() / f"{name}_files.tar.gz"
    env, args = _db_env()
    old = os.umask(0o077)
    try:
        r = subprocess.run(["pg_dump", *args, "--format=custom", "--no-owner", "--file", str(dump)], env=env, capture_output=True, text=True, timeout=3600)
        if r.returncode != 0:
            dump.unlink(missing_ok=True)
            raise RuntimeError("Database backup failed: " + (r.stderr.strip()[-400:] or f"pg_dump exit {r.returncode}"))
        media = Path(settings.MEDIA_ROOT)
        with tarfile.open(files, "w:gz") as tar:
            if media.exists():
                tar.add(str(media), arcname="media", filter=_skip_hidden)
    finally:
        os.umask(old)
    run.name, run.db_bytes, run.files_bytes = name, dump.stat().st_size, files.stat().st_size
    run.offsite = offsite_copy([dump, files])
    prune()
    return run


def _skip_hidden(ti):
    """Leave out temporary folders inside media (.upload-tmp, .restore_tmp)."""
    return None if any(part.startswith(".") for part in ti.name.split("/")[1:]) else ti


def prune() -> int:
    cutoff = timezone.now() - dt.timedelta(days=keep_days())
    n = 0
    for f in root().glob("ws_*"):
        try:
            if dt.datetime.fromtimestamp(f.stat().st_mtime, tz=dt.UTC) < cutoff:
                f.unlink()
                n += 1
        except OSError:
            pass
    return n


def _safe_extract(tar: tarfile.TarFile, dest: Path):
    dest = dest.resolve()
    for m in tar.getmembers():
        target = (dest / m.name).resolve()
        if not str(target).startswith(str(dest) + os.sep) and target != dest:
            raise RuntimeError(f"Unsafe path in backup: {m.name}")
        if m.issym() or m.islnk() or m.isdev():
            raise RuntimeError(f"Links and devices aren't allowed in a backup: {m.name}")
    tar.extractall(dest, filter="data")


def restore(run: BackupRun) -> BackupRun:
    b = find(run.name)
    if b is None:
        raise RuntimeError("That backup isn't in the backups folder any more.")
    # Safety first: a fresh backup of how things are right now.
    safety = BackupRun.objects.create(kind="backup", trigger="before-restore", status="running", requested_by=run.requested_by)
    make_backup(safety)
    BackupRun.objects.filter(pk=safety.pk).update(status="done", name=safety.name, db_bytes=safety.db_bytes, files_bytes=safety.files_bytes,
                                                  offsite=safety.offsite, finished_at=timezone.now(), message="Taken automatically before a restore")
    who, req = run.requested_by_id, run.created_at
    env, args = _db_env()
    r = subprocess.run(["pg_restore", *args, "--clean", "--if-exists", "--no-owner", "--single-transaction", str(root() / b["db"])],
                       env=env, capture_output=True, text=True, timeout=3600)
    if r.returncode != 0:
        raise RuntimeError("Database restore failed — nothing was changed: " + (r.stderr.strip()[-400:] or f"exit {r.returncode}"))
    if b["files"]:
        media = Path(settings.MEDIA_ROOT)
        media.mkdir(parents=True, exist_ok=True)
        tmp = media / ".restore_tmp"  # inside the media volume, so moving files in is instant
        if tmp.exists():
            subprocess.run(["rm", "-rf", str(tmp)], check=False)
        tmp.mkdir()
        with tarfile.open(root() / b["files"], "r:gz") as tar:
            _safe_extract(tar, tmp)
        src = tmp / "media"
        if src.exists():
            for child in media.iterdir():
                if not child.name.startswith("."):  # keep .upload-tmp and the restore folder itself
                    subprocess.run(["rm", "-rf", str(child)], check=False)
            for child in src.iterdir():
                if not child.name.startswith("."):
                    child.rename(media / child.name)
        subprocess.run(["rm", "-rf", str(tmp)], check=False)
    # The restored database has the backup's own history, so record this restore again.
    from django.db import connection
    connection.close()
    return BackupRun.objects.create(kind="restore", status="done", trigger="manual", name=b["name"], requested_by_id=who if _user_exists(who) else None,
                                    finished_at=timezone.now(), message=f"Restored {b['name']} (asked for at {timezone.localtime(req):%b %-d %-I:%M %p}). "
                                    f"Safety backup taken first: {safety.name}.")


def _user_exists(pk) -> bool:
    from apps.accounts.models import User
    return bool(pk) and User.objects.filter(pk=pk).exists()


def run_queued() -> dict:
    """Jobs loop: do anything queued, and the nightly backup."""
    done = []
    for run in BackupRun.objects.filter(status="queued").order_by("created_at")[:3]:
        if BackupRun.objects.filter(pk=run.pk, status="queued").update(status="running") != 1:
            continue
        run.refresh_from_db()
        try:
            if run.kind == "restore":
                result = restore(run)
                BackupRun.objects.filter(pk=run.pk).update(status="done", finished_at=timezone.now())  # may no longer exist after restore
                done.append(f"restored {result.name}")
            else:
                make_backup(run)
                run.status, run.finished_at = "done", timezone.now()
                run.save()
                done.append(run.name)
        except Exception as e:  # noqa: BLE001 — shown on the page
            BackupRun.objects.filter(pk=run.pk).update(status="failed", message=str(e)[:2000], finished_at=timezone.now())
            if run.kind == "restore" and not BackupRun.objects.filter(pk=run.pk).exists():
                BackupRun.objects.create(kind="restore", status="failed", name=run.name, message=str(e)[:2000], finished_at=timezone.now())
            done.append(f"failed: {str(e)[:120]}")
    nightly()
    return {"done": done}


def nightly(now=None) -> bool:
    if Setting.get("backup.nightly", "true") == "false":
        return False
    now = timezone.localtime(now or timezone.now())
    try:
        hour = int(Setting.get("backup.hour", "2") or 2)
    except ValueError:
        hour = 2
    if now.hour < hour:
        return False
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if BackupRun.objects.filter(kind="backup", trigger="nightly", created_at__gte=start).exists():
        return False
    queue("backup", "nightly")
    return True


# ── off-site copy: plain S3 API (Wasabi, Backblaze B2 S3, AWS…) with AWS Signature V4 ──
def s3_cfg() -> dict:
    return {"endpoint": (Setting.get("backup.s3_endpoint", "") or "").rstrip("/"), "region": Setting.get("backup.s3_region", "") or "us-east-1",
            "bucket": Setting.get("backup.s3_bucket", ""), "prefix": (Setting.get("backup.s3_prefix", "") or "weststar-one").strip("/"),
            "key": Setting.get("backup.s3_key", ""), "secret": Setting.get("backup.s3_secret", "")}


def _sign(key, msg):
    return hmac.new(key, msg.encode(), hashlib.sha256).digest()


def s3_put(path: Path, cfg: dict) -> int:
    """Upload one file (streamed, UNSIGNED-PAYLOAD over HTTPS). Returns the HTTP status."""
    host = urllib.parse.urlparse(cfg["endpoint"] if "://" in cfg["endpoint"] else "https://" + cfg["endpoint"]).netloc
    key = urllib.parse.quote(f"{cfg['prefix']}/{path.name}")
    url = f"https://{host}/{cfg['bucket']}/{key}"
    now = dt.datetime.now(dt.UTC)
    amz, day = now.strftime("%Y%m%dT%H%M%SZ"), now.strftime("%Y%m%d")
    size = path.stat().st_size
    headers = {"host": host, "x-amz-content-sha256": "UNSIGNED-PAYLOAD", "x-amz-date": amz}
    signed = ";".join(sorted(headers))
    canon = "\n".join(["PUT", f"/{cfg['bucket']}/{key}", "", "".join(f"{k}:{headers[k]}\n" for k in sorted(headers)), signed, "UNSIGNED-PAYLOAD"])
    scope = f"{day}/{cfg['region']}/s3/aws4_request"
    to_sign = "\n".join(["AWS4-HMAC-SHA256", amz, scope, hashlib.sha256(canon.encode()).hexdigest()])
    k = _sign(_sign(_sign(_sign(("AWS4" + cfg["secret"]).encode(), day), cfg["region"]), "s3"), "aws4_request")
    sig = hmac.new(k, to_sign.encode(), hashlib.sha256).hexdigest()
    auth = f"AWS4-HMAC-SHA256 Credential={cfg['key']}/{scope}, SignedHeaders={signed}, Signature={sig}"
    with open(path, "rb") as fh:
        req = urllib.request.Request(url, data=fh, method="PUT", headers={"x-amz-content-sha256": "UNSIGNED-PAYLOAD", "x-amz-date": amz,
                                                                          "Authorization": auth, "Content-Length": str(size)})
        try:
            with urllib.request.urlopen(req, timeout=600) as r:  # noqa: S310 — https endpoint from Settings
                return r.status
        except urllib.error.HTTPError as e:
            return e.code


def offsite_copy(paths) -> str:
    cfg = s3_cfg()
    if not (cfg["endpoint"] and cfg["bucket"] and cfg["key"] and cfg["secret"]):
        return ""
    for p in paths:
        try:
            code = s3_put(p, cfg)
        except Exception as e:  # noqa: BLE001 — the local backup is still good; just report the off-site problem
            return f"Off-site copy failed ({str(e)[:120]}) — the backup on the server is fine"
        if code not in (200, 201):
            return f"Off-site copy failed (HTTP {code}) — check Settings › Backup schedule & off-site copy"
    return "copied"
