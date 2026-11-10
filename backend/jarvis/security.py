"""Validaciones de seguridad: SSRF, rutas, nombres de archivo y redacción de secretos en logs."""
from __future__ import annotations
import ipaddress
import re
import socket
from pathlib import Path
from urllib.parse import urlsplit


class SecurityError(ValueError):
    pass


def _ip_is_public(ip: str) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    return addr.is_global and not addr.is_multicast


def resolve_host(host: str) -> list[str]:
    infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    return sorted({i[4][0] for i in infos})


def check_public_url(url: str) -> str:
    """Para el importador web: solo http(s) hacia direcciones públicas. Bloquea loopback, redes
    privadas, link-local y metadatos de nube. Devuelve la URL normalizada."""
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https"):
        raise SecurityError("Solo se admiten URLs http o https.")
    if parts.username or parts.password:
        raise SecurityError("La URL no puede incluir credenciales.")
    host = parts.hostname
    if not host:
        raise SecurityError("La URL no tiene un host válido.")
    if host.lower() in ("localhost", "metadata.google.internal") or host.lower().endswith((".local", ".internal", ".localhost")):
        raise SecurityError("Destino interno no permitido.")
    try:
        ips = resolve_host(host)
    except OSError:
        raise SecurityError(f"No se pudo resolver el host {host}.")
    if not ips or not all(_ip_is_public(ip) for ip in ips):
        raise SecurityError("El destino resuelve a una dirección privada o reservada; bloqueado.")
    return parts.geturl()


def check_provider_url(url: str) -> str:
    """Para conexiones configuradas por el usuario (pueden ser locales, p. ej. Ollama)."""
    parts = urlsplit((url or "").strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise SecurityError("La URL del proveedor debe empezar por http:// o https:// e incluir un host.")
    if parts.username or parts.password:
        raise SecurityError("No incluyas credenciales en la URL; usa el campo de credencial.")
    if parts.query or parts.fragment:
        raise SecurityError("La URL base no debe llevar parámetros ni fragmento.")
    return url.strip().rstrip("/")


def is_loopback_url(url: str) -> bool:
    host = urlsplit(url or "").hostname or ""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def safe_join(base: Path, rel: str) -> Path:
    base_r = base.resolve()
    target = (base_r / rel).resolve()
    if target != base_r and base_r not in target.parents:
        raise SecurityError("Ruta fuera del directorio permitido.")
    return target


_NAME_RE = re.compile(r"[^A-Za-z0-9._ \-áéíóúñÁÉÍÓÚÑ()]+")


def sanitize_filename(name: str) -> str:
    name = Path(name.replace("\\", "/")).name
    name = _NAME_RE.sub("_", name).strip(" .")
    return (name or "archivo")[:120]


_SECRET_PATTERNS = [
    re.compile(r"(?i)(authorization|x-goog-api-key|xi-api-key|x-subscription-token|api[-_]?key|token|secret|password)(\"?\s*[:=]\s*\"?)(bearer\s+)?[^\s\"',&]+"),
    re.compile(r"\b(sk|gsk|tvly|xai|AIza)[-_A-Za-z0-9]{16,}\b"),
    re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{12,}"),
]


def redact(text: str) -> str:
    if not text:
        return text
    out = _SECRET_PATTERNS[0].sub(lambda m: f"{m.group(1)}{m.group(2)}[REDACTADO]", str(text))
    out = _SECRET_PATTERNS[1].sub("[REDACTADO]", out)
    out = _SECRET_PATTERNS[2].sub("Bearer [REDACTADO]", out)
    return out
