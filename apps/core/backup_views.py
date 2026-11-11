"""Settings › Backups page (see backups.py)."""
from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import redirect, render

from . import backups
from .audit import audit
from .models import BackupRun, Setting
from .permissions import can


def _admin(request):
    if not can(request.user, "admin", "manage"):
        raise PermissionDenied


def backups_page(request):
    _admin(request)
    if request.method == "POST":
        a = request.POST.get("action")
        if backups.busy():
            messages.error(request, "A backup or restore is already running — wait for it to finish.")
        elif a == "backup":
            backups.queue("backup", "manual", request.user)
            audit(request, "backup", "system", None, "Backup requested", area="admin")
            messages.success(request, "Backup started. It takes a minute or two — this page updates by itself.")
        elif a == "restore":
            name = request.POST.get("name", "")
            if request.POST.get("confirm", "").strip() != "RESTORE":
                messages.error(request, "Type RESTORE in capitals to confirm.")
            elif not backups.find(name):
                messages.error(request, "That backup isn't there any more.")
            else:
                backups.queue("restore", "manual", request.user, name=name)
                audit(request, "restore", "system", None, f"Restore of {name} requested", area="admin")
                messages.success(request, f"Restoring {name}. A safety backup is taken first. Everyone will need to sign in again afterwards.")
        return redirect("/settings/backups/")
    runs = list(BackupRun.objects.select_related("requested_by")[:15])
    ctx = {"backups": backups.listing()[:60], "runs": runs, "busy": backups.busy(), "keep": backups.keep_days(),
           "nightly": Setting.get("backup.nightly", "true") != "false", "hour": Setting.get("backup.hour", "2") or "2",
           "offsite": bool(backups.s3_cfg()["bucket"]), "folder": str(backups.root()),
           "last": next((r for r in runs if r.kind == "backup" and r.status == "done"), None)}
    if request.headers.get("HX-Request") and request.GET.get("part") == "status":
        return render(request, "core/_backup_status.html", ctx)
    return render(request, "core/backups.html", ctx)


def download(request, name, part):
    _admin(request)
    b = backups.find(name)
    if b is None or part not in ("db", "files") or not b[part]:
        raise Http404
    audit(request, "download", "system", None, f"Downloaded backup {b[part]}", area="admin")
    r = FileResponse(open(backups.root() / b[part], "rb"), as_attachment=True, filename=b[part])  # noqa: SIM115 — FileResponse closes it
    r["Cache-Control"] = "private, no-store"
    return r
