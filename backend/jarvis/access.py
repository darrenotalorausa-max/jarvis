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


def via_proxy(headers) -> bool:
    """Con el acceso en red activo, una petición que llega por loopback pero reenviada por un proxy inverso
    (o con JARVIS_REQUIRE_LOGIN=1, como en Docker) no es «este equipo»: debe iniciar sesión como cualquier otra."""
    if not exposed():
        return False
    return os.environ.get("JARVIS_REQUIRE_LOGIN") == "1" or any(headers.get(h) for h in ("x-forwarded-for", "forwarded", "x-real-ip"))


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


# ---------- Usuarios con rol (para quien entra desde otro dispositivo). El propietario entra con el código de acceso.

ROLES = {"equipo": "Equipo: trabaja en los espacios asignados; no ve conexiones, ajustes, respaldos ni aprueba envíos",
         "cliente": "Cliente: solo ve y comenta los entregables de sus espacios"}
_SESSION_DAYS = 14


def _hash(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 240_000).hex()


def list_users() -> list[dict]:
    import json
    from . import db
    rows = db.query("SELECT id, username, role, spaces, active, created_at, last_login FROM users ORDER BY created_at")
    for r in rows:
        r["spaces"], r["active"] = json.loads(r["spaces"] or "[]"), bool(r["active"])
    return rows


def save_user(data: dict, user_id: str | None = None) -> dict:
    import json
    import secrets as pysecrets
    from . import db
    from .util import new_id, now_iso
    username = str(data.get("username") or "").strip().lower()
    role, spaces, password = data.get("role"), list(data.get("spaces") or []), str(data.get("password") or "")
    if role not in ROLES or not username.replace("_", "").replace(".", "").isalnum() or len(username) < 3:
        raise SecurityError("Indica un nombre de usuario (3+ letras o números) y un rol válido.")
    known = {s["id"]: s for s in db.query("SELECT id, kind FROM spaces")}
    if not spaces or any(sid not in known or known[sid]["kind"] == "personal" for sid in spaces):
        raise SecurityError("Asigna al menos un espacio de negocio. Los espacios personales no se comparten.")
    if (not user_id or password) and len(password) < 10:
        raise SecurityError("La contraseña debe tener 10 caracteres o más.")
    if user_id:
        db.execute("UPDATE users SET username=?, role=?, spaces=?, active=? WHERE id=?", (username, role, json.dumps(spaces), int(bool(data.get("active", True))), user_id))
        if password:
            salt = pysecrets.token_hex(16)
            db.execute("UPDATE users SET pass_hash=?, salt=? WHERE id=?", (_hash(password, salt), salt, user_id))
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
        if not data.get("active", True):
            db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    else:
        if db.one("SELECT id FROM users WHERE username=?", (username,)):
            raise SecurityError("Ya existe un usuario con ese nombre.")
        salt = pysecrets.token_hex(16)
        user_id = new_id("usr")
        db.execute("INSERT INTO users(id,username,role,pass_hash,salt,spaces,active,created_at) VALUES(?,?,?,?,?,?,1,?)", (user_id, username, role, _hash(password, salt), salt, json.dumps(spaces), now_iso()))
    db.audit("usuario.guardar", user_id, {"rol": role, "espacios": spaces})
    return next(u for u in list_users() if u["id"] == user_id)


def delete_user(user_id: str) -> None:
    from . import db
    db.execute("DELETE FROM sessions WHERE user_id=?", (user_id,))
    db.execute("DELETE FROM users WHERE id=?", (user_id,))
    db.audit("usuario.eliminar", user_id, {})


