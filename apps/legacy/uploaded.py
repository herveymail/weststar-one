"""Imports started from Settings › Import: files are uploaded through the browser, then the background
jobs worker does the work (so a big import never times out a web request) and reports progress."""
import os
import shutil
import tarfile
import traceback
import zipfile
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.core.crypto import decrypt

from .dumpreader import DumpError, DumpSource
from .importer import Importer
from .models import ImportRun

MAX_EXTRACT_BYTES = 50 * 1024**3   # 50 GB of old uploads, at most
MAX_EXTRACT_FILES = 500_000
KEEP_FILES_HOURS = 24               # after a practice run, so "Import now" can reuse them


def imports_root() -> str:
    path = os.path.join(settings.MEDIA_ROOT, "imports")
    os.makedirs(path, mode=0o750, exist_ok=True)
    return path


def _append(run: ImportRun, line: str) -> None:
    run.log = (run.log + line.rstrip() + "\n")[-200_000:]
    ImportRun.objects.filter(pk=run.pk).update(log=run.log)


def _safe_extract(archive: str, dest: str) -> None:
    """Unpacks a .zip or .tar(.gz) of the old uploads folder without letting any entry escape `dest`."""
    os.makedirs(dest, exist_ok=True)
    real_dest = os.path.realpath(dest)
    if zipfile.is_zipfile(archive):
        with zipfile.ZipFile(archive) as zf:
            infos = [i for i in zf.infolist() if not i.is_dir() and not i.filename.startswith("__MACOSX/")]
            if len(infos) > MAX_EXTRACT_FILES or sum(i.file_size for i in infos) > MAX_EXTRACT_BYTES:
                raise ValueError("The uploads archive is too large to unpack.")
            for info in infos:
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    continue  # skip symlinks
                target = os.path.realpath(os.path.join(dest, info.filename))
                if not target.startswith(real_dest + os.sep):
                    continue  # skip entries trying to leave the folder
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(info) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out, 1024 * 1024)
    elif tarfile.is_tarfile(archive):
        with tarfile.open(archive) as tf:
            members = [m for m in tf.getmembers() if m.isfile()]
            if len(members) > MAX_EXTRACT_FILES or sum(m.size for m in members) > MAX_EXTRACT_BYTES:
                raise ValueError("The uploads archive is too large to unpack.")
            tf.extractall(dest, members=members, filter="data")
    else:
        raise ValueError("The uploads file should be a .zip or .tar.gz of the old uploads folder.")


def _find_uploads_root(base: str) -> str | None:
    """The folder that holds tickets/, clients/ or projects/ (the zip may have an uploads/ folder on top)."""
    for dirpath, dirnames, _files in os.walk(base):
        if dirpath[len(base):].count(os.sep) > 4:
            dirnames[:] = []
            continue
        if {"tickets", "clients", "projects"} & set(dirnames):
            return dirpath
    return None


def process_queued() -> int:
    """Run the next queued import, if any. Called every few seconds by the jobs worker."""
    with transaction.atomic():
        run = ImportRun.objects.select_for_update(skip_locked=True).filter(status="queued").order_by("started_at").first()
        if run is None:
            return 0
        ImportRun.objects.filter(pk=run.pk).update(status="running")
    run.refresh_from_db()
    try:
        _append(run, f"{'Practice run' if run.dry_run else 'Import'} started {timezone.localtime():%b %d, %I:%M %p}.")
        _append(run, f"Reading the backup file {run.dump_name}…")
        src = DumpSource(os.path.join(run.work_dir, "dump"))
        _append(run, f"  found {len(src.columns)} tables")
        uploads_dir = None
        archive = os.path.join(run.work_dir, "uploads-archive")
        if os.path.exists(archive):
            unpacked = os.path.join(run.work_dir, "uploads")
            if not os.path.isdir(unpacked):
                _append(run, f"Unpacking {run.uploads_name}…")
                _safe_extract(archive, unpacked)
            uploads_dir = _find_uploads_root(unpacked)
            if uploads_dir is None:
                _append(run, "  ⚠ Couldn't find tickets/, clients/ or projects/ folders in that archive, so files are skipped.")
        keys = []
        for field in ("old_app_key", "old_encryption_key"):
            try:
                keys.append(decrypt(getattr(run, field)) if getattr(run, field) else "")
            except Exception:  # noqa: BLE001
                keys.append("")
        Importer(src, keys[0], keys[1], log=lambda line: _append(run, line), uploads_dir=uploads_dir).run(dry_run=run.dry_run, run=run)
        run.refresh_from_db()
        run.status = "done"
        _append(run, "Practice run finished: nothing was saved." if run.dry_run else "Import finished.")
    except (DumpError, ValueError, OSError) as e:
        run.refresh_from_db()
        run.status, run.error = "failed", str(e)[:2000]
        _append(run, f"✖ {e}")
    except Exception as e:  # noqa: BLE001
        run.refresh_from_db()
        run.status, run.error = "failed", f"{type(e).__name__}: {e}"[:2000]
        _append(run, "✖ The import stopped. Nothing from this run was saved.")
        _append(run, traceback.format_exc()[-3000:])
    run.finished_at = run.finished_at or timezone.now()
    if not run.dry_run or run.status == "failed":
        discard_files(run)
    run.save()
    return 1


def discard_files(run: ImportRun) -> None:
    """Deletes the uploaded backup/archive and forgets the old keys."""
    if run.work_dir and run.work_dir.startswith(imports_root()):
        shutil.rmtree(run.work_dir, ignore_errors=True)
    run.work_dir, run.old_app_key, run.old_encryption_key = "", "", ""
    ImportRun.objects.filter(pk=run.pk).update(work_dir="", old_app_key="", old_encryption_key="")


def cleanup_old_files() -> int:
    """Practice-run files are kept a day so "Import now" can reuse them; then they're deleted."""
    n = 0
    cutoff = timezone.now() - timedelta(hours=KEEP_FILES_HOURS)
    for run in ImportRun.objects.exclude(work_dir="").filter(status__in=["done", "failed"], finished_at__lt=cutoff):
        discard_files(run)
        n += 1
    return n
