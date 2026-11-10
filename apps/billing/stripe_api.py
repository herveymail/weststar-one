"""Stripe, called directly over HTTPS (no SDK). Card and bank numbers never touch this server:
clients type them on Stripe's own Checkout page; we only keep Stripe's ids and the last 4 digits.

Settings › Payments: stripe.secret_key, stripe.publishable_key, stripe.webhook_secret.
"""
import hashlib
import hmac
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from apps.core.models import Setting

API = "https://api.stripe.com/v1/"
VERSION = "2024-06-20"


class StripeError(Exception):
    def __init__(self, message, code="", decline_code="", status=0, payload=None):
        super().__init__(message)
        self.code, self.decline_code, self.status, self.payload = code, decline_code, status, payload or {}

    @property
    def is_card_error(self):
        return self.status == 402 or self.payload.get("type") == "card_error"


# The events Weststar ONE listens for (the webhook guide and "Set up webhook for me" use this list).
WEBHOOK_EVENTS = ["checkout.session.completed", "checkout.session.async_payment_succeeded", "checkout.session.async_payment_failed",
                  "payment_intent.succeeded", "payment_intent.processing", "payment_intent.payment_failed",
                  "charge.refunded", "payment_method.detached"]


def configured() -> bool:
    return Setting.get("stripe.secret_key", "").startswith(("sk_", "rk_"))


def live() -> bool:
    return Setting.get("stripe.secret_key", "").startswith(("sk_live", "rk_live"))


def _flatten(data, prefix=""):
    out = []
    items = data.items() if isinstance(data, dict) else enumerate(data)
    for k, v in items:
        key = f"{prefix}[{k}]" if prefix else str(k)
        if isinstance(v, (dict, list)):
            out += _flatten(v, key)
        elif v is not None:
            out.append((key, "true" if v is True else "false" if v is False else str(v)))
    return out


def call(method: str, path: str, data: dict | None = None, idempotency_key: str = "") -> dict:
    if not configured():
        raise StripeError("Stripe isn't set up yet (Settings › Payments).")
    body = urllib.parse.urlencode(_flatten(data or {})).encode() if data and method != "GET" else None
    url = API + path + (("?" + urllib.parse.urlencode(_flatten(data))) if data and method == "GET" else "")
    req = urllib.request.Request(url, data=body, method=method, headers={
        "Authorization": f"Bearer {Setting.get('stripe.secret_key')}", "Stripe-Version": VERSION,
        "Content-Type": "application/x-www-form-urlencoded", **({"Idempotency-Key": idempotency_key} if idempotency_key else {})})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — fixed https Stripe URL
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read() or b"{}").get("error", {})
        except ValueError:
            err = {}
        raise StripeError(err.get("message") or f"Stripe said {e.code}", err.get("code", ""), err.get("decline_code", ""), e.code, err) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise StripeError(f"Couldn't reach Stripe: {e}") from e


def verify_webhook(payload: bytes, sig_header: str, tolerance=300) -> dict:
    """Checks the Stripe-Signature header (HMAC-SHA256 with the webhook signing secret)."""
    secret = Setting.get("stripe.webhook_secret", "")
    if not secret:
        raise StripeError("No webhook signing secret saved (Settings › Payments).")
    parts = dict(p.split("=", 1) for p in (sig_header or "").split(",") if "=" in p)
    sigs = [v for k, v in (p.split("=", 1) for p in (sig_header or "").split(",") if "=" in p) if k == "v1"]
    ts = parts.get("t", "")
    if not ts.isdigit() or abs(time.time() - int(ts)) > tolerance:
        raise StripeError("Old or missing webhook timestamp.")
    expected = hmac.new(secret.encode(), f"{ts}.".encode() + payload, hashlib.sha256).hexdigest()
    if not any(hmac.compare_digest(expected, s) for s in sigs):
        raise StripeError("Webhook signature doesn't match.")
    return json.loads(payload)


def key_mode(key: str) -> str:
    """'live', 'test' or '' for a pk_/sk_/rk_ key."""
    k = (key or "").strip()
    return "live" if "_live_" in k else "test" if "_test_" in k else ""


def check() -> dict:
    """Settings › Payments › Check connection: who the keys belong to and whether the account can take payments."""
    from django.utils import timezone
    pk, sk = Setting.get("stripe.publishable_key", ""), Setting.get("stripe.secret_key", "")
    out = {"ok": False, "problems": [], "mode": key_mode(sk), "checked_at": timezone.now().isoformat()}
    if not sk:
        out["problems"].append("No secret key saved yet.")
        return out
    if not pk.startswith("pk_"):
        out["problems"].append("The publishable key should start with pk_live_ or pk_test_.")
    elif key_mode(pk) != key_mode(sk):
        out["problems"].append(f"The publishable key is a {key_mode(pk)} key but the secret key is a {key_mode(sk)} key. Use both from the same mode.")
    try:
        acct = call("GET", "account")
    except StripeError as e:
        out["problems"].append(f"Stripe didn't accept the secret key: {e}")
        return out
    bp = acct.get("business_profile") or {}
    out.update(ok=True, account=acct.get("id", ""), name=bp.get("name") or (acct.get("settings") or {}).get("dashboard", {}).get("display_name") or acct.get("email") or "",
               charges=bool(acct.get("charges_enabled")), payouts=bool(acct.get("payouts_enabled")))
    if not out["charges"]:
        out["problems"].append("Stripe hasn't turned on payments for this account yet. Finish activating it in Stripe (business details and bank account).")
    elif not out["payouts"]:
        out["problems"].append("Payouts to your bank aren't on yet. Add or verify the bank account in Stripe › Settings › Payouts.")
    return out


def setup_webhook(url: str) -> str:
    """Create (or replace) this app's webhook endpoint in Stripe and return its signing secret."""
    existing = call("GET", "webhook_endpoints", {"limit": 100}).get("data", [])
    for ep in existing:
        if ep.get("url", "").rstrip("/") == url.rstrip("/"):
            call("DELETE", f"webhook_endpoints/{ep['id']}")  # its secret can't be read back, so start fresh
    ep = call("POST", "webhook_endpoints", {"url": url, "enabled_events": WEBHOOK_EVENTS, "api_version": VERSION,
                                            "description": "Weststar ONE (invoices, payments, AutoPay)"})
    return ep.get("secret", "")
