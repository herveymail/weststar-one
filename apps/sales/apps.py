from django.apps import AppConfig


class SalesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sales"
    label = "sales"

    def ready(self):
        from . import modules  # noqa: F401 — registers this app's menu modules
