"""Python ports of the old PHP app's decryption routines.

The importer uses these to read secrets encrypted with the OLD keys (APP_KEY / ENCRYPTION_KEY in the
old config/config.php) and re-encrypt them with the new APP_ENCRYPTION_KEY. Plaintext stays in memory.

  decrypt_value()   includes/functions.php — AES-256-CBC, key = hex2bin(ENCRYPTION_KEY),
                    stored as base64( iv(16 raw bytes) . "::" . base64(ciphertext) ).
                    HR fields, and (with a "nenc:" prefix) network Wi-Fi passwords / ISP accounts.
  decrypt_setting() includes/security.php —
                    "v2:" base64(iv12 . tag16 . ct), AES-256-GCM, key = sha256(APP_KEY) raw;
                    no prefix (older): AES-256-CBC, key = APP_KEY NUL-padded to 32, iv = sha256hex(APP_KEY)[:16].
                    TOTP seeds and secret settings ("enc1:" prefix).
"""
import base64
import hashlib
import re

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class LegacyDecryptError(ValueError):
    pass


def _php_key(raw: bytes, n: int = 32) -> bytes:
    """PHP's openssl_* NUL-pads a short key and cuts a long one."""
    return raw[:n].ljust(n, b"\0")


def _cbc(key: bytes, iv: bytes, ct: bytes) -> str:
    try:
        d = Cipher(algorithms.AES(key), modes.CBC(iv)).decryptor()
        padded = d.update(ct) + d.finalize()
        u = padding.PKCS7(128).unpadder()
        return (u.update(padded) + u.finalize()).decode("utf-8")
    except Exception as e:  # noqa: BLE001
        raise LegacyDecryptError("could not decrypt") from e


def decrypt_value(stored: str, encryption_key_hex: str) -> str:
    if not stored:
        return ""
    try:
        data = base64.b64decode(stored)
    except Exception as e:  # noqa: BLE001
        raise LegacyDecryptError("not base64") from e
    sep = data.find(b"::")
    if sep != 16:
        raise LegacyDecryptError("not a decrypt_value payload")
    iv, ct = data[:16], base64.b64decode(data[18:])
    return _cbc(_php_key(bytes.fromhex(encryption_key_hex)), iv, ct)


def decrypt_net_secret(stored, encryption_key_hex: str) -> str:
    s = "" if stored is None else str(stored)
    if not s:
        return ""
    if not s.startswith("nenc:"):
        return s  # old rows were plaintext
    return decrypt_value(s[5:], encryption_key_hex)


def decrypt_setting(stored: str, app_key: str) -> str:
    if not stored:
        return ""
    if stored.startswith("v2:"):
        raw = base64.b64decode(stored[3:])
        if len(raw) < 29:
            raise LegacyDecryptError("short v2 payload")
        key = hashlib.sha256(app_key.encode()).digest()
        try:
            return AESGCM(key).decrypt(raw[:12], raw[28:] + raw[12:28], None).decode("utf-8")
        except Exception as e:  # noqa: BLE001
            raise LegacyDecryptError("could not decrypt") from e
    iv = hashlib.sha256(app_key.encode()).hexdigest()[:16].encode("latin1")
    return _cbc(_php_key(app_key.encode()), iv, base64.b64decode(stored))


def decrypt_setting_value(v: str, app_key: str) -> str:
    return decrypt_setting(v[5:], app_key) if v.startswith("enc1:") else v


def parse_old_config(php: str) -> dict[str, str]:
    """Reads define('NAME', 'value') lines from the old config/config.php."""
    out = {}
    for m in re.finditer(r"define\(\s*['\"]([A-Z_]+)['\"]\s*,\s*(['\"])((?:\\.|(?!\2).)*)\2\s*\)", php):
        out[m.group(1)] = re.sub(r"\\(['\"\\])", r"\1", m.group(3))
    return out
