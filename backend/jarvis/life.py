"""Vida: indicadores de cuerpo, mente, espíritu y patrimonio a partir de lo que el usuario registra.
Solo aritmética sobre sus datos: sin diagnósticos, sin recomendaciones médicas o de inversión, y «sin datos» nunca es 0."""
from __future__ import annotations
from collections import defaultdict
from datetime import date, timedelta

from . import records
from .util import now_iso

ASSETS = ("efectivo", "banco", "inversion", "propiedad", "otro_activo")


def _since(rows: list[dict], days: int, field: str = "date") -> list[dict]:
    cut = (date.today() - timedelta(days=days)).isoformat()
    return [r for r in rows if (r["data"].get(field) or "") > cut]


def _avg(values: list[float]) -> float | None:
    return round(sum(values) / len(values), 2) if values else None


def _days_to(iso: str | None) -> int | None:
    try:
        return (date.fromisoformat(iso[:10]) - date.today()).days
    except (TypeError, ValueError):
        return None


def due_cards(space_id: str) -> list[dict]:
    today = date.today().isoformat()
    return [c for c in records.list_records(space_id, "flashcard", status="activa", limit=5000) if (c["data"].get("due") or today) <= today]


def review_card(space_id: str, card_id: str, grade: int) -> dict:
    """Repetición espaciada (variante simple de SM-2). grade: 0 otra vez, 1 difícil, 2 bien, 3 fácil."""
    card = records.get(card_id, space_id)
    if not card or card["kind"] != "flashcard" or grade not in (0, 1, 2, 3):
        raise records.RecordError("Tarjeta o valoración no válida.")
    d = card["data"]
    ease, interval, reps = float(d.get("ease") or 2.5), float(d.get("interval_days") or 0), int(d.get("reps") or 0)
    if grade == 0:
        reps, interval, ease = 0, 1, max(1.3, ease - 0.2)
    else:
        base = 1 if reps == 0 else 3 if reps == 1 else interval * ease
        interval = max(1, round(base * {1: 0.6, 2: 1.0, 3: 1.3}[grade]))
        ease = max(1.3, ease + {1: -0.15, 2: 0.0, 3: 0.15}[grade])
        reps += 1
    due = (date.today() + timedelta(days=int(interval))).isoformat()
    return records.update(card_id, space_id, {"data": {"ease": round(ease, 2), "interval_days": interval, "reps": reps, "due": due}})


