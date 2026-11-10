"""Acción de escritura en un sistema externo mediante el conector universal. Solo se ejecuta con aprobación específica y de un solo uso."""
from __future__ import annotations

from .. import connections, connectors, db
from ..jobs import ApprovalRequired, JobError
from ..providers.base import ProviderError
from ..util import now_iso
from ..worker import handler


@handler("connector_action")
def connector_action(ctx) -> dict:
    p = ctx.params
    conn = connections.get(p.get("connection_id") or "")
    if not conn or conn["provider"] != "api" or not conn["enabled"] or not conn["terms_accepted"]:
        raise JobError("La conexión no existe o no está habilitada.")
    try:
        digest = connectors.request_hash(conn, p.get("action_id") or "", p.get("variables") or {})
    except ProviderError as exc:
        raise JobError(exc.message)
    key = f"action_approval:{ctx.id}"
    approval = db.get_setting(key)
    if not approval or approval.get("hash") != digest or approval.get("expires_at", "") < now_iso():
        raise ApprovalRequired("Acción externa pendiente de tu aprobación: revisa la petición exacta en Trabajos y apruébala para ejecutarla.")
    db.execute("DELETE FROM settings WHERE key=?", (key,))  # de un solo uso: se consume antes de enviar
    ctx.stage("envio", 0.5, "Ejecutando la acción aprobada")
    try:
        out = connectors.execute(conn, p["action_id"], p.get("variables") or {}, allow_write=True)
    except ProviderError as exc:
        raise JobError(exc.message)
    db.audit("accion_externa", conn["id"], {"accion": p["action_id"], "http": out["status"], "url": out["request"]["url"], "aprobada_por": approval.get("user")}, actor=approval.get("user") or "usuario")
    return {"mensaje": f"Acción ejecutada: HTTP {out['status']}.", "respuesta": out["json"] if out["json"] is not None else (out["text"] or "")[:2000]}
