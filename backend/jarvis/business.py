"""Centro de negocios: consolidación por negocio a partir de datos reales del espacio. «Sin datos» nunca se muestra como 0."""
from __future__ import annotations
from collections import Counter

from . import db, economy, jobs, records, review
from .handlers import clipping

BUSINESSES = {"ecom": "E-commerce", "b2b": "Servicios B2B", "clip": "Clipping", "brands": "Marcas personales"}
SECTIONS = {"A_base_estable": "A · Base estable", "B_por_lanzamiento": "B · Por lanzamiento", "C_ciclo_diario": "C · Ciclo diario",
            "D_revisiones": "D · Revisiones", "E_etapas_de_crecimiento": "E · Etapas de crecimiento", "F_automatizaciones": "F · Automatizaciones"}
PROJECT_TYPE = {"ecom": ("ecommerce", "infoproducto"), "b2b": ("servicio_b2b",), "clip": ("clipping",), "brands": ("marca_personal",)}
OPEN = ("pendiente", "preparada", "en_cola", "ejecutando", "esperando_integracion", "esperando_datos", "esperando_aprobacion", "verificacion")


def summary(space_id: str) -> dict:
    missions = records.list_records(space_id, "mission", limit=100000)
    projects = records.list_records(space_id, "project")
    eco = economy.summary(space_id)
    out = []
    for key, label in BUSINESSES.items():
        mine = [m for m in missions if m["data"].get("business") == key]
        by_status = Counter(m["status"] for m in mine)
        applicable = [m for m in mine if m["status"] not in ("no_aplica", "cancelada")]
        verified = by_status.get("completada_verificada", 0)
        pids = {p["id"] for p in projects if p["data"].get("type") in PROJECT_TYPE[key]}
        money = [r for r in eco["por_proyecto"] if r["proyecto_id"] in pids]
        out.append({
            "id": key, "nombre": label, "misiones": len(mine), "abiertas": sum(by_status.get(s, 0) for s in OPEN), "verificadas": verified,
            "avance": round(verified / len(applicable), 3) if applicable else None,  # None = sin misiones: no es un 0 %
            "bloqueadas": by_status.get("esperando_integracion", 0) + by_status.get("esperando_datos", 0),
            "por_aprobar": by_status.get("esperando_aprobacion", 0), "fallidas": by_status.get("fallida", 0),
            "por_seccion": {sec: {"total": sum(1 for m in mine if m["data"].get("section") == sec),
                                  "verificadas": sum(1 for m in mine if m["data"].get("section") == sec and m["status"] == "completada_verificada")} for sec in SECTIONS},
            "proyectos": len(pids),
            "economia": [{"moneda": r["moneda"], "cobrado": r["ingreso_cobrado"], "facturado": r["ingreso_facturado"], "acordado": r["ingreso_acordado"],
                          "gastos_pagados": r["gasto_pagado"], "contribucion": r["contribucion"]} for r in money] or None,
        })
    clip = clipping.summary(space_id)
    active = jobs.list_jobs(space_id, "active", 100)
    return {
        "negocios": out, "secciones": SECTIONS,
        "agentes": {"pausados": bool(db.get_setting("agents_paused", False)), "en_ejecucion": sum(1 for j in active if j["status"] == "running"),
                    "en_cola": sum(1 for j in active if j["status"] == "pending"), "en_espera": sum(1 for j in active if j["status"].startswith("waiting"))},
        "transversal": {"leads": len(records.list_records(space_id, "lead")), "por_revisar": len(review.list_deliverables(space_id, status="en_revision")),
                        "borradores": len(review.list_deliverables(space_id, status="borrador")), "decisiones_abiertas": len(records.list_records(space_id, "decision", status="abierta")),
                        "clipping": clip["totales"] if clip["campanas"] else None, "alertas_clipping": len(clip["alertas"])},
        "manual": {"importado": bool(db.get_setting("doomsday_manifest")), "nota": "El manual DOOMSDAY.html no se ha importado: las misiones de esta pantalla son las que tú registras o importas por CSV. "
                   "No se ha inventado ninguna tarea del manual."},
        "nota": "El avance cuenta solo misiones con criterio de cierre y evidencia («completada verificada»). Progreso de casillas y resultado real del negocio son cosas distintas: "
                "el resultado va en Economía y en el campo «Resultado real» de cada misión. Un dato ausente se muestra como «sin datos», no como cero.",
    }
