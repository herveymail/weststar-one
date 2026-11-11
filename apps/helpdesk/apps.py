from django.apps import AppConfig


class HelpdeskConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.helpdesk"
    label = "helpdesk"

    def ready(self):
        from . import modules  # noqa: F401 — ticket templates and recurring tickets pages
