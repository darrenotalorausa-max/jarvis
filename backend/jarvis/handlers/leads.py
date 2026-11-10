"""Empleado de leads B2B: búsqueda en fuentes públicas, deduplicación, observación verificable y propuesta revisable."""
from __future__ import annotations
import re
from datetime import date

from pydantic import BaseModel, Field

from .. import db, records, review, router, webfetch
from ..jobs import JobError
from ..worker import handler
from .common import ask_json, available, quote_in_text, save_source

# Directorios y redes: sirven como fuente, no como web propia de una empresa.
AGGREGATORS = {"facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com", "wikipedia.org", "yelp.com",
               "tripadvisor.com", "google.com", "maps.google.com", "amazon.com", "mercadolibre.com", "reddit.com", "pinterest.com", "paginasamarillas.es",
               "yellowpages.com", "trustpilot.com", "glassdoor.com", "crunchbase.com", "medium.com", "apple.com", "play.google.com"}
_MAIL = re.compile(r"^mailto:([^?]+)", re.I)
_TEL = re.compile(r"^tel:(.+)", re.I)


class Observation(BaseModel):
    company: str = Field(description="Nombre comercial tal como aparece en su web")
    segment: str = ""
    observation: str = Field(description="Hecho observable en la web, sin juicios")
    quote: str = Field(description="Cita textual breve de la web que respalda la observación")
    hypotheses: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    fit: bool = Field(description="True si el servicio indicado es pertinente para esta empresa según lo observado")
    fit_reason: str = ""


class Sample(BaseModel):
    deliverable: str
    max_time: str
    revisions: str
    limits: str


class Offer(BaseModel):
    problem: str
    objective: str
    deliverables: list[str]
    exclusions: list[str]
    inputs_needed: list[str]
    timeline: str
    revisions: str
    acceptance: str


class Message(BaseModel):
    subject: str
    body: str


class Proposal(BaseModel):
    sample: Sample
    offer: Offer
    message: Message


def public_channel(page: dict) -> str:
    """Canal comercial que la propia empresa publica en su web (correo, teléfono o página de contacto)."""
    mails, tels, contact = [], [], ""
    for href, text in page.get("links") or []:
        if m := _MAIL.match(href):
            mails.append(m.group(1).strip())
        elif t := _TEL.match(href):
            tels.append(t.group(1).strip())
        elif not contact and re.search(r"contact|contacto|presupuesto|agenda|reserva", (href + " " + text).lower()):
            contact = href if href.startswith("http") else webfetch.urljoin(page["url"], href)
    parts = [f"correo: {mails[0]}"] if mails else []
    parts += [f"teléfono: {tels[0]}"] if tels else []
    parts += [f"contacto: {contact}"] if contact else []
    return "; ".join(parts)


def excluded(space_id: str) -> set[str]:
    return {(r["data"].get("domain") or r["title"]).strip().lower() for r in records.list_records(space_id, "exclusion")}


def known_domains(space_id: str) -> set[str]:
    out = set()
    for archived in (False, True):
        out |= {(r["data"].get("domain") or "").lower() for r in records.list_records(space_id, "lead", archived=archived)}
    return out - {""}


