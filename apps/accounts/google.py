"""Sign in with Google Workspace (OpenID Connect, authorization-code flow with PKCE).

Set up once in Google Cloud Console (see README › Google sign-in), then in Settings › Sign-in & 2FA
fill in the client ID, client secret and the allowed Workspace domain(s).

Safety rules:
* Only existing, active staff can sign in this way. A Google account never creates a user by itself:
  an admin adds people in Staff users first, and the Google email must match.
* The Google account must belong to one of the allowed Workspace domains (the `hd` claim, which
  Google only sets for Workspace accounts, not personal Gmail) and have a verified email.
* state, nonce and PKCE protect the round trip; the ID token comes straight from Google's token
  endpoint over TLS with our client secret (OIDC Core 3.1.3.7), and its issuer, audience, expiry
  and nonce are all checked.
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

from apps.core.models import Setting

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105 — a URL, not a password
ISSUERS = ("https://accounts.google.com", "accounts.google.com")


class GoogleSignInError(Exception):
    """Message is safe to show the person."""


def config() -> dict:
    return {
        "client_id": Setting.get("google.client_id", "").strip(),
        "client_secret": Setting.get("google.client_secret", "").strip(),
        "domains": [d.strip().lower().lstrip("@") for d in Setting.get("google.domains", "").replace(";", ",").split(",") if d.strip()],
    }


def enabled() -> bool:
    c = config()
    return bool(c["client_id"] and c["client_secret"] and c["domains"])


def counts_as_2fa() -> bool:
    return Setting.get("google.counts_as_2fa", "yes") != "no"


def redirect_uri() -> str:
    return settings.APP_URL + "/login/google/callback/"


def start(session) -> str:
    """Remember state/nonce/PKCE in the session and return Google's sign-in URL."""
    c = config()
    state, nonce, verifier = secrets.token_urlsafe(24), secrets.token_urlsafe(24), secrets.token_urlsafe(48)
    session["google_oidc"] = {"state": state, "nonce": nonce, "verifier": verifier, "at": time.time()}
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    params = {
        "client_id": c["client_id"], "redirect_uri": redirect_uri(), "response_type": "code", "scope": "openid email profile",
        "state": state, "nonce": nonce, "code_challenge": challenge, "code_challenge_method": "S256", "prompt": "select_account",
    }
    if len(c["domains"]) == 1:
        params["hd"] = c["domains"][0]  # only a hint for Google's account picker; enforced again below
    return AUTH_URL + "?" + urllib.parse.urlencode(params)


def _post(url: str, data: dict) -> dict:
    req = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urllib.request.urlopen(req, timeout=10) as r:  # noqa: S310 — fixed https URL
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        raise GoogleSignInError("Google didn't accept the sign-in. Try again.") from e
    except (urllib.error.URLError, TimeoutError, ValueError) as e:
        raise GoogleSignInError("Couldn't reach Google. Try again in a minute.") from e


def _claims(id_token: str) -> dict:
    try:
        payload = id_token.split(".")[1]
        return json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (IndexError, ValueError) as e:
        raise GoogleSignInError("Google sent back something unexpected. Try again.") from e


def finish(session, params) -> str:
    """Check Google's reply and return the verified Workspace email address."""
    saved = session.pop("google_oidc", None)
    if params.get("error"):
        raise GoogleSignInError("Google sign-in was cancelled.")
    if not saved or not secrets.compare_digest(str(params.get("state", "")), saved["state"]) or time.time() - saved["at"] > 600:
        raise GoogleSignInError("That sign-in link expired. Start again.")
    c = config()
    tokens = _post(TOKEN_URL, {
        "code": params.get("code", ""), "client_id": c["client_id"], "client_secret": c["client_secret"],
        "redirect_uri": redirect_uri(), "grant_type": "authorization_code", "code_verifier": saved["verifier"],
    })
    claims = _claims(tokens.get("id_token", ""))
    now = time.time()
    if claims.get("iss") not in ISSUERS or claims.get("aud") != c["client_id"] or float(claims.get("exp", 0)) < now - 60:
        raise GoogleSignInError("Google sent back something unexpected. Try again.")
    if not secrets.compare_digest(str(claims.get("nonce", "")), saved["nonce"]):
        raise GoogleSignInError("That sign-in link expired. Start again.")
    email = str(claims.get("email", "")).strip().lower()
    hd = str(claims.get("hd", "")).lower()
    if not claims.get("email_verified") or not email:
        raise GoogleSignInError("Your Google account's email isn't verified.")
    if hd not in c["domains"] or email.rsplit("@", 1)[-1] not in c["domains"]:
        raise GoogleSignInError("Use your company Google Workspace account to sign in.")
    return email
