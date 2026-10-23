"""Settings › Import from old Weststar One: upload the old backup (and uploads folder), practice run, import."""
import os
import secrets

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.core.audit import audit
from apps.core.crypto import encrypt
from apps.core.permissions import can

from .crypto import parse_old_config
from .models import ImportRun
from .uploaded import discard_files, imports_root

MAX_DUMP_BYTES = 5 * 1024**3
MAX_UPLOADS_BYTES = 50 * 1024**3


def _need_admin(request):
    if not can(request.user, "admin", "manage"):
        raise PermissionDenied


def _save(upload, path):
    with open(path, "wb") as out:
        for chunk in upload.chunks():
            out.write(chunk)


@login_required
def import_page(request):
    if not can(request.user, "admin"):
        raise PermissionDenied
    error = ""
    if request.method == "POST":
        _need_admin(request)
        dump, archive, config = request.FILES.get("dump"), request.FILES.get("uploads"), request.FILES.get("config")
        app_key, enc_key = request.POST.get("old_app_key", "").strip(), request.POST.get("old_encryption_key", "").strip()
        if config:
            if config.size > 1024 * 1024:
                error = "That config.php is too big to be the old app's settings file."
            else:
                found = parse_old_config(config.read().decode("utf-8", "replace"))
                app_key = app_key or found.get("APP_KEY", "")
                enc_key = enc_key or found.get("ENCRYPTION_KEY", "")
                if not (found.get("APP_KEY") or found.get("ENCRYPTION_KEY")):
                    error = "That config.php doesn't have APP_KEY or ENCRYPTION_KEY in it."
        if not dump:
            error = error or "Choose the old database backup file (.sql, .sql.gz or .zip)."
        elif dump.size > MAX_DUMP_BYTES:
            error = "That backup file is larger than 5 GB."
        elif not dump.name.lower().endswith((".sql", ".gz", ".zip")):
            error = "The backup should be a .sql, .sql.gz or .zip file."
        if archive and archive.size > MAX_UPLOADS_BYTES:
            error = error or "The uploads archive is larger than 50 GB."
        if archive and not archive.name.lower().endswith((".zip", ".tar", ".tgz", ".tar.gz", ".gz")):
            error = error or "The uploads folder should be a .zip or .tar.gz file."
        if not error:
            work = os.path.join(imports_root(), secrets.token_hex(16))
            os.makedirs(work, mode=0o750)
            _save(dump, os.path.join(work, "dump"))
            if archive:
                _save(archive, os.path.join(work, "uploads-archive"))
            run = ImportRun.objects.create(
                status="queued", dry_run=request.POST.get("mode") != "import", work_dir=work, requested_by=request.user,
                dump_name=os.path.basename(dump.name)[:255], uploads_name=os.path.basename(archive.name)[:255] if archive else "",
                old_app_key=encrypt(app_key) if app_key else "", old_encryption_key=encrypt(enc_key) if enc_key else "",
            )
            audit(request, "import_start", "import", run.pk, f"Uploaded {run.dump_name} for a {'practice run' if run.dry_run else 'import'}", area="admin")
            return redirect(f"/settings/import/?run={run.pk}")
    runs = list(ImportRun.objects.select_related("requested_by")[:20])
    current = None
    if request.GET.get("run", "").isdigit():
        current = ImportRun.objects.filter(pk=int(request.GET["run"])).first()
    current = current or next((r for r in runs if r.status in ("queued", "running")), None) or (runs[0] if runs else None)
    return render(request, "legacy/import.html", {"runs": runs, "current": current, "error": error,
                                                 "can_manage": can(request.user, "admin", "manage")}, status=400 if error else 200)


@login_required
def import_status(request, pk):
    """The progress box, refreshed every few seconds while an import runs."""
    if not can(request.user, "admin"):
        raise PermissionDenied
    run = get_object_or_404(ImportRun, pk=pk)
    if run.status in ("done", "failed") and request.headers.get("HX-Request"):
        r = HttpResponse(status=204)
        r["HX-Refresh"] = "true"  # finished: reload once so the history and buttons are up to date
        return r
    return render(request, "legacy/_status.html", {"current": run, "can_manage": can(request.user, "admin", "manage")})


@login_required
@require_POST
def import_again(request, pk):
    """After a practice run: do the real import with the same files (no second upload)."""
    _need_admin(request)
    practice = get_object_or_404(ImportRun, pk=pk, dry_run=True, status="done")
    if not practice.work_dir or not os.path.isdir(practice.work_dir):
        messages.error(request, "Those files were already removed. Upload the backup again.")
        return redirect("/settings/import/")
    run = ImportRun.objects.create(status="queued", dry_run=False, work_dir=practice.work_dir, requested_by=request.user,
                                   dump_name=practice.dump_name, uploads_name=practice.uploads_name,
                                   old_app_key=practice.old_app_key, old_encryption_key=practice.old_encryption_key)
    ImportRun.objects.filter(pk=practice.pk).update(work_dir="", old_app_key="", old_encryption_key="")
    audit(request, "import_start", "import", run.pk, f"Import of {run.dump_name} (after a practice run)", area="admin")
    return redirect(f"/settings/import/?run={run.pk}")


@login_required
@require_POST
def import_discard(request, pk):
    _need_admin(request)
    run = get_object_or_404(ImportRun, pk=pk)
    if run.status in ("queued", "running"):
        messages.error(request, "That import is still running.")
    else:
        discard_files(run)
        messages.success(request, "The uploaded backup files were deleted.")
    return redirect(f"/settings/import/?run={run.pk}")