@handler("lead_search")
def lead_search(ctx) -> dict:
    p = ctx.params
    urls = [u for u in (p.get("urls") or []) if u.strip()]
    if not (p.get("sector") or urls):
        raise JobError("Indica al menos el sector o una lista de webs.")
    max_c = max(1, min(int(p.get("max_candidates") or 8), 25))
    candidates: dict[str, dict] = {}
    for u in urls:
        candidates.setdefault(webfetch.domain_of(u), {"url": u, "source_url": u, "provider": "URL aportada", "query": ""})
    if p.get("sector"):
        if not available(ctx, "busqueda") and not urls:
            raise router.RouterError("needs_config", "Buscar empresas requiere un proveedor de búsqueda (Brave o Tavily), o aporta una lista de webs.")
        if available(ctx, "busqueda"):
            base = " ".join(filter(None, [p.get("sector"), p.get("location")]))
            queries = [base, f"{base} {p.get('signals') or ''}".strip(), f"{base} {p.get('client_type') or 'empresa'} sitio oficial"]
            for i, q in enumerate(dict.fromkeys(queries)):
                if len(candidates) >= max_c * 2:
                    break
                ctx.stage("busqueda", 0.05 + 0.2 * i / 3, f"Buscando: {q}")
                hits, meta = router.search(ctx.router, q, count=10, lang=p.get("language"))
                for h in hits:
                    dom = webfetch.domain_of(h.url)
                    if dom and not any(dom == a or dom.endswith("." + a) for a in AGGREGATORS):
                        candidates.setdefault(dom, {"url": f"https://{dom}/", "source_url": h.url, "provider": meta["connection"], "query": q})
    skip_ex, skip_known = excluded(ctx.space_id), known_domains(ctx.space_id)
    stats = {"candidatos": len(candidates), "excluidos": 0, "duplicados": 0, "no_accesibles": 0, "sin_encaje": 0, "creados": 0}
    created = []
    use_llm = available(ctx, "extraccion")
    todo = []
    for dom, cand in candidates.items():
        if dom in skip_ex or any(e and e in dom for e in skip_ex):
            stats["excluidos"] += 1
        elif dom in skip_known:
            stats["duplicados"] += 1
        else:
            todo.append((dom, cand))
    for i, (dom, cand) in enumerate(todo[:max_c]):
        ctx.stage("investigacion", 0.3 + 0.65 * i / max(1, min(len(todo), max_c)), f"Investigando {dom}")
        page = webfetch.fetch_page(cand["url"])
        if page["status"] != "ok" or not page["text"].strip():
            stats["no_accesibles"] += 1
            save_source(ctx, url=cand["url"], title=dom, provider=cand["provider"], query=cand["query"], status=page["status"], note=page.get("note", ""))
            continue
        src = save_source(ctx, url=page["url"], title=page.get("title") or dom, provider=cand["provider"], query=cand["query"],
                          snippet=page.get("description") or page["text"][:300], text=page["text"], published_at=page.get("published_at"))
        data = {"website": page["url"], "domain": dom, "source_url": cand["source_url"], "source_date": date.today().isoformat(),
                "public_channel": public_channel(page), "service": p.get("service") or ""}
        company, status = (page.get("title") or dom).split("|")[0].split(" - ")[0].strip()[:120] or dom, "nuevo"
        if use_llm:
            system = ("Analizas la web pública de una empresa para un proveedor de servicios B2B. Describe solo lo que se observa en el texto. "
                      "La observación debe ser verificable y llevar una cita textual. No inventes nombres de personas, cifras, ventas ni problemas internos. "
                      "Lo que supongas va en hipótesis; lo que no se sabe, en desconocidos. Escribe en español.")
            user = (f"Servicio que puedo prestar: {p.get('service') or 'no especificado'}\nFiltros: sector={p.get('sector')}, ubicación={p.get('location')}, "
                    f"tipo de cliente={p.get('client_type')}, señales buscadas={p.get('signals')}, oferta activa={p.get('active_offer')}\n\n"
                    f"<fuente id=\"S1\" url=\"{page['url']}\">\n{page['text'][:5000].replace('</fuente>', '')}\n</fuente>")
            obs, _ = ask_json(ctx, Observation, system=system, user=user, max_tokens=900, ttl_s=7 * 24 * 3600, prompt_version="lead-obs-v1")
            if not obs.fit:
                stats["sin_encaje"] += 1
                ctx.log(f"{dom}: sin encaje con el servicio ({obs.fit_reason[:120]})")
                continue
            verified = quote_in_text(obs.quote, page["text"])
            company = obs.company[:120] or company
            data.update(segment=obs.segment, observation=obs.observation if verified else "",
                        evidence=obs.quote if verified else "",
                        hypotheses="\n".join(obs.hypotheses + ([] if verified else [f"(Sin verificar: la cita no se localizó en la web) {obs.observation}"])),
                        unknowns="\n".join(obs.unknowns))
            status = "investigado" if verified else "nuevo"
        rec = records.create(ctx.space_id, "lead", company, data, status=status, project_id=p.get("project_id"))
        db.execute("UPDATE sources SET note=? WHERE id=?", (f"Lead {rec['id']}", src["id"]))
        created.append(rec["id"])
        stats["creados"] += 1
    note = "" if use_llm else " Sin modelo de texto: los leads se crearon con empresa, web, fuente y canal público; la observación queda pendiente."
    return {"mensaje": f"{stats['creados']} leads creados de {stats['candidatos']} candidatos.{note}", "lead_ids": created, "resumen": stats}


