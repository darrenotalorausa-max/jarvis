"""Fábrica de contenido: brief → ángulos → hooks → guiones → shot list → variantes, por marca y sin mezclar identidades."""
from __future__ import annotations

from pydantic import BaseModel, Field

from .. import records, review
from ..jobs import JobError
from ..worker import handler
from .common import ask_json

OBJECTIVES = {"viralidad": "alcance y compartidos; apertura fuerte y ritmo", "confianza": "demostración, proceso y prueba verificable",
              "captacion": "llevar a registro o contacto con un incentivo claro", "ventas": "oferta concreta, objeciones y llamada a comprar"}


class Shot(BaseModel):
    description: str
    resource: str = Field(description="Recurso propio a usar, o 'FALTA: …' si hay que conseguirlo")


class Piece(BaseModel):
    angle: str
    hypothesis: str
    hook: str
    script: str
    on_screen_text: list[str] = Field(default_factory=list)
    shots: list[Shot] = Field(default_factory=list)
    visual_prompt: str = ""
    format: str = ""
    cta: str = ""
    copy_text: str = Field(default="", description="Texto de la publicación")
    claims_to_verify: list[str] = Field(default_factory=list, description="Afirmaciones del guion no cubiertas por los hechos comprobados")


class Batch(BaseModel):
    angles: list[str]
    pieces: list[Piece]


def brand_context(space_id: str, brand_id: str | None) -> tuple[str, list[str], dict | None]:
    """Contexto exclusivamente de la marca indicada: nunca se mezclan bibliotecas de otras marcas o clientes."""
    if not brand_id:
        return "", [], None
    brand = records.get(brand_id, space_id)
    if not brand or brand["kind"] != "brand":
        raise JobError("La marca indicada no existe en este espacio.")
    b = brand["data"]
    lines = [f"Marca: {brand['title']}", f"Voz y tono: {b.get('voice') or ''}", f"Audiencia: {b.get('audience') or ''}", f"Restricciones: {b.get('restrictions') or ''}"]
    asset_ids = []
    for a in records.list_records(space_id, "brand_asset", brand_id=brand_id, status="vigente"):
        d = a["data"]
        if d.get("type") == "permiso":
            continue
        flag = "" if d.get("permission") != "sin_confirmar" else " [permiso sin confirmar: no usar literalmente]"
        lines.append(f"[{d.get('type')}] {a['title']}: {(d.get('body') or '')[:600]}{flag}")
        asset_ids.append(a["id"])
    return "\n".join(lines), asset_ids, brand


