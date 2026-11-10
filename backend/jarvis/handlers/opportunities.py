"""Mesa de oportunidades: búsqueda real, evidencia con fuente y fecha, expediente editable."""
from __future__ import annotations
from typing import Literal

from pydantic import BaseModel, Field

from .. import files, records, review, router, webfetch
from ..jobs import JobError
from ..worker import handler
from .common import ask_json, available, quote_in_text, save_source, sources_block

SIGNALS = {"popularidad": "Popularidad", "interes": "Interés", "intencion": "Intención", "compra": "Compra comprobable"}
SCORE_LABELS = {"evidencia_demanda": "Evidencia de demanda", "competencia": "Espacio frente a la competencia", "viabilidad": "Viabilidad operativa",
                "margen": "Encaje con el margen objetivo", "calidad_evidencia": "Calidad de la evidencia"}


class Fact(BaseModel):
    claim: str
    signal: Literal["popularidad", "interes", "intencion", "compra"] = "interes"
    source: str
    quote: str = Field(description="Cita textual breve copiada de la fuente")
    limitations: str = ""


class Alt(BaseModel):
    name: str
    note: str = ""
    source: str = ""


class Step(BaseModel):
    step: str
    limit: str = Field(description="Límite de tiempo o dinero de la prueba")
    success_signal: str


class Score(BaseModel):
    value: int = Field(ge=0, le=5)
    rationale: str


class Analysis(BaseModel):
    buyer: str
    problem: str
    facts: list[Fact] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)
    alternatives: list[Alt] = Field(default_factory=list)
    opportunity: str
    risks: list[str] = Field(default_factory=list)
    missing_data: list[str] = Field(default_factory=list)
    validation_plan: list[Step] = Field(default_factory=list)
    scores: dict[str, Score] = Field(default_factory=dict)


def build_queries(p: dict) -> list[str]:
    topic = " ".join(filter(None, [p.get("category"), p.get("question")])).strip() or p.get("question") or ""
    core = p.get("category") or p.get("question") or ""
    country = p.get("country") or ""
    es = (p.get("language") or "es").lower().startswith("es")
    templates = ([topic, f"{core} problemas quejas {country}", f"{core} opiniones reseñas", f"{core} alternativas comparativa",
                  f"{core} precio comprar {country}", f"{core} {p.get('buyer_type') or ''} necesita solución"] if es else
                 [topic, f"{core} problems complaints {country}", f"{core} reviews", f"{core} alternatives comparison",
                  f"{core} price buy {country}", f"{core} {p.get('buyer_type') or ''} needs solution"])
    out = []
    for q in templates:
        q = " ".join(q.split())
        if q and q not in out:
            out.append(q)
    return out[: max(1, min(int(p.get("max_queries") or 4), 8))]