@handler("lead_proposal")
def lead_proposal(ctx) -> dict:
    p = ctx.params
    lead = records.get(p.get("lead_id") or "", ctx.space_id)
    if not lead or lead["kind"] != "lead":
        raise JobError("El lead indicado no existe en este espacio.")
    L = lead["data"]
    service = records.get(p.get("service_id") or "", ctx.space_id)
    service_text = (f"{service['title']}: {service['data'].get('description') or ''}\nEntregables típicos: {service['data'].get('deliverables') or ''}\n"
                    f"Plazo típico: {service['data'].get('timeline') or ''}") if service else (p.get("service") or L.get("service") or "")
    if not service_text.strip():
        raise JobError("Indica el servicio que vas a proponer (en el lead o al lanzar la propuesta).")
    ctx.stage("redaccion", 0.3, "Redactando muestra, oferta y mensaje")
    system = ("Preparas una propuesta B2B honesta en español. Usa solo la observación verificada y los datos del lead; no inventes cifras, resultados, "
              "nombres de personas ni promesas. No incluyas precio: lo define el usuario. La muestra gratuita debe ser pequeña y acotada "
              "(entregable, tiempo máximo, revisiones, límites). El mensaje es breve, respetuoso, menciona la observación y ofrece la muestra; "
              "sin urgencia falsa ni garantías.")
    user = (f"Empresa: {lead['title']}\nWeb: {L.get('website')}\nSegmento: {L.get('segment')}\nObservación verificada: {L.get('observation') or '(ninguna)'}\n"
            f"Evidencia: {L.get('evidence') or '(ninguna)'}\nHipótesis (no afirmarlas como hechos): {L.get('hypotheses') or ''}\n"
            f"Desconocidos: {L.get('unknowns') or ''}\n\nServicio a proponer:\n{service_text}\n\nIndicaciones del usuario: {p.get('notes') or ''}")
    prop, meta = ask_json(ctx, Proposal, system=system, user=user, max_tokens=2000, prompt_version="propuesta-v1")
    price = p.get("price")
    if price in (None, "") and service and service["data"].get("price_from"):
        price = f"desde {service['data']['price_from']} {service['data'].get('currency') or ''}".strip()
    o, s = prop.offer, prop.sample
    sections = [
        {"key": "observacion", "title": "Observación verificable", "type": "facts", "items": [
            {"claim": L.get("observation") or "[pendiente: sin observación verificada]", "kind": "hecho" if L.get("observation") else "desconocido",
             "source_ids": [r["id"] for r in db.query("SELECT id FROM sources WHERE space_id=? AND note=?", (ctx.space_id, f"Lead {lead['id']}"))],
             "evidence": L.get("evidence") or "", "limitations": f"Web consultada el {L.get('source_date')}."}]
            + [{"claim": h, "kind": "hipotesis", "source_ids": [], "evidence": "", "limitations": ""} for h in (L.get("hypotheses") or "").splitlines() if h.strip()]},
        {"key": "muestra", "title": "Muestra gratuita limitada", "type": "list",
         "items": [f"Entregable: {s.deliverable}", f"Tiempo máximo: {s.max_time}", f"Revisiones: {s.revisions}", f"Límites: {s.limits}"]},
        {"key": "oferta", "title": "Oferta pagada", "type": "list",
         "items": [f"Problema: {o.problem}", f"Objetivo: {o.objective}", "Entregables: " + "; ".join(o.deliverables), "Exclusiones: " + "; ".join(o.exclusions),
                   "Insumos necesarios: " + "; ".join(o.inputs_needed), f"Plazo: {o.timeline}", f"Revisiones: {o.revisions}",
                   f"Criterio de aceptación: {o.acceptance}", f"Precio: {price if price not in (None, '') else '[precio por definir]'}"]},
        {"key": "mensaje", "title": "Mensaje (borrador, no enviado)", "type": "text", "body": f"**Asunto:** {prop.message.subject}\n\n{prop.message.body}",
         "note": f"Canal publicado por la empresa: {L.get('public_channel') or 'no encontrado'}. Jarvis no envía mensajes; exporta el borrador."},
    ]
    d = review.create(ctx.space_id, "proposal", f"Propuesta para {lead['title']}", {"summary": f"Redactado con {meta['connection']}. Revisa antes de usar.", "sections": sections,
                      "source_ids": sections[0]["items"][0]["source_ids"], "meta": {"lead_id": lead["id"]}}, author="jarvis", job_id=ctx.id,
                      project_id=lead["project_id"], ref_id=lead["id"])
    records.update(lead["id"], ctx.space_id, {"status": "propuesta_lista", "data": {
        "sample": "\n".join(sections[1]["items"]), "offer": "\n".join(sections[2]["items"]), "next_action": "Revisar y aprobar la propuesta"}})
    return {"mensaje": f"Propuesta para {lead['title']} lista para revisión.", "deliverable_ids": [d["id"]], "lead_id": lead["id"]}
