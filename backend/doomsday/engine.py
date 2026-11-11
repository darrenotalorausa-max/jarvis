"""Ejecutor de órdenes de Doomsday: skill del módulo + datos + evidencia calculada → entregable revisable.

Reglas del motor que aquí se cumplen: la salida del modelo entra solo como datos validados (`ask_json`); las fuentes web van entre
<fuente>; sin IA el trabajo espera configuración o entrega únicamente la evidencia calculada; nada externo se ejecuta desde aquí.
"""
from __future__ import annotations
import json

from pydantic import BaseModel, Field

from jarvis import db, records, review, webfetch
from jarvis.handlers.common import ask_json, available, save_source, sources_block
from jarvis.jobs import JobError
from jarvis.worker import handler

from . import catalog, skills, tools

PROMPT_VERSION = "dd1"
EMIT_STATUS = {"dd_mensaje": "borrador_listo", "dd_prospecto": "borrador_listo", "dd_nota": "procesada", "dd_voz": "vigente"}

review.KINDS.setdefault("dd", {"label": "Entregable Doomsday", "required": ["resumen"]})
review.HUMAN_CHECKS.setdefault("dd", ["Que cada cifra y afirmación coincida con tus datos reales", "Que el resultado sirva tal cual o qué hay que ajustar",
                                      "Decisión de publicar, enviar o gastar: siempre es tuya"])


class Seccion(BaseModel):
    titulo: str
    contenido: str


class Elemento(BaseModel):
    titulo: str
    campos: dict = Field(default_factory=dict)
    nota: str = ""


class Comprobacion(BaseModel):
    criterio: str
    cumple: bool
    nota: str = ""


class Entrega(BaseModel):
    titulo: str
    resumen: str
    secciones: list[Seccion] = Field(default_factory=list)
    elementos: list[Elemento] = Field(default_factory=list)
    comprobaciones: list[Comprobacion] = Field(default_factory=list)
    supuestos: list[str] = Field(default_factory=list)
    limitaciones: list[str] = Field(default_factory=list)
    preguntas: list[str] = Field(default_factory=list)


def find_action(mod: dict, action_id: str) -> dict:
    act = next((a for a in mod["acciones"] if a["id"] == action_id), None)
    if not act:
        raise JobError("La acción no existe en este módulo.")
    return act


def clean_inputs(act: dict, inputs: dict) -> dict:
    out = {}
    for f in act["campos"]:
        v = (inputs or {}).get(f["name"])
        if v not in (None, ""):
            out[f["name"]] = str(v)[:60_000] if isinstance(v, str) else v
    return out


def _records_block(space_id: str, kinds: list[str], limit: int = 40) -> str:
    parts = []
    for kind in kinds:
        rows = records.list_records(space_id, kind, limit=limit)
        if not rows:
            continue
        spec = records.KINDS[kind]
        lines = [json.dumps({"titulo": r["title"], "estado": r["status"], **{k: (v[:600] if isinstance(v, str) else v) for k, v in r["data"].items() if v not in (None, "", [])}},
                            ensure_ascii=False) for r in rows]
        parts.append(f"<datos tipo=\"registros\" clase=\"{spec['plural']}\" total_mostrado=\"{len(rows)}\">\n" + "\n".join(lines) + "\n</datos>")
    return "\n\n".join(parts)


def _tool_sections(res: dict) -> list[dict]:
    out = []
    if res.get("metricas"):
        out.append({"key": "indicadores", "title": f"{res['titulo']} · indicadores", "type": "table", "columns": ["Indicador", "Valor"],
                    "rows": [[m["label"], m["valor"]] for m in res["metricas"]], "note": res.get("resumen") or ""})
    for i, t in enumerate(res.get("tablas") or []):
        if t["filas"]:
            out.append({"key": f"calculo{i}", "title": t["titulo"], "type": "table", "columns": t["columnas"], "rows": [list(r) for r in t["filas"][:120]],
                        "note": "Calculado con tus registros, sin IA."})
    if res.get("alertas"):
        out.append({"key": "alertas", "title": "Alertas del cálculo", "type": "list", "items": res["alertas"]})
    return out


