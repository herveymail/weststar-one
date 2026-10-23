from django.apps import AppConfig


class ToolsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.tools"
    label = "tools"

    def ready(self):
        from . import modules  # noqa: F401 — registers this app's menu modules
