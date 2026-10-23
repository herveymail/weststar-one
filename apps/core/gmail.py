"""The support mailbox through Google itself (no app passwords, no blocked email ports).

Settings › Email sending › "Connect Google mailbox": an admin signs in once as support@ (OAuth, the same
Google Cloud client as staff sign-in). The refresh token is stored encrypted and is then used to
  * send email with the Gmail API (HTTPS, port 443 — works where SMTP ports are blocked), and
  * read the inbox for email-to-ticket over IMAP with XOAUTH2 (no app password needed).
"""
import base64
import hashlib
import json
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

from .models import Setting

SCOPE = "openid email https://mail.google.com/"
SEND_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"


class GmailError(Exception):
    """Message is safe to show."""


def redirect_uri() -> str:
    return settings.APP_URL + "/settings/email/google/callback/"


def connected() -> bool:
    return bool(Setting.get("email.gmail_refresh_token", "") and Setting.get("email.gmail_address", ""))


def address() -> str:
    return Setting.get("email.gmail_address", "")


def start(session, hint: str = "") -> str:
    from apps.accounts.google import AUTH_URL, config
    c = config()
    if not (c["client_id"] and c["client_secret"]):
        raise GmailError("Fill in the Google client ID and secret in Settings › Sign-in & 2FA first (the same ones staff sign-in uses).")
    state, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    session["gmail_oauth"] = {"state": state, "verifier": verifier, "at": time.time()}
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {"client_id": c["client_id"], "redirect_uri": redirect_uri(), "response_type": "code", "scope": SCOPE, "state": state,
              "code_challenge": challenge, "code_challenge_method": "S256", "access_type": "offline", "prompt": "consent select_account",
              "include_granted_scopes": "false"}
    if hint:
        params["login_hint"] = hint
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def finish(session, params) -> str:
    from apps.accounts.google import TOKEN_URL, _claims, config
    saved = session.pop("gmail_oauth", None)
    if params.get("error"):
        raise GmailError("Google sign-in was cancelled.")
    if not saved or not secrets.compare_digest(str(params.get("state", "")), saved["state"]) or time.time() - saved["at"] > 600:
        raise GmailError("That link expired. Click Connect again.")
    c = config()
    tok = _token(TOKEN_URL, {"code": params.get("code", ""), "client_id": c["client_id"], "client_secret": c["client_secret"],
                             "redirect_uri": redirect_uri(), "grant_type": "authorization_code", "code_verifier": saved["verifier"]})
    if "https://mail.google.com/" not in tok.get("scope", ""):
        raise GmailError("Google didn't give mail access. Click Connect again and allow access to the mailbox.")
    if not tok.get("refresh_token"):
        raise GmailError("Google didn't send a long-term token. Remove the app's access for this mailbox in Google Account › Security, then connect again.")
    email = str(_claims(tok.get("id_token", "")).get("email", "")).lower()
    Setting.put("email.gmail_refresh_token", tok["refresh_token"], secret=True)
    Setting.put("email.gmail_address", email)
    cache.set("gmail_access_token", tok.get("access_token", ""), max(60, int(tok.get("expires_in", 3600)) - 300))
    return email


def disconnect():
    Setting.objects.filter(key__in=["email.gmail_refresh_token", "email.gmail_address"]).delete()
    cache.delete("gmail_access_token")


def _token(url, data) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:  # noqa: S310 — fixed https Google URL
            return json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read() or b"{}")
        except ValueError:
            err = {}
        if err.get("error") == "invalid_grant":
            raise GmailError("Google access for the mailbox was removed or expired. Reconnect it in Settings › Email sending.") from e
        raise GmailError(f"Google said: {err.get('error_description') or err.get('error') or e.code}") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise GmailError(f"Couldn't reach Google: {e}") from e


def access_token() -> str:
    tok = cache.get("gmail_access_token")
    if tok:
        return tok
    from apps.accounts.google import TOKEN_URL, config
    c = config()
    t = _token(TOKEN_URL, {"client_id": c["client_id"], "client_secret": c["client_secret"], "grant_type": "refresh_token",
                           "refresh_token": Setting.get("email.gmail_refresh_token", "")})
    cache.set("gmail_access_token", t["access_token"], max(60, int(t.get("expires_in", 3600)) - 300))
    return t["access_token"]


def send_raw(message_bytes: bytes) -> str:
    raw = base64.urlsafe_b64encode(message_bytes).decode()
    req = urllib.request.Request(SEND_URL, data=json.dumps({"raw": raw}).encode(),
                                 headers={"Authorization": f"Bearer {access_token()}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:  # noqa: S310 — fixed https Google URL
            return json.loads(r.read() or b"{}").get("id", "")
    except urllib.error.HTTPError as e:
        try:
            msg = json.loads(e.read() or b"{}").get("error", {}).get("message", "")
        except ValueError:
            msg = ""
        if e.code == 401:
            cache.delete("gmail_access_token")
        if e.code == 403 and ("has not been used" in msg or "disabled" in msg):
            raise GmailError("Turn on the Gmail API for your Google Cloud project (APIs & Services › Library › Gmail API › Enable).") from e
        raise GmailError(f"Gmail said: {msg or e.code}") from e


def imap_xoauth2(conn, user: str) -> None:
    tok = access_token()
    conn.authenticate("XOAUTH2", lambda _x: f"user={user}\x01auth=Bearer {tok}\x01\x01".encode())
