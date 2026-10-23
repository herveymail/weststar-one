"""
Encryption for secrets at rest (AES-256-GCM, random 96-bit nonce).

Stored format: "v1:" + base64(nonce | ciphertext+tag). The key is APP_ENCRYPTION_KEY; keys listed in
APP_ENCRYPTION_KEYS_OLD still decrypt, so the key can be rotated (values are re-encrypted when saved).
"""
import base64
import hashlib
import hmac
import os
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings


class DecryptError(Exception):
    pass


def _raw(key_b64: str) -> bytes:
    return base64.b64decode(key_b64)


def _keys() -> list[bytes]:
    return [_raw(settings.APP_ENCRYPTION_KEY)] + [_raw(k) for k in settings.APP_ENCRYPTION_KEYS_OLD]


def _derive(key: bytes, purpose: bytes) -> bytes:
    return HKDF(algorithm=SHA256(), length=32, salt=None, info=b"weststar-one:" + purpose).derive(key)


def encrypt(plain: str | None) -> str:
    if plain is None or plain == "":
        return ""
    nonce = os.urandom(12)
    key = _derive(_keys()[0], b"aes-gcm")
    ct = AESGCM(key).encrypt(nonce, plain.encode("utf-8"), None)
    return "v1:" + base64.b64encode(nonce + ct).decode()


def decrypt(stored: str | None) -> str:
    if not stored:
        return ""
    if not stored.startswith("v1:"):
        raise DecryptError("Unknown ciphertext format")
    raw = base64.b64decode(stored[3:])
    nonce, ct = raw[:12], raw[12:]
    for key in _keys():
        try:
            return AESGCM(_derive(key, b"aes-gcm")).decrypt(nonce, ct, None).decode("utf-8")
        except Exception:  # noqa: BLE001 — try the next key
            continue
    raise DecryptError("Could not decrypt with any configured key (check APP_ENCRYPTION_KEY)")


def keyed_hashes(value: str) -> list[str]:
    """HMAC of value under the current and every old key (separate HMAC key derived from each)."""
    return [hmac.new(_derive(k, b"hmac"), value.encode(), hashlib.sha256).hexdigest() for k in _keys()]


def keyed_hash(value: str) -> str:
    return keyed_hashes(value)[0]


def token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
