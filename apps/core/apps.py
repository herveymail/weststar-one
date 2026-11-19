from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core"
    label = "core"

    def ready(self):
        from django.core.signals import got_request_exception

        from .support import record_exception
        got_request_exception.connect(record_exception, dispatch_uid="ws-error-events")
