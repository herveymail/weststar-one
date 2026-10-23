from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from apps.core.audit import audit
from apps.core.permissions import can
from apps.crm.models import Client, Project

from .models import INLINE_EXT, Upload
from .services import save_uploads


@login_required
def download(request, pk):
    u = get_object_or_404(Upload, pk=pk)
    if not can(request.user, u.area):
        raise PermissionDenied
    try:
        fh = u.file.open("rb")
    except (FileNotFoundError, OSError) as e:
        raise Http404("This file is missing on the server.") from e
    inline = request.GET.get("view") == "1" and u.ext in INLINE_EXT
    resp = FileResponse(fh, as_attachment=not inline, filename=u.original_name,
                        content_type=u.content_type if inline else "application/octet-stream")
    resp["X-Content-Type-Options"] = "nosniff"
    resp["Content-Security-Policy"] = "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'; sandbox"
    resp["Cache-Control"] = "private, no-store"
    return resp


@login_required
@require_POST
def delete(request, pk):
    u = get_object_or_404(Upload, pk=pk)
    if not can(request.user, u.area, "manage") and not (u.uploaded_by_id == request.user.pk and can(request.user, u.area, "edit")):
        raise PermissionDenied
    name = u.original_name
    u.file.delete(save=False)
    u.delete()
    audit(request, "delete", "file", pk, f"Deleted file {name}", area=u.area)
    r = HttpResponse(status=204)
    r["HX-Trigger"] = "filesChanged"
    return r


def _owner(kind, pk):
    if kind == "client":
        return {"client": get_object_or_404(Client, pk=pk)}
    if kind == "project":
        return {"project": get_object_or_404(Project, pk=pk)}
    raise Http404


@login_required
def file_list(request, kind, pk):
    """Files tab for a client or project; POST uploads more."""
    area = "clients" if kind == "client" else "projects"
    if not can(request.user, area):
        raise PermissionDenied
    owner = _owner(kind, pk)
    error = ""
    if request.method == "POST":
        if not can(request.user, area, "edit"):
            raise PermissionDenied
        try:
            save_uploads(request, request.FILES.getlist("files"), kind=kind, **owner)
        except ValidationError as e:
            error = " ".join(e.messages)
    files = Upload.objects.filter(kind=kind, **{f"{kind}": list(owner.values())[0]}).select_related("uploaded_by")
    return render(request, "files/_list.html", {"files": files, "kind": kind, "pk": pk, "error": error,
                                                "can_edit": can(request.user, area, "edit"), "can_manage": can(request.user, area, "manage")})