@handler("content_batch")
def content_batch(ctx) -> dict:
    p = ctx.params
    objective = p.get("objective") or "confianza"
    if objective not in OBJECTIVES:
        raise JobError("Objetivo no reconocido.")
    count = max(1, min(int(p.get("count") or 5), 20))
    ctx_text, asset_ids, brand = brand_context(ctx.space_id, p.get("brand_id"))
    facts = [f.strip() for f in (p.get("facts") or "").splitlines() if f.strip()]
    system = ("Eres guionista de contenido corto en español. Trabaja solo con la marca, el producto y los hechos comprobados que se te dan. "
              "Prohibido inventar experiencias, credenciales, testimonios, cifras o resultados. Si un guion necesita una afirmación que no está en los "
              "hechos comprobados, inclúyela en claims_to_verify. En shots, indica el recurso propio a usar o 'FALTA: …'. "
              "visual_prompt es una indicación para una herramienta de imagen o video externa, no un video terminado.")
    pieces: list[Piece] = []
    angles: list[str] = []
    used = []
    per_call = 5
    while len(pieces) < count:
        n = min(per_call, count - len(pieces))
        ctx.stage("guiones", 0.1 + 0.8 * len(pieces) / count, f"Generando piezas {len(pieces) + 1}–{len(pieces) + n} de {count}")
        user = (f"{ctx_text}\n\nProducto u oferta: {p.get('product') or ''}\nObjetivo: {objective} ({OBJECTIVES[objective]})\nCanal: {p.get('channel') or ''}\n"
                f"Audiencia: {p.get('audience') or ''}\nReferencias de estilo: {p.get('references') or ''}\nFormato deseado: {p.get('format') or 'vertical 9:16'}\n"
                f"Recursos autorizados disponibles: {p.get('assets') or 'no indicados'}\nHechos comprobados:\n- " + ("\n- ".join(facts) if facts else "(ninguno aportado)")
                + f"\n\nGenera {n} piezas distintas" + (f". Evita repetir estos ángulos ya usados: {'; '.join(a for a in angles)}" if angles else "") + ".")
        batch, meta = ask_json(ctx, Batch, system=system, user=user, max_tokens=4000, prompt_version="contenido-v1")
        if not batch.pieces:
            raise JobError("El modelo no devolvió piezas.")
        pieces += batch.pieces[:n]
        angles += [a for a in batch.angles if a not in angles]
        used.append(meta["connection"])
    code = (brand["title"][:3].upper() if brand else "GEN") + "-" + ctx.id[-4:].upper()
    usage = ctx.router.summary()
    cost = f"{usage['costo_estimado_usd']:.4f} USD estimados" if usage["costo_estimado_usd"] else "sin costo estimado registrado (proveedor local o sin precio configurado)"
    rows, detail, missing = [], [], []
    for i, pc in enumerate(pieces, start=1):
        pid = f"{code}-{i:02d}"
        rows.append([pid, pc.angle, pc.hook, pc.format or p.get("format") or "9:16", pc.cta, "borrador", "; ".join(pc.claims_to_verify)])
        shots = "\n".join(f"{j}. {s.description} — recurso: {s.resource}" for j, s in enumerate(pc.shots, start=1))
        missing += [f"{pid}: {s.resource}" for s in pc.shots if s.resource.upper().startswith("FALTA")]
        body = (f"**Hipótesis:** {pc.hypothesis}\n\n**Hook:** {pc.hook}\n\n**Guion:**\n{pc.script}\n\n**Texto en pantalla:**\n" + "\n".join(f"- {t}" for t in pc.on_screen_text)
                + f"\n\n**Shot list:**\n{shots}\n\n**Prompt visual (para herramienta externa):** {pc.visual_prompt or '—'}\n\n**CTA:** {pc.cta}\n\n**Copy:** {pc.copy_text}")
        detail.append({"key": f"pieza_{i:02d}", "title": f"{pid} · {pc.angle}", "type": "text", "body": body,
                       "note": ("Afirmaciones por verificar antes de publicar: " + "; ".join(pc.claims_to_verify)) if pc.claims_to_verify else ""})
    sections = [
        {"key": "brief", "title": "Brief", "type": "list", "items": [f"Marca: {brand['title'] if brand else 'sin marca'}", f"Objetivo: {objective}", f"Canal: {p.get('channel') or '—'}",
                                                                     f"Audiencia: {p.get('audience') or '—'}", f"Producto: {p.get('product') or '—'}", f"Responsable: {p.get('owner') or 'sin asignar'}",
                                                                     f"Costo de generación: {cost}"]},
        {"key": "hechos_base", "title": "Hechos comprobados aportados", "type": "list", "items": facts or ["Ninguno: todo dato del guion requiere verificación."]},
        {"key": "angulos", "title": "Ángulos", "type": "list", "items": angles},
        {"key": "piezas", "title": "Lote", "type": "table", "columns": ["ID", "Ángulo", "Hook", "Formato", "CTA", "Estado", "Por verificar"], "rows": rows},
        *detail,
        {"key": "recursos_faltantes", "title": "Recursos faltantes", "type": "list", "items": missing or ["Ninguno señalado"],
         "note": "Paquete de producción: los prompts visuales no son videos terminados. Importa los activos producidos al Editor audiovisual."},
    ]
    title = f"Lote {code}: {objective} · {(p.get('product') or (brand['title'] if brand else 'contenido'))[:60]}"
    d = review.create(ctx.space_id, "content_batch", title, {"summary": f"{len(pieces)} piezas generadas con {', '.join(sorted(set(used)))}.", "sections": sections,
                      "meta": {"asset_ids": asset_ids, "brief_id": p.get("brief_id"), "objetivo": objective}}, author="jarvis", job_id=ctx.id,
                      brand_id=p.get("brand_id"), project_id=p.get("project_id"), ref_id=p.get("brief_id"))
    if p.get("brief_id") and records.get(p["brief_id"], ctx.space_id):
        records.update(p["brief_id"], ctx.space_id, {"status": "producido"})
    return {"mensaje": f"Lote {code} con {len(pieces)} piezas listo para revisión.", "deliverable_ids": [d["id"]], "piezas": len(pieces)}
