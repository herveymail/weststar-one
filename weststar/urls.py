from django.urls import include, path

urlpatterns = [path("", include("apps.core.urls"))]
handler403 = "apps.core.views.forbidden"
handler404 = "apps.core.views.not_found"