def collect_evidence(ctx, p: dict, queries: list[str], max_pages: int) -> tuple[list[dict], dict]:
    """Devuelve (fuentes guardadas, cobertura). Usado también por el módulo de leads."""
    coverage = {"consultas": [], "sin_busqueda": None, "paginas_solicitadas": 0}
    sources, seen = [], set()
    hits = []
    has_search = available(ctx, "busqueda")
    if queries and not has_search:
        coverage["sin_busqueda"] = "No hay proveedor de búsqueda disponible; solo se usaron las URLs y archivos aportados."
    if has_search:
        for i, q in enumerate(queries):
            ctx.stage("busqueda", 0.05 + 0.25 * i / max(1, len(queries)), f"Buscando: {q}")
            found, meta = router.search(ctx.router, q, count=8, country=p.get("country_code"), lang=p.get("language"), freshness=p.get("freshness"))
            coverage["consultas"].append({"consulta": q, "resultados": len(found), "proveedor": meta["connection"], "en_cache": meta["cached"], "obtenido": meta["obtained_at"]})
            for h in found:
                if h.url not in seen:
                    seen.add(h.url)
                    hits.append((h, q, meta))
    excl = [e.strip().lower() for e in (p.get("exclusions") or "").replace(";", ",").split(",") if e.strip()]
    todo = [(u, None, "", None) for u in (p.get("urls") or []) if u.strip()]
    for h, q, meta in hits:
        if any(e in (h.title + " " + h.url).lower() for e in excl):
            continue
        todo.append((h.url, h, q, meta))
    todo = todo[: max_pages + len(p.get("urls") or [])]
    coverage["paginas_solicitadas"] = len(todo)
    for i, (url, hit, q, meta) in enumerate(todo):
        ctx.stage("lectura", 0.3 + 0.35 * i / max(1, len(todo)), f"Leyendo fuente {i + 1} de {len(todo)}")
        page = webfetch.fetch_page(url)
        provider = meta["connection"] if meta else "URL aportada"
        if page["status"] == "ok":
            sources.append(save_source(ctx, url=page["url"], title=page.get("title") or (hit.title if hit else url), provider=provider, query=q,
                                       snippet=(hit.snippet if hit else page.get("description") or page["text"][:300]),
                                       published_at=page.get("published_at") or (hit.published_at if hit else None), text=page["text"], note=page.get("note", "")))
        elif hit and hit.snippet:
            sources.append(save_source(ctx, url=url, title=hit.title, provider=provider, query=q, snippet=hit.snippet, published_at=hit.published_at,
                                       status="solo_fragmento", note=f"Página no leída ({page['note']}); solo se dispone del fragmento del buscador.", text=hit.snippet))
        else:
            sources.append(save_source(ctx, url=url, title=url, provider=provider, query=q, status=page["status"], note=page["note"]))
    for fid in p.get("file_ids") or []:
        f = files.get(fid, ctx.space_id)
        if not f:
            continue
        text = webfetch.file_to_text(files.path_of(f), f["name"])
        sources.append(save_source(ctx, url=f"archivo:{f['id']}", title=f["name"], provider="Archivo importado", text=text, snippet=text[:300],
                                   status="ok" if text.strip() else "no_disponible", note="" if text.strip() else "No se pudo extraer texto del archivo."))
    return sources, coverage


def _criteria(p: dict) -> list[str]:
    labels = [("business_type", "Tipo de negocio"), ("country", "País"), ("language", "Idioma"), ("category", "Categoría"), ("exclusions", "Exclusiones"),
              ("price_range", "Rango de precios"), ("buyer_type", "Tipo de comprador"), ("offer_type", "Tipo de oferta"), ("logistics", "Restricciones de logística"),
              ("competition", "Competencia"), ("seasonality", "Estacionalidad"), ("recurrence", "Recurrencia del problema"), ("target_margin", "Margen objetivo"),
              ("freshness", "Frescura exigida")]
    return [f"{lab}: {p[k]}" for k, lab in labels if p.get(k)]


