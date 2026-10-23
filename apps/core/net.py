from django.conf import settings


def client_ip(request) -> str:
    """The real client IP. Behind our proxy (TRUST_PROXY=true) we take the RIGHTMOST X-Forwarded-For
    entry — the one our own proxy added — never the leftmost one, which the client can forge."""
    if request is None:
        return ""
    if settings.TRUST_PROXY:
        xff = request.META.get("HTTP_X_FORWARDED_FOR", "")
        parts = [p.strip() for p in xff.split(",") if p.strip()]
        if parts:
            return parts[-1][:64]
    return (request.META.get("REMOTE_ADDR") or "")[:64]
