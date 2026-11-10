"""Acceso desde otros dispositivos de tu red (p. ej. el celular). Desactivado por defecto.

Se activa solo si defines JARVIS_HOST distinto de loopback Y un JARVIS_ACCESS_CODE de 10 caracteres o más.
El tráfico va por HTTP sin cifrar: úsalo solo en una red de confianza (tu casa), nunca en redes públicas.
"""
from __future__ import annotations
import hashlib
import hmac
import ipaddress
import os
import socket
import time

from . import config
from .security import SecurityError

COOKIE = "jarvis_sesion"
MIN_CODE = 10
_failures: dict[str, list[float]] = {}


def code() -> str:
    return os.environ.get("JARVIS_ACCESS_CODE", "")


def exposed() -> bool:
    return config.host() not in ("127.0.0.1", "localhost", "::1")


def enabled() -> bool:
    return exposed() and len(code()) >= MIN_CODE


def is_loopback(host: str) -> bool:
    if host in ("testclient", "localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _token() -> str:
    return hmac.new(code().encode(), b"jarvis-os-sesion-v1", hashlib.sha256).hexdigest()


def valid_cookie(value: str | None) -> bool:
    return bool(value) and enabled() and hmac.compare_digest(value, _token())


def login(client: str, attempt: str) -> str:
    """Valida el código con límite de intentos por dispositivo. Devuelve el valor de la cookie de sesión."""
    if not enabled():
        raise SecurityError("El acceso desde otros dispositivos no está activado.")
    now = time.time()
    recent = [t for t in _failures.get(client, []) if now - t < 600]
    if len(recent) >= 5:
        raise SecurityError("Demasiados intentos fallidos. Espera 10 minutos.")
    if not hmac.compare_digest(attempt.encode(), code().encode()):
        _failures[client] = recent + [now]
        raise SecurityError("Código de acceso incorrecto.")
    _failures.pop(client, None)
    return _token()


def lan_urls() -> list[str]:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))  # no envía nada: solo averigua la interfaz de salida
            return [f"http://{s.getsockname()[0]}:{config.port()}/"]
    except OSError:
        return []
