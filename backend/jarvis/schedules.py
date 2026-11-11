"""Agentes con horario: órdenes para Jarvis que se lanzan solas a una hora o cada cierto tiempo.

Cada horario ejecuta una orden del asistente (las mismas que escribes en Comando), así que solo puede lanzar herramientas
internas. Respeta la pausa global, las políticas del espacio, los presupuestos y un tope diario de ejecuciones.
"""
from __future__ import annotations
from datetime import datetime, timedelta

from . import db, notify, records
from .util import now, now_iso

WEEKDAYS = ["lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo"]
MAX_RUNS_PER_DAY = 24


def _local(iso: str | None) -> datetime | None:
    try:
        return datetime.fromisoformat(iso).astimezone() if iso else None
    except ValueError:
        return None


def is_due(data: dict, at: datetime | None = None) -> bool:
    at = (at or now()).astimezone()
    last = _local(data.get("last_run"))
    freq = data.get("frequency") or "diario"
    if freq == "intervalo":
        hours = max(1.0, float(data.get("every_hours") or 6))
        return not last or at - last >= timedelta(hours=hours)
    hour = max(0, min(23, int(data.get("hour") or 9)))
    if at.hour < hour or (last and last.date() == at.date()):
        return False
    if freq == "semanal":
        return WEEKDAYS[at.weekday()] == (data.get("weekday") or "lunes")
    return True


def run(rec: dict, *, manual: bool = False) -> dict:
    from . import assistant
    d, space_id = rec["data"], rec["space_id"]
    order = (d.get("order") or "").strip()
    day = now().astimezone().date().isoformat()
    runs = d.get("runs") if isinstance(d.get("runs"), dict) and d["runs"].get("day") == day else {"day": day, "n": 0}
    if not manual and runs["n"] >= MAX_RUNS_PER_DAY:
        return {"horario": rec["title"], "ejecutado": False, "motivo": "tope diario alcanzado"}
    if not order:
        out = {"reply": "El horario no tiene ninguna orden.", "error": True}
    else:
        try:
            out = assistant.handle(space_id, order, "horario")
        except Exception as exc:  # un horario roto no detiene a los demás
            out = {"reply": f"La orden no pudo ejecutarse: {type(exc).__name__}", "error": True}
    reply = (out.get("reply") or "")[:300]
    records.update(rec["id"], space_id, {"data": {"last_run": now_iso(), "last_result": reply, "runs": {"day": day, "n": runs["n"] + 1}}})
    db.audit("horario.ejecutar", rec["id"], {"herramienta": out.get("tool"), "manual": manual, "error": bool(out.get("error"))}, actor="horario")
    sent = 0
    if d.get("notify", True) and not manual:
        sent = notify.send(reply, space_id=space_id, title=f"Jarvis · {rec['title']}")
    return {"horario": rec["title"], "ejecutado": True, "respuesta": reply, "herramienta": out.get("tool"), "trabajo": (out.get("job") or {}).get("id"), "avisos": sent, "error": bool(out.get("error"))}


def run_due() -> list[dict]:
    if db.get_setting("agents_paused", False):
        return []
    out = []
    for sp in db.query("SELECT id FROM spaces WHERE archived=0"):
        for rec in records.list_records(sp["id"], "schedule", status="activo"):
            if is_due(rec["data"]):
                out.append(run(rec))
    return out