@handler("opportunity_research")
def opportunity_research(ctx) -> dict:
    p = ctx.params
    if not (p.get("question") or p.get("category") or p.get("urls") or p.get("file_ids")):
        raise JobError("Indica una pregunta, una categoría o al menos una URL o archivo.")
    queries = build_queries(p) if (p.get("question") or p.get("category")) else []
    if queries and not available(ctx, "busqueda") and not (p.get("urls") or p.get("file_ids")):
        raise router.RouterError("needs_config", "La investigación necesita un proveedor de búsqueda (Brave o Tavily) o que aportes URLs o archivos. Configúralo en Conexiones.")
    sources, coverage = collect_evidence(ctx, p, queries, max(1, min(int(p.get("max_pages") or 6), 15)))
    usable = [s for s in sources if s["status"] in ("ok", "solo_fragmento") and (s["text"] or s["snippet"])]
    title = f"Oportunidad: {p.get('question') or p.get('category') or 'material aportado'}"[:200]
    limits = [f"Se ejecutaron {len(coverage['consultas'])} consultas y se solicitaron {coverage['paginas_solicitadas']} páginas; no es una revisión exhaustiva de internet.",
              f"Fuentes utilizables: {len(usable)} de {len(sources)}."]
    if coverage["sin_busqueda"]:
        limits.append(coverage["sin_busqueda"])
    limits += [f"No disponible: {s['url']} — {s['note']}" for s in sources if s["status"] in ("bloqueada", "no_disponible")][:10]
    src_table = {"key": "fuentes_consultadas", "title": "Fuentes consultadas y cobertura", "type": "table",
                 "columns": ["ID", "Título", "URL", "Consultada", "Publicada", "Estado", "Nota"],
                 "rows": [[s["id"], s["title"], s["url"], s["fetched_at"], s["published_at"] or "no disponible", s["status"], s["note"]] for s in sources]}
    sections = [{"key": "criterios", "title": "Criterios de la investigación", "type": "list", "items": _criteria(p) or ["Sin filtros adicionales"]}]
    analysis_state = "pendiente"
    if usable and available(ctx, "extraccion"):
        ctx.stage("analisis", 0.7, "Extrayendo hechos y armando el expediente")
        block, labels = sources_block(usable[:12])
        system = ("Eres un analista de oportunidades de negocio riguroso. A partir exclusivamente de las fuentes, separa hechos de hipótesis. "
                  "Cada hecho lleva la etiqueta de su fuente (S1, S2…) y una cita textual breve copiada de ella. Clasifica la señal de cada hecho: "
                  "popularidad (se habla de ello), interes (se busca o pregunta), intencion (se compara o quiere comprar), compra (venta o pago comprobable). "
                  "Las puntuaciones (0-5) son orientativas, no probabilidades de éxito; usa las claves: " + ", ".join(SCORE_LABELS) + ". "
                  "El plan de validación debe ser pequeño y con límite explícito. Escribe en español.")
        user = f"Pregunta: {p.get('question') or ''}\nCriterios:\n- " + "\n- ".join(_criteria(p) or ["(sin filtros)"]) + f"\n\nFuentes:\n{block}"
        analysis, meta = ask_json(ctx, Analysis, system=system, user=user, max_tokens=3500, ttl_s=24 * 3600, prompt_version="oportunidad-v1")
        facts, demoted = [], 0
        for f in analysis.facts:
            src = labels.get(f.source.strip().upper())
            ok = bool(src) and quote_in_text(f.quote, src["text"] or src["snippet"])
            if ok:
                facts.append({"claim": f.claim, "kind": "hecho", "signal": SIGNALS[f.signal], "source_ids": [src["id"]], "evidence": f.quote,
                              "limitations": f.limitations + ("" if src["status"] == "ok" else " Basado solo en el fragmento del buscador.")})
            else:
                demoted += 1
                facts.append({"claim": f.claim, "kind": "hipotesis", "signal": SIGNALS[f.signal], "source_ids": [src["id"]] if src else [], "evidence": "",
                              "limitations": "La cita aportada por el modelo no se localizó en la fuente; se degrada a hipótesis hasta revisarla."})
        facts += [{"claim": h, "kind": "hipotesis", "source_ids": [], "evidence": "", "limitations": ""} for h in analysis.hypotheses]
        facts += [{"claim": m, "kind": "desconocido", "source_ids": [], "evidence": "", "limitations": ""} for m in analysis.missing_data]
        if demoted:
            limits.append(f"{demoted} afirmación(es) del modelo no pudieron verificarse contra el texto de su fuente y figuran como hipótesis.")
        sections += [
            {"key": "comprador", "title": "Comprador y problema", "type": "text", "body": f"**Comprador:** {analysis.buyer}\n\n**Problema:** {analysis.problem}"},
            {"key": "hechos", "title": "Hechos, hipótesis y desconocidos", "type": "facts", "items": facts,
             "note": "Señales: popularidad ≠ interés ≠ intención ≠ compra comprobable."},
            {"key": "alternativas", "title": "Alternativas y competencia", "type": "table", "columns": ["Alternativa", "Nota", "Fuente"],
             "rows": [[a.name, a.note, labels[a.source.strip().upper()]["id"] if a.source.strip().upper() in labels else ""] for a in analysis.alternatives]},
            {"key": "oportunidad", "title": "Oportunidad propuesta", "type": "text", "body": analysis.opportunity},
            {"key": "riesgos", "title": "Riesgos", "type": "list", "items": analysis.risks},
            {"key": "validacion", "title": "Plan de validación limitado", "type": "table", "columns": ["Paso", "Límite", "Señal de éxito"],
             "rows": [[s.step, s.limit, s.success_signal] for s in analysis.validation_plan]},
            {"key": "puntuaciones", "title": "Puntuaciones desglosadas", "type": "scores",
             "items": [{"label": SCORE_LABELS.get(k, k), "value": v.value, "rationale": v.rationale} for k, v in analysis.scores.items()],
             "note": f"Valoración orientativa generada por {meta['connection']} ({meta.get('model') or 'modelo sin nombre'}). No es una probabilidad de éxito."},
        ]
        analysis_state = "completo"
    else:
        reason = "no se obtuvo ninguna fuente utilizable" if not usable else "no hay un modelo de texto disponible para este espacio"
        sections += [
            {"key": "comprador", "title": "Comprador y problema", "type": "text", "body": "", "note": f"Análisis pendiente: {reason}."},
            {"key": "hechos", "title": "Evidencia recopilada (sin analizar)", "type": "facts",
             "items": [{"claim": s["title"], "kind": "desconocido", "source_ids": [s["id"]], "evidence": (s["snippet"] or "")[:280],
                        "limitations": "Fragmento sin analizar; requiere lectura."} for s in usable]},
            {"key": "oportunidad", "title": "Oportunidad propuesta", "type": "text", "body": ""},
            {"key": "riesgos", "title": "Riesgos", "type": "list", "items": []},
            {"key": "validacion", "title": "Plan de validación limitado", "type": "table", "columns": ["Paso", "Límite", "Señal de éxito"], "rows": []},
        ]
    sections += [src_table, {"key": "limites", "title": "Límites de esta investigación", "type": "list", "items": limits}]
    summary = ("Expediente generado a partir de fuentes consultadas. Revisa hechos y fuentes antes de decidir."
               if analysis_state == "completo" else "Evidencia recopilada sin análisis automático. Completa el expediente manualmente o configura un modelo y relanza.")
    d = review.create(ctx.space_id, "dossier", title, {"summary": summary, "sections": sections, "source_ids": [s["id"] for s in sources],
                                                        "meta": {"criterios": p, "analisis": analysis_state, "cobertura": coverage}},
                      author="jarvis", job_id=ctx.id, project_id=p.get("project_id"))
    ctx.stage("entregable", 0.98, "Expediente creado")
    return {"mensaje": f"Expediente creado con {len(usable)} fuentes utilizables (análisis: {analysis_state}).", "deliverable_ids": [d["id"]],
            "analisis": analysis_state, "fuentes": len(sources), "fuentes_utilizables": len(usable)}


