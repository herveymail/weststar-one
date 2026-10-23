"""The Python ports must read exactly what the old PHP functions wrote. These helpers re-create the
PHP encryption with the same parameters (see tests/fixtures/legacy-seed.php for the PHP originals)."""
import base64
import hashlib
import os

from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from apps.legacy.crypto import decrypt_net_secret, decrypt_setting, decrypt_value, parse_old_config

ENC = os.urandom(32).hex()
APP = "old-app-key-from-config-php"


def _cbc(key, iv, text):
    p = padding.PKCS7(128).padder()
    data = p.update(text.encode()) + p.finalize()
    e = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return e.update(data) + e.finalize()


def php_encrypt_value(text, iv=None):
    iv = iv or os.urandom(16)
    ct = base64.b64encode(_cbc(bytes.fromhex(ENC), iv, text))
    return base64.b64encode(iv + b"::" + ct).decode()


def php_encrypt_setting_v2(text):
    iv = os.urandom(12)
    sealed = AESGCM(hashlib.sha256(APP.encode()).digest()).encrypt(iv, text.encode(), None)
    return "v2:" + base64.b64encode(iv + sealed[-16:] + sealed[:-16]).decode()


def php_legacy_setting(text):
    iv = hashlib.sha256(APP.encode()).hexdigest()[:16].encode()
    return base64.b64encode(_cbc(APP.encode()[:32].ljust(32, b"\0"), iv, text)).decode()


def test_decrypt_value_and_network_prefix():
    assert decrypt_value(php_encrypt_value("123-45-6789"), ENC) == "123-45-6789"
    assert decrypt_net_secret("nenc:" + php_encrypt_value("Wifi-Pass!"), ENC) == "Wifi-Pass!"
    assert decrypt_net_secret("plain-old-value", ENC) == "plain-old-value"


def test_iv_containing_separator_still_works():
    iv = b"ab::cdefghijklmn"
    assert decrypt_value(php_encrypt_value("x", iv=iv), ENC) == "x"


def test_decrypt_settings_both_formats():
    assert decrypt_setting(php_encrypt_setting_v2("JBSWY3DPEHPK3PXP"), APP) == "JBSWY3DPEHPK3PXP"
    assert decrypt_setting(php_legacy_setting("KRSXG5CTMVRXEZLU"), APP) == "KRSXG5CTMVRXEZLU"


def test_wrong_key_raises():
    import pytest

    from apps.legacy.crypto import LegacyDecryptError
    with pytest.raises(LegacyDecryptError):
        decrypt_setting(php_encrypt_setting_v2("x"), "other-key")


def test_parse_old_config():
    php = """<?php define('DB_HOST', 'localhost'); define("DB_PASS", 'p\\'ss'); define('APP_KEY','abc');"""
    c = parse_old_config(php)
    assert c == {"DB_HOST": "localhost", "DB_PASS": "p'ss", "APP_KEY": "abc"}
