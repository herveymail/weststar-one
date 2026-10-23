from django.http import HttpResponsePermanentRedirect
from django.urls import include, path, re_path

urlpatterns = [
    path("client-portal/", include("apps.portal.urls")),
    # old/short address → the client portal
    re_path(r"^portal(?:/(?P<rest>.*))?$", lambda request, rest="": HttpResponsePermanentRedirect(f"/client-portal/{rest or ''}")),
    path("", include("apps.core.urls")),
]
handler403 = "apps.core.views.forbidden"
handler404 = "apps.core.views.not_found"
