"""Avisos al celular del propietario y órdenes remotas por Telegram.

Es una política explícita que configura el usuario en cada conexión (qué eventos avisar y si acepta órdenes).
Los avisos solo llevan título, estado y motivo del trabajo; nunca el contenido de entregables ni datos de espacios personales
(salvo que la conexión esté autorizada para datos personales).

Aprobar desde el celular es otra política explícita, por canal y desactivada por defecto («approvals»): con ella, Telegram recibe
el resumen del entregable o la petición exacta de una acción externa junto a los botones Aprobar y Rechazar. Solo cuenta la
respuesta del chat autorizado, cada solicitud sirve una vez, caduca, y queda ligada a la versión o a la petición exacta.
"""
from __future__ import annotations
import logging
import re
import secrets

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


APPROVAL_HOURS = 24
_APPROVAL_CMD = re.compile(r"^(ap|re|aprobar|aprueba|rechazar|rechaza)[:\s]+([a-z0-9]{6,12})$", re.I)


def _approval_channels(space: dict) -> list[dict]:
    return [c for c in connections.list_all() if c["provider"] == "telegram" and c["enabled"] and c["terms_accepted"] and (c["options"] or {}).get("approvals")
            and not (space["kind"] == "personal" and c["data_policy"] != "todo")]


def request_approval(space_id: str, payload: dict, text: str, title: str) -> int:
    """Envía una solicitud con botones a los Telegram que tienen activadas las aprobaciones. payload: {kind: action|deliverable, …}."""
    space = db.one("SELECT * FROM spaces WHERE id=?", (space_id,))
    if not space:
        return 0
    from .util import iso_in
    sent = 0
    for c in _approval_channels(space):
        code = secrets.token_hex(4)
        db.set_setting(f"tg_approval:{code}", {**payload, "space_id": space_id, "connection_id": c["id"], "expires_at": iso_in(APPROVAL_HOURS * 3600)})
        try:
            channels.send(c, secrets_store.get_secret(connections.secret_name(c["id"])), f"{text[:3000]}\n\nTambién puedes responder: aprobar {code} · rechazar {code}",
                          title, buttons=[("Aprobar", f"ap:{code}"), ("Rechazar", f"re:{code}")])
            sent += 1
        except ProviderError as exc:
            db.execute("DELETE FROM settings WHERE key=?", (f"tg_approval:{code}",))
            connections.record_error(c, exc)
    return sent


def deliverable_approval(deliverable_id: str, space_id: str) -> int:
    from . import review
    d = review.detail(deliverable_id, space_id)
    if not d or d["status"] in ("aprobado", "rechazado"):
        return 0
    v = d["version"]
    fails = [c for c in ((v.get("checks") or {}).get("automaticas") or []) if c.get("result") in ("fail", "warn")]
    summary = str((v.get("content") or {}).get("summary") or "")[:700]
    text = (f"{d['title']}\n{d['kind_label']} · versión {d['current_version']}\n" + (f"\n{summary}\n" if summary else "")
            + (f"\nComprobaciones con avisos: {len(fails)}\n" + "\n".join(f"• {c.get('label')}" for c in fails[:5]) if fails else "\nComprobaciones automáticas sin avisos."))
    return request_approval(space_id, {"kind": "deliverable", "deliverable_id": deliverable_id, "version": d["current_version"]}, text, "Jarvis · ¿apruebas este entregable?")


def action_approval(job: dict) -> int:
    from . import connectors
    conn = connections.get(job["params"].get("connection_id") or "")
    if not conn:
        return 0
    try:
        action = connectors.action_of(conn, job["params"]["action_id"])
        req = connectors.build(conn, action, job["params"].get("variables") or {})
        digest = connectors.request_hash(conn, job["params"]["action_id"], job["params"].get("variables") or {})
    except (ProviderError, KeyError, ValueError):
        return 0
    import json
    body = json.dumps(req.get("body"), ensure_ascii=False, indent=1)[:900] if req.get("body") else ""
    text = f"{job['title']}\n{req['method']} {req['url']}" + (f"\n{body}" if body else "") + "\n\nSe enviará exactamente esta petición, una sola vez."
    return request_approval(job["space_id"], {"kind": "action", "job_id": job["id"], "hash": digest}, text, "Jarvis · ¿apruebas esta acción externa?")