def _section(content: dict, key: str) -> dict:
    return next((s for s in content["sections"] if s["key"] == key), {"body": "", "items": [], "rows": []})


def convert(deliverable_id: str, space_id: str, target: str) -> dict:
    """Convierte un expediente en producto, oferta B2B, brief de contenido o proyecto (registros editables enlazados)."""
    d = review.detail(deliverable_id, space_id)
    if not d or d["kind"] != "dossier":
        raise review.ReviewError("Solo un expediente de oportunidad puede convertirse.")
    c = d["version"]["content"]
    name = d["title"].removeprefix("Oportunidad: ")[:120]
    opp, buyer = _section(c, "oportunidad")["body"], _section(c, "comprador")["body"]
    origin = f"Origen: expediente {d['id']} v{d['current_version']}."
    facts = [f"{it['claim']} (fuentes: {', '.join(it.get('source_ids', []))})" for it in _section(c, "hechos")["items"] if it.get("kind") == "hecho"]
    if target == "producto":
        rec = records.create(space_id, "product", name, {"audience": buyer, "specs": "", "conditions": "", "benefits": ""}, project_id=d["project_id"])
        note = "Producto en borrador: completa especificaciones, precio y condiciones reales antes de generar el paquete."
    elif target == "oferta_b2b":
        rec = records.create(space_id, "service", name, {"description": f"{opp}\n\n{origin}", "deliverables": ""})
        note = "Servicio añadido a tu catálogo de ofertas B2B; define entregables y precio."
    elif target == "brief":
        rec = records.create(space_id, "brief", name, {"audience": buyer, "product": opp, "facts": "\n".join(facts), "notes": origin}, project_id=d["project_id"])
        note = "Brief creado con los hechos respaldados del expediente."
    elif target == "proyecto":
        rec = records.create(space_id, "project", name, {"description": f"{opp}\n\n{origin}"})
        plan = _section(c, "validacion")["rows"]
        for row in plan[:8]:
            records.create(space_id, "milestone", str(row[0])[:200], {"notes": f"Límite: {row[1] if len(row) > 1 else ''}. Señal: {row[2] if len(row) > 2 else ''}"}, project_id=rec["id"])
        note = f"Proyecto creado con {min(len(plan), 8)} hitos del plan de validación."
    else:
        raise review.ReviewError("Destino de conversión no reconocido.")
    return {"record": rec, "nota": note}
