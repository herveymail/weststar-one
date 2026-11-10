"""Public legal pages: /legal/privacy/ and /legal/terms/ (client portal terms). No sign-in needed."""
from django.http import Http404
from django.shortcuts import render

from . import legal
from .models import Setting

PUBLIC = {"privacy": "privacy", "terms": "portal_terms"}


def page(request, slug):
    key = PUBLIC.get(slug)
    if not key:
        raise Http404
    from .branding import login_brand, logo_url
    resp = render(request, "core/legal_public.html", {
        **login_brand(), "company": Setting.get("company.name", "") or "Weststar MSP", "logo_url": logo_url(),
        "doc_title": legal.title(key), "body": legal.html(key), "slug": slug})
    resp["X-Robots-Tag"] = "noindex"
    return resp