def resolve_approval(conn: dict, verb: str, code: str) -> str:
    """Aplica la decisión tomada en Telegram. Devuelve el texto de respuesta."""
    from . import jobs, review
    from .util import iso_in, now_iso
    key = f"tg_approval:{code.lower()}"
    req = db.get_setting(key)
    if not req or req.get("connection_id") != conn["id"]:
        return "Esa solicitud no existe o ya se resolvió."
    db.execute("DELETE FROM settings WHERE key=?", (key,))  # de un solo uso
    if req.get("expires_at", "") < now_iso():
        return "Esa solicitud caducó. Resuélvela desde el panel."
    approve = verb.lower() in ("ap", "aprobar", "aprueba")
    actor = f"propietario (Telegram · {conn['name']})"
    try:
        if req["kind"] == "action":
            from . import connectors
            job = jobs.get(req["job_id"])
            if not job or job["status"] != "waiting_approval":
                return "Esa acción ya no está esperando aprobación."
            if not approve:
                jobs.cancel(job["id"])
                db.audit("accion_externa.rechazar", job["id"], {}, actor=actor)
                return f"Rechazada: {job['title']}. No se envió nada."
            target = connections.get(job["params"]["connection_id"])
            if not target or connectors.request_hash(target, job["params"]["action_id"], job["params"].get("variables") or {}) != req["hash"]:
                return "La petición cambió desde que se te envió. No se aprobó: revísala en el panel."
            db.set_setting(f"action_approval:{job['id']}", {"hash": req["hash"], "user": actor, "expires_at": iso_in(3600)})
            db.audit("accion_externa.aprobar", job["id"], {"conexion": target["id"], "accion": job["params"]["action_id"]}, actor=actor)
            jobs.retry(job["id"])
            return f"Aprobada: {job['title']}. Se ejecuta ahora, una sola vez."
        d = review.get(req["deliverable_id"], req["space_id"])
        if not d:
            return "Ese entregable ya no existe."
        if d["current_version"] != req["version"]:
            return f"«{d['title']}» tiene una versión más nueva que la que se te envió. Revísala en el panel."
        if approve:
            review.approve(d["id"], req["space_id"], version=req["version"], user=actor)
            return f"Aprobado: {d['title']} (versión {req['version']})."
        review.reject(d["id"], req["space_id"], "Rechazado desde Telegram", actor)
        return f"Rechazado: {d['title']}."
    except Exception as exc:
        log.warning("No se pudo aplicar la decisión de Telegram: %s", redact(str(exc)))
        return f"No se pudo aplicar la decisión: {redact(str(exc))[:200]}"


def job_event(job: dict) -> int:
    status = job["status"]
    event = "completed" if status == "completed" else "failed" if status == "failed" else "waiting" if status.startswith("waiting") else None
    if not event:
        return 0
    from .jobs import STATUS_LABELS
    detail = job.get("error") or job.get("message") or ""
    sent = send(f"{job['title']}\nEstado: {STATUS_LABELS[status]}\n{detail}"[:900].strip() + f"\n{job['id']}", event=event, space_id=job["space_id"])
    try:
        if status == "waiting_approval" and job["type"] == "connector_action":
            sent += action_approval(job)
        elif status == "completed":
            for did in ((job.get("result") or {}).get("deliverable_ids") or [])[:3]:
                sent += deliverable_approval(did, job["space_id"])
    except Exception as exc:  # una solicitud fallida no rompe el aviso
        log.warning("No se pudo enviar la solicitud de aprobación: %s", redact(str(exc)))
    return sent


def poll_commands() -> int:
    """Lee órdenes enviadas al bot de Telegram desde el chat autorizado y responde con el resultado.
    Solo ejecuta herramientas internas del asistente; mensajes de otros chats se ignoran."""
    from . import assistant
    handled = 0
    for c in connections.list_all():
        o = c["options"] or {}
        if c["provider"] != "telegram" or not c["enabled"] or not c["terms_accepted"] or not (o.get("commands") or o.get("approvals")):
            continue
        space = db.one("SELECT * FROM spaces WHERE id=? AND archived=0", (o.get("space_id") or "",)) if o.get("commands") else None
        if space and space["kind"] == "personal" and c["data_policy"] != "todo":
            space = None
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
            decision = _APPROVAL_CMD.match(u["text"].strip())
            if decision or u.get("callback_id"):
                reply = resolve_approval(c, decision.group(1), decision.group(2)) if decision and o.get("approvals") else "Las aprobaciones desde Telegram no están activadas en esta conexión."
                try:
                    if u.get("callback_id"):
                        channels.telegram_ack(c, secret, u["callback_id"], reply)
                    channels.send(c, secret, reply, "Jarvis")
                except ProviderError as exc:
                    connections.record_error(c, exc)
                handled += 1
                continue
            if not space:
                continue
            out = assistant.handle(space["id"], u["text"], "texto")
            try:
                channels.send(c, secret, out["reply"][:3000], f"Jarvis · {space['name']}")
            except ProviderError as exc:
                connections.record_error(c, exc)
            db.audit("orden_remota", c["id"], {"herramienta": out.get("tool"), "modo": out.get("mode")}, actor="telegram")
            handled += 1
    return handled
