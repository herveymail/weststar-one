import mimetypes
import os

from django.conf import settings
from django.core.exceptions import ValidationError

from apps.core.audit import audit

from .models import ALLOWED_EXT, Upload


def max_bytes() -> int:
    from apps.core.models import Setting
    try:
        mb = int(Setting.get("tickets.max_upload_mb", "") or settings.MAX_UPLOAD_MB)
    except ValueError:
        mb = settings.MAX_UPLOAD_MB
    return max(1, min(mb, 200)) * 1024 * 1024


def check(f) -> str:
    """Returns a problem in plain words, or '' if the file is fine."""
    name = os.path.basename(f.name or "")
    ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    if ext not in ALLOWED_EXT:
        return f"“{name}” is not an allowed file type."
    if f.size > max_bytes():
        return f"“{name}” is larger than {max_bytes() // 1024 // 1024} MB."
    if f.size == 0:
        return f"“{name}” is empty."
    return ""


def save_uploads(request, files, *, kind, ticket=None, message=None, client=None, project=None) -> list[str]:
    problems = []
    for f in files[:20]:
        p = check(f)
        if p:
            problems.append(p)
            continue
        name = os.path.basename(f.name)[:255]
        u = Upload(kind=kind, ticket=ticket, message=message, client=client, project=project, original_name=name,
                   content_type=(mimetypes.guess_type(name)[0] or "application/octet-stream")[:100], size=f.size,
                   uploaded_by=request.user, notes=(request.POST.get("notes", "") or "")[:500])
        u.file.save(name, f, save=True)
        audit(request, "upload", "file", u.pk, f"Uploaded {name}", area=u.area)
    if len(files) > 20:
        problems.append("Only the first 20 files were uploaded.")
    if problems:
        raise ValidationError(problems)
    return []
