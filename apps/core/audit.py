from .models import AuditLog
from .net import client_ip


def audit(request, action: str, entity: str, entity_id=None, summary: str = "", changes=None, area: str = "", user=None):
    AuditLog.objects.create(
        user=user if user is not None else (request.user if request is not None and getattr(request, "user", None) and request.user.is_authenticated else None),
        action=action, entity=entity, entity_id="" if entity_id is None else str(entity_id),
        area=area, summary=summary[:500], changes=changes, ip=client_ip(request) if request is not None else "",
    )
