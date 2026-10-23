"""Staff alerts in Google Chat (Settings › Google Chat webhook). Best-effort: never raises."""
import json
import logging
import urllib.request

from django.conf import settings

from .models import Setting

log = logging.getLogger("weststar.notify")


def chat(text: str) -> bool:
    url = Setting.get("chat.webhook_url", "")
    if not url.startswith("https://chat.googleapis.com/"):
        return False
    req = urllib.request.Request(url, data=json.dumps({"text": text[:3500]}).encode(), headers={"Content-Type": "application/json; charset=UTF-8"})
    try:
        with urllib.request.urlopen(req, timeout=5):  # noqa: S310 — https Google Chat URL only (checked above)
            return True
    except Exception as e:  # noqa: BLE001
        log.warning("Google Chat alert failed: %s", e)
        return False


def ticket_email(row) -> None:
    if row.result not in ("ticket", "reply") or not row.ticket_id:
        return
    t = row.ticket
    if row.result == "ticket" and Setting.get("chat.notify_new_ticket", "true") != "false":
        chat(f"🎫 New ticket {t.number} from {row.from_name or row.from_address}{' (' + t.client.name + ')' if t.client_id else ''}\n*{t.subject}*\n{settings.APP_URL}/tickets/{t.pk}/")
    elif row.result == "reply" and Setting.get("chat.notify_client_replies", "true") != "false":
        chat(f"↩️ {row.from_name or row.from_address} replied on {t.number}: {t.subject}\n{settings.APP_URL}/tickets/{t.pk}/")
