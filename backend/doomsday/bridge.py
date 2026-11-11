"""Puente Jarvis → Doomsday: el asistente (texto, voz, Telegram, horarios) puede manejar los 100 módulos.

Solo acciones internas: encolar una orden, ejecutar una herramienta de lectura o buscar un módulo. Nada externo sale por aquí.
"""
from __future__ import annotations
import re

from pydantic import BaseModel, Field

from jarvis import assistant, jobs
from jarvis.handlers.common import norm

from . import catalog, seed, tools


class OrdenArgs(BaseModel):
    modulo: str = Field(min_length=2, max_length=80, description="Código del módulo (por ejemplo G04) o parte de su nombre")
    orden: str = Field(min_length=3, max_length=4000)


class HerramientaArgs(BaseModel):
    modulo: str = Field(min_length=2, max_length=80)
    herramienta: str = ""


class BuscarArgs(BaseModel):
    busqueda: str = ""


def find_module(text: str) -> dict | None:
    code = text.strip().upper()[:3]
    if code in catalog.MODULES:
        return catalog.MODULES[code]
    q = norm(text)
    hits = [m for m in catalog.MODULES.values() if q and q in norm(m["nombre"])]
    return hits[0] if len(hits) == 1 else None


def search_modules(text: str) -> list[dict]:
    words = [w for w in norm(text).split() if len(w) > 2]
    scored = []
    for m in catalog.MODULES.values():
        hay = norm(f"{m['id']} {m['nombre']} {m['problema']} {m['solucion']} {' '.join(m['funciones'])}")
        s = sum(hay.count(w) for w in words)
        if s or not words:
            scored.append((s + m["puntos"] / 1000, m))
    return [m for _, m in sorted(scored, key=lambda x: -x[0])[:8]]


def _no_module(text: str) -> dict:
    cerca = search_modules(text)[:4]
    return {"reply": f"No encontré un módulo «{text}». " + ("Quizá: " + "; ".join(f"{m['id']} {m['nombre']}" for m in cerca) + "." if cerca else "Di «módulos de pauta» para buscar."),
            "speak": "No encontré ese módulo.", "error": True}


def _orden(space_id: str, a: OrdenArgs) -> dict:
    mod = find_module(a.modulo)
    if not mod:
        return _no_module(a.modulo)
    job, created = jobs.enqueue(seed.space_for(mod, space_id), "dd_run", f"{mod['id']} · Orden libre", {"module": mod["id"], "action": "orden", "inputs": {"orden": a.orden}})
    out = assistant._job_reply(job, created)
    out["reply"] += f" Módulo {mod['id']} · {mod['nombre']}: el resultado llegará como borrador a Revisión."
    return out


def _herramienta(space_id: str, a: HerramientaArgs) -> dict:
    mod = find_module(a.modulo)
    if not mod:
        return _no_module(a.modulo)
    tid = a.herramienta if a.herramienta in mod["tools"] else next((t for t in mod["tools"] if tools.TOOLS[t]["auto"] and t not in tools.ESCRIBEN), None)
    if not tid:
        lista = ", ".join(tools.TOOLS[t]["label"] for t in mod["tools"]) or "ninguna"
        return {"reply": f"{mod['id']} · {mod['nombre']} no tiene una herramienta que corra sin entradas. Ábrelo en su panel. Herramientas: {lista}.", "speak": "Ese módulo necesita datos de entrada; ábrelo en su panel."}
    try:
        res = tools.run(tid, seed.space_for(mod, space_id), {"_module": mod["id"]})
    except ValueError as exc:
        return {"reply": f"{tools.TOOLS[tid]['label']}: {exc}", "speak": "Faltan datos para esa herramienta.", "error": True}
    lines = [f"{mod['id']} · {res['titulo']}", res.get("resumen") or ""]
    lines += [f"· {m['label']}: {m['valor']}" for m in res["metricas"][:8]]
    lines += [f"⚠ {x}" for x in res["alertas"][:5]]
    clave = "; ".join(f"{m['label']}: {m['valor']}" for m in res["metricas"][:3])
    return {"reply": "\n".join(l for l in lines if l), "speak": (clave or res.get("resumen") or "Listo.")[:240], "data": {"modulo": mod["id"], "herramienta": tid}}


def _modulos(space_id: str, a: BuscarArgs) -> dict:
    hits = search_modules(a.busqueda)
    if not hits:
        return {"reply": f"Ningún módulo coincide con «{a.busqueda}».", "speak": "No encontré módulos para eso."}
    return {"reply": "Módulos de Doomsday:\n" + "\n".join(f"· {m['id']} {m['nombre']}: {m['solucion']}" for m in hits), "speak": f"Encontré {len(hits)} módulos; el primero es {hits[0]['nombre']}.",
            "data": {"modulos": [m["id"] for m in hits]}}


_CODE = re.compile(r"^(?:(?:doomsday|m[oó]dulo)\s+)?([A-Za-z]\d\d)\b\s*[:,.\-]?\s*(.*)$", re.S)
_LEER = re.compile(r"^(calcula\w*|ejecuta\w*|corre|estado|resumen|como va|c[oó]mo va|herramienta|datos|abre|muestra\w*)?\s*$", re.I)


def parse(raw: str):
    if m := _CODE.match(raw):
        code, rest = m.group(1).upper(), m.group(2).strip()
        if code in catalog.MODULES:
            return ("doomsday_herramienta", {"modulo": code}) if _LEER.match(rest) else ("doomsday_orden", {"modulo": code, "orden": rest})
    if m := re.match(r"^(?:calcula|ejecuta|corre|muestra)\w*\s+(?:el\s+|la\s+)?(?:m[oó]dulo\s+)?([A-Za-z]\d\d)\s*$", raw, flags=re.I):
        if m.group(1).upper() in catalog.MODULES:
            return "doomsday_herramienta", {"modulo": m.group(1).upper()}
    if re.match(r"^(?:dame\s+|hazme\s+)?(?:el\s+|mi\s+)?brief(?:\s+(?:del?\s+)?(?:d[ií]a|hoy|diario|ceo))?\s*$", raw, flags=re.I):
        return "doomsday_herramienta", {"modulo": "P07"}
    if m := re.match(r"^(?:doomsday|qu[eé]\s+m[oó]dulos?|m[oó]dulos?)\s+(?:hay\s+|tienes\s+|sirven?\s+)?(?:de|para|sobre|con)?\s*(.*)$", raw, flags=re.I):
        return "doomsday_modulos", {"busqueda": m.group(1).strip(" ?.")}
    return None


def register() -> None:
    if "doomsday_orden" in assistant.TOOLS:
        return
    assistant.tool("doomsday_orden", "Da una orden a uno de los 100 módulos de Doomsday; su skill profesional entrega un borrador revisable.", OrdenArgs, "trabajo")(_orden)
    assistant.tool("doomsday_herramienta", "Ejecuta la herramienta de cálculo de un módulo de Doomsday con los datos registrados (sin IA) y resume el resultado.", HerramientaArgs, "lectura")(_herramienta)
    assistant.tool("doomsday_modulos", "Busca entre los 100 módulos de Doomsday el que resuelve una necesidad.", BuscarArgs, "lectura")(_modulos)
    assistant.EXTRA_PARSERS.append(parse)
    assistant.EXTRA_HELP.append("También manejo los 100 módulos de Doomsday: «G04: ficha para este producto…» da una orden a un módulo, «G02 calcula» ejecuta su herramienta, "
                                "«brief» resume lo que exige decisión y «módulos de pauta» busca el módulo adecuado.")
