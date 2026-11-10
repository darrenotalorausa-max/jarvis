"""Envío externo de un entregable a un webhook configurado (p. ej. CRM). Requiere aprobación específica y vigente."""
from __future__ import annotations

from .. import connections, db, review
from ..jobs import ApprovalRequired, JobError
from ..providers import base
from ..util import now_iso
from ..worker import handler


@handler("external_export")
def external_export(ctx) -> dict:
    p = ctx.params
    d = review.detail(p.get("deliverable_id") or "", ctx.space_id)
    conn = connections.get(p.get("connection_id") or "")
    if not d:
        raise JobError("El entregable no existe en este espacio.")
    if not conn or conn["provider"] != "webhook" or not conn["enabled"] or not conn["terms_accepted"]:
        raise JobError("El destino no es un webhook habilitado. Revísalo en Conexiones.")
    destination = conn["base_url"]
    approval = review.find_valid_approval(d["id"], "envio_externo", destination)
    if not approval:
        raise ApprovalRequired(f"Falta una aprobación vigente de envío externo para la versión {d['current_version']} hacia {destination}. "
                               "Apruébala en Revisión y reanuda el trabajo.")
    if approval["used_at"]:
        raise ApprovalRequired("La aprobación ya se utilizó para un envío. Aprueba de nuevo si quieres reenviar.")
    v = d["version"]
    ctx.stage("envio", 0.5, f"Enviando versión {v['version']} a {destination}")
    payload = {"origen": "jarvis-os", "entregable": {"id": d["id"], "tipo": d["kind"], "titulo": d["title"], "version": v["version"], "hash": v["content_hash"]},
               "contenido": v["content"], "markdown": review.render_markdown(d, v, d["sources"]), "aprobacion": {"id": approval["id"], "usuario": approval["user"], "alcance": approval["scope"]}}
    with base.client(conn.get("timeout_s") or 30) as cli:
        try:
            resp = base.send(cli, "POST", destination, "Envío externo", json=payload)
        except base.ProviderError as exc:
            raise JobError(exc.message, retryable=exc.kind == "network")
    db.execute("UPDATE approvals SET used_at=? WHERE id=?", (now_iso(), approval["id"]))
    db.audit("envio_externo", d["id"], {"destino": destination, "version": v["version"], "aprobacion": approval["id"], "http": resp.status_code}, actor=approval["user"])
    return {"mensaje": f"Versión {v['version']} enviada a {destination} (HTTP {resp.status_code}).", "deliverable_ids": [d["id"]]}
