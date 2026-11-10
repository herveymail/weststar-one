class SecurityHeadersMiddleware:
    """Strict Content-Security-Policy: scripts and styles only from this site (htmx is served locally).
    form-action also allows Stripe Checkout and Google sign-in: "Pay now", "Set up AutoPay" and "Connect Google
    mailbox" are forms whose answer is a redirect there, and browsers block that redirect unless it's listed."""

    CSP = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; img-src 'self' data:; connect-src 'self'; "
        "frame-src 'self'; frame-ancestors 'none'; form-action 'self' https://checkout.stripe.com https://accounts.google.com; base-uri 'self'; object-src 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.CSP)
        response.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        if "Server" in response:
            del response["Server"]
        return response


class TimingMiddleware:
    """Times every page and save. Adds a Server-Timing header (visible in the browser's network tab) and records
    anything slower than SLOW_REQUEST_MS on Settings › Speed & server health, with how much was database time."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import time

        from django.conf import settings
        from django.db import connection
        stats = {"n": 0, "t": 0.0}

        def wrap(execute, sql, params, many, context):
            a = time.perf_counter()
            try:
                return execute(sql, params, many, context)
            finally:
                stats["n"] += 1
                stats["t"] += time.perf_counter() - a

        start = time.perf_counter()
        with connection.execute_wrapper(wrap):
            response = self.get_response(request)
        total = (time.perf_counter() - start) * 1000
        db = stats["t"] * 1000
        response["Server-Timing"] = f'app;dur={total - db:.0f}, db;dur={db:.0f};desc="{stats["n"]} queries"'
        limit = getattr(settings, "SLOW_REQUEST_MS", 1000)
        if total >= limit and not request.path.startswith(("/static/", "/stripe/webhook/")):
            try:
                from .models import SlowRequest
                user = getattr(request, "user", None)
                SlowRequest.objects.create(method=request.method[:8], path=request.get_full_path()[:300], status=response.status_code,
                                           total_ms=int(total), db_ms=int(db), queries=stats["n"],
                                           user=(user.email if user is not None and user.is_authenticated else "")[:150])
            except Exception:  # noqa: BLE001 — timing must never break a page
                pass
        return response
