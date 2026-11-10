"""Control económico administrativo. Estimaciones a partir de lo que el usuario registra o importa; no es contabilidad conciliada."""
from __future__ import annotations
from collections import defaultdict

from . import records


def summary(space_id: str) -> dict:
    txs = [t for t in records.list_records(space_id, "transaction", limit=100000) if t["status"] == "vigente"]
    times = records.list_records(space_id, "time_entry", limit=100000)
    projects = {p["id"]: p["title"] for p in records.list_records(space_id, "project")}
    hours = defaultdict(float)
    for t in times:
        hours[t["project_id"] or ""] += t["data"].get("hours") or 0

    def blank():
        return {"ingreso_acordado": 0.0, "ingreso_facturado": 0.0, "ingreso_cobrado": 0.0, "gasto_pagado": 0.0, "gasto_comprometido": 0.0,
                "creditos": 0.0, "suscripciones": 0.0, "movimientos": 0}

    groups: dict[tuple[str, str], dict] = defaultdict(blank)
    for t in txs:
        d = t["data"]
        amount = abs(d.get("amount") or 0)
        cur = (d.get("currency") or "sin moneda").upper()
        for key in ((t["project_id"] or "", cur), ("*", cur)):
            g = groups[key]
            g["movimientos"] += 1
            typ, stage = d.get("type"), d.get("stage")
            if typ == "ingreso":
                g["ingreso_" + ("cobrado" if stage in ("cobrado", "pagado") else stage)] += amount
            elif typ in ("gasto", "suscripcion"):
                g["gasto_pagado" if stage in ("pagado", "cobrado") else "gasto_comprometido"] += amount
                if typ == "suscripcion":
                    g["suscripciones"] += amount
            elif typ == "credito":
                g["creditos"] += amount

    def finish(pid: str, cur: str, g: dict) -> dict:
        h = hours.get(pid, 0.0) if pid != "*" else sum(hours.values())
        contribution = g["ingreso_cobrado"] - g["gasto_pagado"]
        return {"proyecto_id": None if pid in ("", "*") else pid, "proyecto": "Total" if pid == "*" else projects.get(pid, "Sin proyecto"), "moneda": cur,
                **{k: round(v, 2) if isinstance(v, float) else v for k, v in g.items()},
                "pendiente_de_facturar": round(g["ingreso_acordado"], 2), "pendiente_de_cobrar": round(g["ingreso_facturado"], 2),
                "horas": round(h, 2), "contribucion": round(contribution, 2), "contribucion_por_hora": round(contribution / h, 2) if h else None}

    rows = [finish(pid, cur, g) for (pid, cur), g in groups.items() if pid != "*"]
    totals = [finish(pid, cur, g) for (pid, cur), g in groups.items() if pid == "*"]
    rows.sort(key=lambda r: (r["moneda"], -r["contribucion"]))
    subs = [{"id": t["id"], "titulo": t["title"], "importe": t["data"].get("amount"), "moneda": t["data"].get("currency"), "fecha": t["data"].get("date"),
             "contraparte": t["data"].get("counterparty")} for t in txs if t["data"].get("type") == "suscripcion"]
    return {"por_proyecto": rows, "totales": totals, "suscripciones": subs, "horas_sin_proyecto": round(hours.get("", 0.0), 2),
            "nota": "Cada movimiento cuenta una sola vez en su estado actual: acordado (pendiente de facturar), facturado (pendiente de cobrar) o cobrado. "
                    "Las tres columnas no se suman. Contribución = ingresos cobrados − gastos pagados; es una estimación administrativa basada en lo registrado, "
                    "no contabilidad conciliada ni asesoría fiscal. No se convierten monedas."}
