"""Your logo (Settings › Branding): shown on the sign-in page, in the menu and in the client portal.
Served publicly at /brand/logo/ (the sign-in page needs it before anyone signs in)."""
import hashlib
import os
import re

from django.conf import settings
from django.http import FileResponse, Http404

from .models import Setting

TYPES = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg", "webp": "image/webp", "svg": "image/svg+xml"}
MAX_BYTES = 2 * 1024 * 1024
UNSAFE_SVG = re.compile(rb"<\s*script|\bon[a-z]+\s*=|javascript:|<\s*foreignObject|<\s*iframe|<\s*embed|<\s*object|xlink:href\s*=\s*[\"'](?!#)|href\s*=\s*[\"'](?!#)", re.I)


def _dir():
    d = os.path.join(settings.MEDIA_ROOT, "brand")
    os.makedirs(d, exist_ok=True)
    return d


def logo_url() -> str:
    name = Setting.get("brand.logo", "")
    return f"/brand/logo/?v={name.split('.')[0][-8:]}" if name else ""


def save_logo(f) -> str:
    """Returns '' when saved, else the problem in plain words."""
    ext = (f.name.rsplit(".", 1)[-1] if "." in f.name else "").lower()
    if ext not in TYPES:
        return "The logo must be a PNG, JPG, WebP or SVG file."
    if f.size > MAX_BYTES:
        return "The logo must be 2 MB or smaller."
    data = f.read()
    if ext == "svg" and UNSAFE_SVG.search(data):
        return "That SVG has scripts or links in it. Export a plain SVG, or use a PNG."
    if ext in ("png", "jpg", "jpeg", "webp") and not (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff" or data[8:12] == b"WEBP"):
        return "That file isn't a real image."
    name = f"logo-{hashlib.sha256(data).hexdigest()[:12]}.{ext}"
    for old in os.listdir(_dir()):
        if old.startswith("logo-"):
            os.remove(os.path.join(_dir(), old))
    with open(os.path.join(_dir(), name), "wb") as out:
        out.write(data)
    Setting.put("brand.logo", name)
    return ""


def remove_logo():
    for old in os.listdir(_dir()):
        if old.startswith("logo-"):
            os.remove(os.path.join(_dir(), old))
    Setting.objects.filter(key="brand.logo").delete()


def logo_view(request):
    name = Setting.get("brand.logo", "")
    path = os.path.join(_dir(), name) if name and "/" not in name and ".." not in name else ""
    if not path or not os.path.exists(path):
        raise Http404
    r = FileResponse(open(path, "rb"), content_type=TYPES.get(name.rsplit(".", 1)[-1], "application/octet-stream"))
    r["Cache-Control"] = "public, max-age=86400"
    r["X-Content-Type-Options"] = "nosniff"
    r["Content-Security-Policy"] = "default-src 'none'; style-src 'unsafe-inline'; sandbox"
    return r
