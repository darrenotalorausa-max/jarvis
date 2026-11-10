"""Avisos al celular del propietario y órdenes remotas por Telegram.

Es una política explícita que configura el usuario en cada conexión (qué eventos avisar y si acepta órdenes).
Los avisos solo llevan título, estado y motivo del trabajo; nunca el contenido de entregables ni datos de espacios personales
(salvo que la conexión esté autorizada para datos personales).
"""
from __future__ import annotations
import logging

from . import connections, db, secrets_store
from .providers import notify as channels
from .providers.base import ProviderError
from .security import redact

log = logging.getLogger("jarvis.notify")
CHANNELS = ("telegram", "whatsapp", "ntfy")
EVENTS = {"completed": "Trabajo completado", "failed": "Trabajo fallido", "waiting": "Trabajo en espera (configuración, cuota o aprobación)"}
DEFAULT_EVENTS = ["completed", "failed", "waiting"]


def _targets(event: str | None, space: dict | None) -> list[dict]:
    out = []
    for c in connections.list_all():
        if c["provider"] not in CHANNELS or not c["enabled"] or not c["terms_accepted"]:
            continue
        if event and event not in ((c["options"] or {}).get("events") or DEFAULT_EVENTS):
            continue
        if space and space["kind"] == "personal" and c["data_policy"] != "todo":
            continue
        out.append(c)
    return out


def send(text: str, *, event: str | None = None, space_id: str | None = None, title: str = "Jarvis OS") -> int:
    """Envía a todos los canales suscritos. Devuelve cuántos lo recibieron. Nunca lanza: un aviso fallido no rompe el trabajo."""
    space = db.one("SELECT * FROM spaces WHERE id=?", (space_id,)) if space_id else None
    sent = 0
    for c in _targets(event, space):
        try:
            channels.send(c, secrets_store.get_secret(connections.secret_name(c["id"])), text, title)
            connections.set_status(c["id"], "operativa", None)
            db.execute("INSERT INTO usage(ts,space_id,connection_id,provider,capability,category,units,state,cost_basis) VALUES(?,?,?,?,?,?,1,'ok','aviso')",
                       (db.now_iso(), space_id, c["id"], c["provider"], "notificacion", "avisos"))
            sent += 1
        except ProviderError as exc:
            connections.record_error(c, exc)
            log.warning("Aviso por %s falló: %s", c["name"], exc.message)
        except Exception as exc:  # un canal roto no debe afectar al trabajo
            log.warning("Aviso por %s falló: %s", c["name"], redact(str(exc)))
    return sent


def job_event(job: dict) -> int:
    status = job["status"]
    event = "completed" if status == "completed" else "failed" if status == "failed" else "waiting" if status.startswith("waiting") else None
    if not event:
        return 0
    from .jobs import STATUS_LABELS
    detail = job.get("error") or job.get("message") or ""
    return send(f"{job['title']}\nEstado: {STATUS_LABELS[status]}\n{detail}"[:900].strip() + f"\n{job['id']}", event=event, space_id=job["space_id"])


def poll_commands() -> int:
    """Lee órdenes enviadas al bot de Telegram desde el chat autorizado y responde con el resultado.
    Solo ejecuta herramientas internas del asistente; mensajes de otros chats se ignoran."""
    from . import assistant
    handled = 0
    for c in connections.list_all():
        o = c["options"] or {}
        if c["provider"] != "telegram" or not c["enabled"] or not c["terms_accepted"] or not o.get("commands") or not o.get("space_id"):
            continue
        space = db.one("SELECT * FROM spaces WHERE id=? AND archived=0", (o["space_id"],))
        if not space or (space["kind"] == "personal" and c["data_policy"] != "todo"):
            continue
        secret = secrets_store.get_secret(connections.secret_name(c["id"]))
        key = f"telegram_offset:{c['id']}"
        try:
            updates = channels.telegram_updates(c, secret, int(db.get_setting(key, 0)))
        except ProviderError as exc:
            connections.record_error(c, exc)
            continue
        for u in updates:
            db.set_setting(key, u["update_id"] + 1)  # se avanza antes de ejecutar: una orden nunca se procesa dos veces
            if u["chat_id"] != str(o.get("chat_id")) or not u["text"].strip():
                continue
            out = assistant.handle(space["id"], u["text"], "texto")
            try:
                channels.send(c, secret, out["reply"][:3000], f"Jarvis · {space['name']}")
            except ProviderError as exc:
                connections.record_error(c, exc)
            db.audit("orden_remota", c["id"], {"herramienta": out.get("tool"), "modo": out.get("mode")}, actor="telegram")
            handled += 1
    return handled
