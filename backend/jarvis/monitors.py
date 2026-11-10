"""Monitores proactivos deterministas: revisan datos reales cada cierto tiempo, registran alertas y avisan al celular.
Sin modelos ni bucles: cada monitor tiene frecuencia, no repite un mismo hallazgo y hay un tope diario de avisos."""
from __future__ import annotations
from datetime import date, timedelta

from . import db, jobs, life, notify, records, review, webfetch
from .handlers import clipping
from .util import now, now_iso, sha256_text

TYPES = {
    "tareas_vencidas": "Tareas vencidas", "vencimientos": "Vencimientos de documentos, salud e inversiones", "suscripciones": "Renovaciones y suscripciones sin uso",
    "presupuesto": "Presupuesto excedido", "clipping": "Alertas de clipping", "trabajos_fallidos": "Trabajos fallidos o en espera", "por_aprobar": "Entregables por aprobar",
    "sitio_web": "Sitio web caído o con error", "resumen_diario": "Resumen diario",
}
MAX_NOTIFICATIONS_PER_DAY = 12


def _findings(space_id: str, kind: str, cfg: dict) -> list[str]:
    today = date.today().isoformat()
    if kind == "tareas_vencidas":
        return [f"Tarea vencida: {t['title']} ({t['data']['due_date']})" for t in records.list_records(space_id, "task") if t["status"] != "hecha" and (t["data"].get("due_date") or "9999") < today]
    if kind == "vencimientos":
        return [f"{v['tipo']}: {v['titulo']} — {'vencido' if v['dias'] < 0 else f'en {v['dias']} día(s)'} ({v['fecha']})" for v in life.summary(space_id)["vencimientos"] if v["dias"] <= int(cfg.get("days") or 7)]
    if kind == "suscripciones":
        return [a["texto"] for a in life.summary(space_id)["economia"]["alertas"]]
    if kind == "presupuesto":
        return [f"Presupuesto «{b['categoria']}» excedido: {b['gastado']} de {b['limite']}" for b in life.summary(space_id)["economia"]["presupuesto"] if b["excedido"]]
    if kind == "clipping":
        return [f"{a['campana']}: {a['texto']}" for a in clipping.summary(space_id)["alertas"]]
    if kind == "trabajos_fallidos":
        cut = (now() - timedelta(hours=24)).isoformat(timespec="seconds")
        return [f"{j['title']}: {j['status_label']} — {(j['error'] or j['message'] or '')[:140]}" for j in jobs.list_jobs(space_id, limit=100)
                if (j["status"] == "failed" and (j["finished_at"] or "") > cut) or j["status"].startswith("waiting")]
    if kind == "por_aprobar":
        return [f"Por aprobar: {d['title']}" for d in review.list_deliverables(space_id, status="en_revision")]
    if kind == "sitio_web":
        url = (cfg.get("url") or "").strip()
        if not url:
            return ["Monitor de sitio web sin URL configurada."]
        page = webfetch.fetch_page(url, respect_robots=False)
        return [] if page["status"] == "ok" else [f"{url}: {page.get('note') or page['status']}"]
    if kind == "resumen_diario":
        from . import assistant
        s = assistant.pending_summary(space_id)
        return [f"Resumen {today}: {s['por_aprobar']} por aprobar, {s['tareas_abiertas']} tareas abiertas ({s['tareas_vencidas']} vencidas), {s['trabajos_activos']} trabajos activos."]
    return []


def run_monitor(mon: dict, *, force: bool = False) -> dict:
    d, space_id = mon["data"], mon["space_id"]
    kind = d.get("type")
    try:
        found = _findings(space_id, kind, d)
    except Exception as exc:  # un monitor roto no detiene a los demás
        found = [f"El monitor no pudo ejecutarse: {type(exc).__name__}"]
    seen = set(d.get("seen") or [])
    fresh = [f for f in found if force or sha256_text(f)[:16] not in seen]
    created = 0
    for text in fresh[:20]:
        records.create(space_id, "alert", text[:290], {"monitor_id": mon["id"], "type": kind, "detected": now_iso()})
        created += 1
    sent = 0
    if fresh and d.get("notify", True):
        day = now_iso()[:10]
        count = db.get_setting(f"monitor_notified:{day}", 0)
        if count < MAX_NOTIFICATIONS_PER_DAY:
            sent = notify.send("\n".join(f"• {f}" for f in fresh[:8]) + (f"\n… y {len(fresh) - 8} más" if len(fresh) > 8 else ""), space_id=space_id, title=f"Jarvis · {mon['title']}")
            db.set_setting(f"monitor_notified:{day}", count + 1)
    # Se recuerdan solo los hallazgos vigentes: si algo se resuelve y reaparece, vuelve a avisar.
    records.update(mon["id"], space_id, {"data": {"last_run": now_iso(), "last_result": f"{len(found)} hallazgo(s), {created} nuevo(s)", "seen": [sha256_text(f)[:16] for f in found][:300]}})
    return {"monitor": mon["title"], "hallazgos": len(found), "nuevos": created, "avisos": sent}


def run_due() -> list[dict]:
    if db.get_setting("agents_paused", False):
        return []
    out = []
    for sp in db.query("SELECT id FROM spaces WHERE archived=0"):
        for mon in records.list_records(sp["id"], "monitor", status="activo"):
            d = mon["data"]
            hours = max(1.0, float(d.get("every_hours") or 24))
            if d.get("last_run") and d["last_run"] > (now() - timedelta(hours=hours)).isoformat(timespec="seconds"):
                continue
            if d.get("type") == "resumen_diario" and now().astimezone().hour < int(d.get("hour") or 8):
                continue
            out.append(run_monitor(mon))
    return out