def _compact_tool(res: dict) -> str:
    slim = {"resumen": res.get("resumen"), "indicadores": {m["label"]: m["valor"] for m in res.get("metricas") or []}, "alertas": res.get("alertas"),
            "tablas": [{"titulo": t["titulo"], "columnas": t["columnas"], "filas": t["filas"][:40]} for t in res.get("tablas") or []]}
    return f"<datos tipo=\"calculo\" herramienta=\"{res['titulo']}\">\n{json.dumps(slim, ensure_ascii=False)}\n</datos>"


def _emit(ctx, kind: str, elementos: list[Elemento]) -> list[str]:
    """Crea un registro por elemento. Cada campo se valida por separado: los que no encajan en el esquema se descartan, nunca se fuerzan."""
    spec, ids = records.KINDS[kind], []
    names = {f["name"] for f in spec["fields"]}
    status = EMIT_STATUS.get(kind)
    for el in elementos[:60]:
        data = {}
        for k, v in (el.campos or {}).items():
            if k in names and v not in (None, ""):
                try:
                    data.update(records.validate(kind, {k: v}, partial=True))
                except records.RecordError:
                    ctx.log(f"Campo «{k}» descartado en «{el.titulo[:60]}»: no cumple el esquema.")
        try:
            ids.append(records.create(ctx.space_id, kind, el.titulo, data, status=status)["id"])
        except records.RecordError as exc:
            ctx.log(f"No se creó el registro «{el.titulo[:60]}»: {exc}")
    return ids