def login_user(client: str, username: str, password: str) -> str:
    import secrets as pysecrets
    from . import db
    from .util import iso_in, now_iso
    if not enabled():
        raise SecurityError("El acceso desde otros dispositivos no está activado.")
    now = time.time()
    recent = [t for t in _failures.get(client, []) if now - t < 600]
    if len(recent) >= 5:
        raise SecurityError("Demasiados intentos fallidos. Espera 10 minutos.")
    u = db.one("SELECT * FROM users WHERE username=? AND active=1", (username.strip().lower(),))
    if not u or not hmac.compare_digest(_hash(password, u["salt"]), u["pass_hash"]):
        _failures[client] = recent + [now]
        raise SecurityError("Usuario o contraseña incorrectos.")
    token = pysecrets.token_urlsafe(32)
    db.execute("INSERT INTO sessions(token_hash,user_id,expires_at,created_at) VALUES(?,?,?,?)", (hashlib.sha256(token.encode()).hexdigest(), u["id"], iso_in(_SESSION_DAYS * 86400), now_iso()))
    db.execute("UPDATE users SET last_login=? WHERE id=?", (now_iso(), u["id"]))
    return "u." + token


def session_user(cookie: str | None) -> dict | None:
    """Devuelve {'role': 'propietario'} para el código de acceso, o el usuario de la sesión, o None."""
    import json
    from . import db
    from .util import now_iso
    if not cookie or not enabled():
        return None
    if valid_cookie(cookie):
        return {"id": "propietario", "username": "propietario", "role": "propietario", "spaces": None}
    if not cookie.startswith("u."):
        return None
    row = db.one("SELECT u.id, u.username, u.role, u.spaces FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.active=1",
                 (hashlib.sha256(cookie[2:].encode()).hexdigest(), now_iso()))
    if row:
        row["spaces"] = json.loads(row["spaces"] or "[]")
    return row


# Lista blanca por rol: (método, expresión de ruta). Todo lo que no figure aquí se deniega.
import re as _re
_TEAM = [("GET", r"/api/(bootstrap|overview|availability|library(/doc|/search|/file)?|business/summary|clipping/summary|economy/summary|assistant/(history|tools))"),
         ("GET", r"/api/(records(/export\.csv|/[\w]+)?|deliverables(/[\w]+(/diff)?)?|files(/[\w]+/(download|preview))?|jobs|video/preview|video/[\w]+/(subtitles|manifest))"),
         ("POST", r"/api/(records(/import)?|deliverables(/[\w]+/(versions|status|comments|export|convert))?|jobs|assistant|video/[\w]+/subtitles)"),
         ("PATCH", r"/api/records/[\w]+")]
_CLIENT = [("GET", r"/api/(bootstrap|deliverables(/[\w]+(/diff)?)?|files/[\w]+/(download|preview))"), ("POST", r"/api/deliverables/[\w]+/comments")]
_TEAM_JOBS = ("opportunity_research", "lead_search", "lead_proposal", "content_batch", "video_transcribe", "video_suggest", "video_render", "shopify_package", "clipping_import_url")


def allowed(user: dict, method: str, path: str) -> bool:
    if user["role"] == "propietario":
        return True
    rules = _TEAM if user["role"] == "equipo" else _CLIENT
    return any(method == m and _re.fullmatch(rx, path) for m, rx in rules)


def body_ok(user: dict, path: str, body: dict) -> bool:
    """Comprobaciones adicionales sobre el cuerpo para roles limitados."""
    if path == "/api/jobs" and body.get("type") not in _TEAM_JOBS:
        return False
    return True


# ---------- Token para programas externos (n8n, atajos, scripts): solo permite enviar órdenes a Jarvis

def new_api_token() -> str:
    import secrets as pysecrets
    from . import db
    token = "jrv_" + pysecrets.token_urlsafe(32)
    db.set_setting("api_token_hash", hashlib.sha256(token.encode()).hexdigest())
    db.audit("token_api.crear", "", {})
    return token


def valid_api_token(header: str | None) -> bool:
    from . import db
    saved = db.get_setting("api_token_hash")
    if not saved or not header or not header.lower().startswith("bearer "):
        return False
    return hmac.compare_digest(hashlib.sha256(header[7:].strip().encode()).hexdigest(), saved)