def summary(space_id: str) -> dict:
    L = lambda kind, **kw: records.list_records(space_id, kind, limit=20000, **kw)
    sleep, journal, workouts = L("sleep"), L("journal"), [w for w in L("workout") if w["status"] == "hecho"]
    mood = lambda rows: _avg([float(r["data"]["mood"]) for r in rows if r["data"].get("mood")])
    week_mood, prev_mood = mood(_since(journal, 7)), mood([r for r in _since(journal, 14) if r not in _since(journal, 7)])
    w7 = _since(workouts, 7)
    blocks = [b for b in _since(L("focus_block"), 7) if b["status"] == "completado"]

    worth: dict[str, dict] = defaultdict(lambda: {"activos": 0.0, "deudas": 0.0})
    stale = []
    for a in L("account", status="activa"):
        d = a["data"]
        cur = (d.get("currency") or "sin moneda").upper()
        worth[cur]["activos" if d.get("type") in ASSETS else "deudas"] += abs(d.get("balance") or 0)
        age = _days_to(d.get("updated"))
        if age is None or age < -45:
            stale.append(a["title"])
    for inv in L("investment", status="abierta"):
        d = inv["data"]
        if d.get("current_value") is not None:
            worth[(d.get("currency") or "sin moneda").upper()]["activos"] += d["current_value"]
    net = [{"moneda": c, "activos": round(v["activos"], 2), "deudas": round(v["deudas"], 2), "neto": round(v["activos"] - v["deudas"], 2)} for c, v in sorted(worth.items())]

    month = date.today().isoformat()[:7]
    spent: dict[str, float] = defaultdict(float)
    for t in L("transaction"):
        d = t["data"]
        if t["status"] == "vigente" and d.get("type") in ("gasto", "suscripcion") and d.get("stage") in ("pagado", "cobrado") and (d.get("date") or "").startswith(month):
            spent[(d.get("category") or "").strip().lower()] += abs(d.get("amount") or 0)
    budgets = []
    for b in L("budget"):
        used, limit = spent.get((b["data"].get("category") or "").strip().lower(), 0.0), b["data"].get("monthly_limit") or 0
        budgets.append({"categoria": b["data"].get("category"), "limite": limit, "gastado": round(used, 2), "moneda": b["data"].get("currency"),
                        "uso": round(used / limit, 3) if limit else None, "excedido": bool(limit and used > limit)})

    subs = L("subscription", status="activa")
    alerts = []
    by_cat: dict[str, list[str]] = defaultdict(list)
    monthly: dict[str, float] = defaultdict(float)
    for s in subs:
        d = s["data"]
        monthly[(d.get("currency") or "sin moneda").upper()] += (d.get("amount") or 0) / (12 if d.get("period") == "anual" else 1)
        if d.get("category"):
            by_cat[d["category"].strip().lower()].append(s["title"])
        left = _days_to(d.get("renewal_date"))
        if left is not None and 0 <= left <= 14:
            alerts.append({"tipo": "renovacion_proxima", "texto": f"{s['title']} se renueva en {left} día(s) por {d.get('amount')} {d.get('currency') or ''}."})
        used = _days_to(d.get("last_used"))
        if used is not None and used < -45:
            alerts.append({"tipo": "sin_uso", "texto": f"{s['title']}: sin uso registrado desde hace {-used} días."})
        if d.get("needed") in ("no", "dudoso"):
            alerts.append({"tipo": "revisar", "texto": f"{s['title']}: la marcaste como «{d['needed']}»."})
    alerts += [{"tipo": "posible_duplicado", "texto": f"Varias suscripciones en «{c}»: {', '.join(names)}."} for c, names in by_cat.items() if len(names) > 1]

    due = []
    for kind, field, label in (("admin_doc", "due_date", "Documento"), ("health_record", "next_date", "Salud"), ("care_routine", "next_date", "Cuidado"), ("investment", "review_date", "Revisar inversión")):
        for r in L(kind):
            left = _days_to(r["data"].get(field))
            if left is not None and left <= 30 and r["status"] not in ("cumplido", "resuelto", "cerrada", "pausada"):
                due.append({"tipo": label, "titulo": r["title"], "fecha": r["data"][field], "dias": left})
    due.sort(key=lambda x: x["dias"])

    return {
        "actualizado": now_iso(),
        "cuerpo": {"sueno_7d": _avg([r["data"]["hours"] for r in _since(sleep, 7) if r["data"].get("hours") is not None]),
                   "sueno_30d": _avg([r["data"]["hours"] for r in _since(sleep, 30) if r["data"].get("hours") is not None]), "noches_registradas_7d": len(_since(sleep, 7)),
                   "entrenos_7d": len(w7) if workouts else None, "minutos_entreno_7d": sum(w["data"].get("minutes") or 0 for w in w7) if workouts else None,
                   "por_comprar": len(L("pantry", status="por_comprar"))},
        "mente": {"animo_7d": week_mood, "animo_7d_previos": prev_mood, "bloques_enfoque_7d": len(blocks), "minutos_enfoque_7d": sum(b["data"].get("minutes") or 0 for b in blocks),
                  "interrupciones_7d": sum(b["data"].get("interruptions") or 0 for b in blocks), "tarjetas_para_hoy": len(due_cards(space_id)),
                  "decisiones_por_evaluar": sum(1 for c in L("choice", status="decidida") if (_days_to(c["data"].get("review_date")) or 1) <= 0)},
        "espiritu": {"devocionales_7d": len([d for d in _since(L("devotional"), 7) if d["status"] == "hecho"]), "minutos_7d": sum(d["data"].get("minutes") or 0 for d in _since(L("devotional"), 7)),
                     "oraciones_abiertas": len(L("prayer", status="abierta")) + len(L("prayer", status="en_seguimiento")), "respondidas": len(L("prayer", status="respondida"))},
        "economia": {"patrimonio": net or None, "saldos_sin_actualizar": stale, "presupuesto": budgets,
                     "suscripciones_mes": [{"moneda": c, "importe": round(v, 2)} for c, v in sorted(monthly.items())] or None, "alertas": alerts},
        "vencimientos": due,
        "nota": "Indicadores calculados solo con lo que tú registras. No son diagnóstico médico ni asesoría financiera, y Jarvis no opera dinero ni interpreta tu vida espiritual. "
                "Un valor vacío significa que aún no hay datos, no que sea cero.",
    }