@handler("dd_run")
def dd_run(ctx):
    p = ctx.params
    mod = catalog.MODULES.get(p.get("module") or "")
    if not mod:
        raise JobError("El módulo no existe.")
    act = find_action(mod, p.get("action") or "orden")
    inputs = clean_inputs(act, p.get("inputs") or {})
    if act["campos"] and not inputs and act["id"] == "orden":
        raise JobError("Escribe la orden.")

    ctx.stage("contexto", 0.1, "Reuniendo datos del módulo")
    evidencia, nota_tool = None, ""
    tool_id = act.get("herramienta") or next((t for t in mod["tools"] if tools.TOOLS[t]["auto"]), None)
    if tool_id:
        try:
            evidencia = tools.run(tool_id, ctx.space_id, inputs)
        except ValueError as exc:
            nota_tool = f"La herramienta «{tools.TOOLS[tool_id]['label']}» no se ejecutó: {exc}"

    fuentes = []
    for f in act["campos"]:
        if f["type"] == "url" and inputs.get(f["name"]):
            ctx.stage("fuentes", 0.25, "Leyendo la fuente indicada")
            page = webfetch.fetch_page(str(inputs[f["name"]]))
            fuentes.append(save_source(ctx, url=page["url"], title=page.get("title") or "", provider="webfetch", status=page["status"], note=page.get("note") or "",
                                       text=page.get("text") or "", published_at=page.get("published_at")))
    legibles = [s for s in fuentes if s["status"] == "ok" and s["text"]]

    secciones: list[dict] = []
    meta = {"modulo": mod["id"], "accion": act["id"], "entradas": {k: (v if not isinstance(v, str) else v[:400]) for k, v in inputs.items()}}
    if not available(ctx, "extraccion"):
        if not evidencia or not (evidencia.get("metricas") or evidencia.get("tablas")):
            ask_json(ctx, Entrega, system="-", user="-")  # sin IA y sin evidencia: el router explica qué falta y el trabajo queda esperando configuración
        ctx.log("No hay IA disponible en este espacio: se entrega solo la evidencia calculada.")
        resumen = "Sin IA disponible: este entregable contiene únicamente la evidencia calculada con tus registros, sin interpretación. " + (evidencia.get("resumen") or "")
        d = review.create(ctx.space_id, "dd", f"{mod['id']} · {evidencia['titulo']}",
                          {"summary": resumen, "sections": [{"key": "resumen", "title": "Resumen", "type": "text", "body": resumen}] + _tool_sections(evidencia),
                           "meta": {**meta, "sin_ia": True}}, author="doomsday", job_id=ctx.id, ref_id=mod["id"])
        return {"deliverable_ids": [d["id"]], "mensaje": "Entregada solo la evidencia calculada (sin IA disponible)"}

    emit_fields = records.KINDS[act["emite"]]["fields"] if act.get("emite") else None
    system, skill = skills.system_prompt(mod, act, emit_fields)
    bloque_fuentes, _ = sources_block(legibles, per_source_chars=9000)
    user = "\n\n".join(x for x in [
        "ENTRADAS DEL USUARIO:\n" + json.dumps(inputs, ensure_ascii=False, indent=1) if inputs else "",
        _compact_tool(evidencia) if evidencia else "", nota_tool,
        _records_block(ctx.space_id, act["contexto"] or []),
        bloque_fuentes,
        "; ".join(f"No se pudo leer {s['url']}: {s['note'] or s['status']}" for s in fuentes if s not in legibles),
    ] if x) or "Sin datos adicionales."
    ctx.stage("redaccion", 0.45, f"Aplicando la skill {mod['id']} (v{skill['version']}, {skill['origen']})")
    entrega, usage = ask_json(ctx, Entrega, system=system, user=user, max_tokens=8000, prompt_version=f"{PROMPT_VERSION}:{mod['id']}:{skill['version']}:{skill['origen']}")

    ctx.stage("entregable", 0.85, "Armando el entregable")
    secciones.append({"key": "resumen", "title": "Resumen", "type": "text", "body": entrega.resumen})
    for i, s in enumerate(entrega.secciones[:40]):
        secciones.append({"key": f"s{i + 1}", "title": s.titulo[:200], "type": "text", "body": s.contenido})
    if entrega.elementos:
        cols = []
        for el in entrega.elementos:
            cols += [k for k in el.campos if k not in cols]
        cols = cols[:8]
        labels = {f["name"]: f["label"] for f in emit_fields or []}
        secciones.append({"key": "elementos", "title": "Elementos", "type": "table", "columns": ["Elemento", *[labels.get(c, c) for c in cols], "Nota"],
                          "rows": [[el.titulo, *[str(el.campos.get(c, "") if el.campos.get(c) is not None else "") for c in cols], el.nota] for el in entrega.elementos[:80]]})
    if evidencia:
        secciones += _tool_sections(evidencia)
    if "cumplimiento" in mod["tools"] and tool_id != "cumplimiento":
        texto = "\n".join([entrega.resumen] + [s.contenido for s in entrega.secciones] + [f"{el.titulo} {' '.join(str(v) for v in el.campos.values())}" for el in entrega.elementos])
        hall = tools.scan_cumplimiento(texto, tools.recs(ctx.space_id, "dd_politica", "vigente"))
        secciones.append({"key": "cumplimiento", "title": "Revisión automática de cumplimiento (X07)", "type": "table" if hall else "text", "columns": ["Gravedad", "Regla", "Fragmento"],
                          "rows": hall[:60], "body": "" if hall else "Sin hallazgos con los patrones conocidos. Reduce el riesgo; no garantiza la aprobación de la plataforma.",
                          "note": "Corrige los hallazgos graves antes de publicar." if any(h[0] == "alta" for h in hall) else ""})
    if entrega.comprobaciones:
        secciones.append({"key": "comprobaciones", "title": "Autoevaluación contra el estándar de la skill", "type": "table", "columns": ["Criterio", "Cumple", "Nota"],
                          "rows": [[c.criterio, "sí" if c.cumple else "NO", c.nota] for c in entrega.comprobaciones[:30]]})
    for key, title, items in (("supuestos", "Supuestos", entrega.supuestos), ("limitaciones", "Limitaciones y datos que faltan", entrega.limitaciones),
                              ("preguntas", "Preguntas que cambiarían el resultado", entrega.preguntas)):
        if items:
            secciones.append({"key": key, "title": title, "type": "list", "items": items[:30]})
    d = review.create(ctx.space_id, "dd", f"{mod['id']} · {entrega.titulo}"[:300],
                      {"summary": entrega.resumen[:1200], "sections": secciones, "source_ids": [s["id"] for s in fuentes],
                       "meta": {**meta, "skill_version": skill["version"], "skill_origen": skill["origen"], "conexion": usage.get("connection")}},
                      author="doomsday", job_id=ctx.id, ref_id=mod["id"])
    creados = _emit(ctx, act["emite"], entrega.elementos) if act.get("emite") and entrega.elementos else []
    db.audit("dd_run", mod["id"], {"accion": act["id"], "entregable": d["id"], "registros": len(creados), "skill": f"{skill['origen']} v{skill['version']}"}, actor="doomsday")
    extra = f" y {len(creados)} registros en «{records.KINDS[act['emite']]['plural']}»" if creados else ""
    return {"deliverable_ids": [d["id"]], "record_ids": creados, "mensaje": f"Entregable listo para tu revisión{extra}"}
