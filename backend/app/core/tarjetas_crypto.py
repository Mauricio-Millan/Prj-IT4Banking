"""Custodia del PAN de una tarjeta: AES-256-GCM en reposo + HMAC-SHA256 como huella
para poder garantizar UNIQUE sin descifrar. Ver Docs/Proyecto/HU-Tarjeta-Datos-Cifrados-Revelar.md.

Dos claves distintas (cifrado, hmac): comprometer una no compromete la otra. AAD = cuenta_id
impide trasplantar el blob cifrado de una fila a otra. Byte de version al inicio del blob
para poder rotar la clave despues sin migrar el esquema.
"""
import base64
import hashlib
import hmac
import secrets

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.core.config import settings

_VERSION = b"\x01"
_LARGO_NONCE = 12


def _clave_cifrado() -> bytes:
    return base64.b64decode(settings.tarjeta_clave_cifrado)


def _clave_hmac() -> bytes:
    return base64.b64decode(settings.tarjeta_clave_hmac)


def cifrar_pan(pan: str, cuenta_id: int) -> bytes:
    nonce = secrets.token_bytes(_LARGO_NONCE)
    ciphertext = AESGCM(_clave_cifrado()).encrypt(nonce, pan.encode(), str(cuenta_id).encode())
    return _VERSION + nonce + ciphertext


def descifrar_pan(blob: bytes, cuenta_id: int) -> str:
    version, nonce, ciphertext = blob[:1], blob[1:1 + _LARGO_NONCE], blob[1 + _LARGO_NONCE:]
    if version != _VERSION:
        raise ValueError(f"Version de cifrado de tarjeta no soportada: {version!r}")
    return AESGCM(_clave_cifrado()).decrypt(nonce, ciphertext, str(cuenta_id).encode()).decode()


def huella_pan(pan: str) -> bytes:
    """HMAC, no SHA-256 a secas: con el BIN conocido el PAN solo tiene 10**7 posibilidades
    y un hash simple se invierte por fuerza bruta en segundos."""
    return hmac.new(_clave_hmac(), pan.encode(), hashlib.sha256).digest()
