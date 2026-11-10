"""Jarvis: registro de herramientas tipadas. Funciona con comandos deterministas sin modelo; con modelo, este solo
elige una herramienta permitida y sus argumentos, que se validan antes de ejecutar. Ninguna herramienta realiza acciones externas."""
from __future__ import annotations
import json
import re
from datetime import date

from pydantic import BaseModel, Field, ValidationError

from . import db, jobs, records, review, router
from .handlers.common import norm
from .util import dumps, loads, now_iso

TOOLS: dict[str, dict] = {}


def tool(name: str, description: str, args: type[BaseModel], kind: str):
    """kind: lectura | trabajo | registro. Solo acciones internas y reversibles."""
    def deco(fn):
        TOOLS[name] = {"name": name, "description": description, "args": args, "kind": kind, "fn": fn}
        return fn
    return deco


class NoArgs(BaseModel):
    pass


class OppArgs(BaseModel):
    question: str = Field(min_length=3, max_length=300)
    category: str = ""
    country: str = ""
    language: str = "es"
    max_queries: int = Field(default=4, ge=1, le=8)
    max_pages: int = Field(default=6, ge=1, le=15)


class LeadArgs(BaseModel):
    sector: str = Field(min_length=2, max_length=200)
    location: str = ""
    service: str = ""
    max_candidates: int = Field(default=8, ge=1, le=25)


class ProposalArgs(BaseModel):
    lead_ids: list[str] = Field(default_factory=list, max_length=10)
    service: str = ""


class ContentArgs(BaseModel):
    brand: str = Field(min_length=1, max_length=120)
    objective: str = "confianza"
    product: str = ""
    channel: str = ""
    count: int = Field(default=5, ge=1, le=20)


class JobRef(BaseModel):
    job_id: str = ""


class DelivRef(BaseModel):
    deliverable_id: str = ""


class CaptureArgs(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    as_task: bool = False
    origin: str = "texto"


def _job_reply(job: dict, created: bool) -> dict:
    lead = "Trabajo creado" if created else "Ya había un trabajo activo equivalente; no lo dupliqué"
    return {"reply": f"{lead}: {job['title']} · {job['id']} · estado: {job['status_label']}. Te aviso del progreso en Trabajos.",
            "speak": f"{lead}. Estado: {job['status_label']}.", "job": {"id": job["id"], "status": job["status"], "status_label": job["status_label"], "title": job["title"]}}


@tool("buscar_oportunidades", "Lanza una investigación de oportunidades con búsqueda web y expediente con fuentes.", OppArgs, "trabajo")
def _opp(space_id: str, a: OppArgs) -> dict:
    job, created = jobs.enqueue(space_id, "opportunity_research", f"Oportunidades: {a.question[:80]}", a.model_dump())
    return _job_reply(job, created)


@tool("buscar_leads", "Busca empresas candidatas en fuentes públicas para un sector y ubicación.", LeadArgs, "trabajo")
def _leads(space_id: str, a: LeadArgs) -> dict:
    job, created = jobs.enqueue(space_id, "lead_search", f"Leads: {a.sector[:80]}", a.model_dump())
    return _job_reply(job, created)


@tool("preparar_propuestas", "Prepara propuestas revisables para leads (los indicados o los investigados sin propuesta, máximo 5).", ProposalArgs, "trabajo")
def _proposals(space_id: str, a: ProposalArgs) -> dict:
    leads = [records.get(i, space_id) for i in a.lead_ids] if a.lead_ids else [
        l for l in records.list_records(space_id, "lead") if l["status"] in ("investigado", "nuevo")][:5]
    leads = [l for l in leads if l and l["kind"] == "lead"]
    if not leads:
        return {"reply": "No hay leads pendientes de propuesta en este espacio. Busca leads primero.", "speak": "No hay leads pendientes de propuesta."}
    created = []
    for l in leads:
        job, _ = jobs.enqueue(space_id, "lead_proposal", f"Propuesta: {l['title'][:80]}", {"lead_id": l["id"], "service": a.service})
        created.append({"id": job["id"], "status": job["status"], "status_label": job["status_label"], "title": job["title"]})
    return {"reply": f"{len(created)} trabajo(s) de propuesta en cola: " + ", ".join(j["id"] for j in created) + ". Quedarán en Revisión; no se envía nada.",
            "speak": f"{len(created)} propuestas en preparación.", "jobs": created, "job": created[0]}


@tool("generar_contenido", "Genera un lote de contenido para una marca registrada.", ContentArgs, "trabajo")
def _content(space_id: str, a: ContentArgs) -> dict:
    brands = records.list_records(space_id, "brand")
    match = [b for b in brands if norm(a.brand) in norm(b["title"]) or norm(b["title"]) in norm(a.brand)]
    if len(match) != 1:
        names = ", ".join(b["title"] for b in brands) or "ninguna registrada"
        return {"reply": f"No identifico una única marca «{a.brand}» en este espacio. Marcas disponibles: {names}.", "speak": "No encontré esa marca en este espacio."}
    objective = a.objective if a.objective in ("viralidad", "confianza", "captacion", "ventas") else "confianza"
    job, created = jobs.enqueue(space_id, "content_batch", f"Contenido: {match[0]['title']} · {objective}",
                                {"brand_id": match[0]["id"], "objective": objective, "product": a.product, "channel": a.channel, "count": a.count})
    return _job_reply(job, created)


@tool("cancelar_trabajo", "Cancela un trabajo (el indicado o el último activo).", JobRef, "registro")
def _cancel(space_id: str, a: JobRef) -> dict:
    job = jobs.get(a.job_id) if a.job_id else next(iter(jobs.list_jobs(space_id, "active", 1)), None)
    if not job or job["space_id"] != space_id:
        return {"reply": "No hay ningún trabajo activo que cancelar en este espacio.", "speak": "No hay trabajos activos."}
    job = jobs.request_cancel(job["id"])
    state = "cancelado" if job["status"] == "cancelled" else "con cancelación solicitada; se detendrá en el siguiente punto seguro"
    return {"reply": f"{job['title']} · {job['id']}: {state}.", "speak": f"Trabajo {state.split(';')[0]}.",
            "job": {"id": job["id"], "status": job["status"], "status_label": job["status_label"], "title": job["title"]}}


@tool("estado_trabajos", "Muestra el estado de un trabajo o de los trabajos recientes, con sus entregables.", JobRef, "lectura")
def _status(space_id: str, a: JobRef) -> dict:
    items = [jobs.get(a.job_id)] if a.job_id else jobs.list_jobs(space_id, limit=6)
    items = [j for j in items if j and j["space_id"] == space_id]
    if not items:
        return {"reply": "No hay trabajos en este espacio.", "speak": "No hay trabajos."}
    lines = []
    for j in items:
        dels = (j["result"] or {}).get("deliverable_ids") or []
        lines.append(f"{j['id']} · {j['title']} · {j['status_label']}" + (f" · {j['message']}" if j["message"] and j["status"] != "completed" else "")
                     + (f" · entregables: {', '.join(dels)}" if dels else ""))
    active = sum(1 for j in items if j["status"] in jobs.ACTIVE)
    return {"reply": "\n".join(lines), "speak": f"{len(items)} trabajos recientes, {active} activos.", "jobs": [{"id": j["id"], "status": j["status"], "status_label": j["status_label"], "title": j["title"]} for j in items]}


def pending_summary(space_id: str) -> dict:
    today = date.today().isoformat()
    tasks = [t for t in records.list_records(space_id, "task") if t["status"] != "hecha"]
    overdue = [t for t in tasks if (t["data"].get("due_date") or "9999") < today]
    in_review = review.list_deliverables(space_id, status="en_revision")
    drafts = review.list_deliverables(space_id, status="borrador")
    changes = review.list_deliverables(space_id, status="cambios_solicitados")
    active = jobs.list_jobs(space_id, "active", 50)
    waiting = [j for j in active if j["status"].startswith("waiting")]
    return {"tareas_abiertas": len(tasks), "tareas_vencidas": len(overdue), "por_aprobar": len(in_review), "borradores": len(drafts),
            "con_cambios_solicitados": len(changes), "trabajos_activos": len(active), "trabajos_en_espera": len(waiting),
            "detalle": {"por_aprobar": [{"id": d["id"], "titulo": d["title"], "tipo": d["kind_label"]} for d in in_review[:8]],
                        "en_espera": [{"id": j["id"], "titulo": j["title"], "estado": j["status_label"], "motivo": j["message"]} for j in waiting[:8]],
                        "vencidas": [{"id": t["id"], "titulo": t["title"], "fecha": t["data"].get("due_date")} for t in overdue[:8]]}}


@tool("resumen_pendientes", "Resume lo pendiente: tareas, decisiones por aprobar y trabajos activos o en espera.", NoArgs, "lectura")
def _pending(space_id: str, a: NoArgs) -> dict:
    s = pending_summary(space_id)
    reply = (f"Por aprobar: {s['por_aprobar']} entregable(s) en revisión, {s['borradores']} borrador(es) y {s['con_cambios_solicitados']} con cambios solicitados. "
             f"Tareas abiertas: {s['tareas_abiertas']} ({s['tareas_vencidas']} vencidas). Trabajos activos: {s['trabajos_activos']}, de ellos {s['trabajos_en_espera']} en espera.")
    for w in s["detalle"]["en_espera"]:
        reply += f"\n· En espera {w['id']}: {w['motivo']}"
    return {"reply": reply, "speak": f"{s['por_aprobar']} por aprobar, {s['tareas_abiertas']} tareas abiertas y {s['trabajos_activos']} trabajos activos.", "data": s}


@tool("costos_y_cuotas", "Muestra uso, costos estimados y cuotas configuradas u observadas de las conexiones.", NoArgs, "lectura")
def _costs(space_id: str, a: NoArgs) -> dict:
    u = router.usage_summary()
    total = sum(c["costo_estimado_usd"] or 0 for c in u["por_categoria"])
    lines = [f"Costo estimado este mes: {total:.4f} USD (gasto de pago {'activado' if u['gasto_pago_activado'] else 'desactivado'})."]
    for c in u["por_conexion"]:
        limits = ", ".join(filter(None, [f"{c['rpm_limit']:.0f}/min configurado" if c["rpm_limit"] else "", f"{c['daily_limit']:.0f}/día configurado" if c["daily_limit"] else ""])) or "sin límite configurado"
        seen = "cuota observada en cabeceras del proveedor" if c["confirmed_quota"] else "cuota no confirmada por el proveedor"
        lines.append(f"· {c['name'] or c['connection_id']}: {c['llamadas']} llamadas ({c['en_cache'] or 0} en caché), {c['costo_estimado_usd'] or 0:.4f} USD estimados; {limits}; {seen}.")
    lines.append(u["nota"])
    return {"reply": "\n".join(lines), "speak": f"Costo estimado del mes: {total:.2f} dólares. La factura del proveedor es la referencia.", "data": u}


@tool("fuentes_usadas", "Lista las fuentes de un entregable (o del último expediente) con fecha de consulta y de publicación.", DelivRef, "lectura")
def _sources(space_id: str, a: DelivRef) -> dict:
    d = review.detail(a.deliverable_id, space_id) if a.deliverable_id else None
    if not d:
        last = next(iter(review.list_deliverables(space_id, kind="dossier")), None) or next(iter(review.list_deliverables(space_id)), None)
        d = review.detail(last["id"], space_id) if last else None
    if not d:
        return {"reply": "Todavía no hay entregables con fuentes en este espacio.", "speak": "Aún no hay fuentes registradas."}
    if not d["sources"]:
        return {"reply": f"«{d['title']}» no tiene fuentes registradas.", "speak": "Ese entregable no tiene fuentes registradas."}
    lines = [f"Fuentes de «{d['title']}» ({d['id']}):"]
    for s in d["sources"]:
        lines.append(f"· {s['title']} — {s['url']} — consultada {s['fetched_at']}; publicada {s['published_at'] or 'no disponible'}; estado {s['status']}")
    return {"reply": "\n".join(lines), "speak": f"{len(d['sources'])} fuentes; el detalle está en pantalla.", "deliverables": [d["id"]]}


@tool("capturar", "Guarda una captura rápida o una tarea en el espacio actual.", CaptureArgs, "registro")
def _capture(space_id: str, a: CaptureArgs) -> dict:
    if a.as_task:
        rec = records.create(space_id, "task", a.text[:200], {"notes": a.text if len(a.text) > 200 else ""})
        return {"reply": f"Tarea creada: {rec['title']} ({rec['id']}).", "speak": "Tarea creada.", "record": rec["id"]}
    rec = records.create(space_id, "capture", a.text[:80], {"body": a.text, "origin": a.origin if a.origin in ("texto", "voz") else "texto"})
    return {"reply": f"Captura guardada ({rec['id']}).", "speak": "Anotado.", "record": rec["id"]}


@tool("pausar_agentes", "Pausa todos los agentes: no se inicia ningún trabajo nuevo hasta reanudar.", NoArgs, "registro")
def _pause(space_id: str, a: NoArgs) -> dict:
    db.set_setting("agents_paused", True)
    db.audit("agentes.pausar", "", {}, actor="asistente")
    return {"reply": "Agentes en pausa. No se iniciará ningún trabajo nuevo; los que estén en curso terminan su etapa actual. Di «reanuda los agentes» para continuar.", "speak": "Agentes en pausa."}


@tool("reanudar_agentes", "Reanuda los agentes tras una pausa.", NoArgs, "registro")
def _resume(space_id: str, a: NoArgs) -> dict:
    db.set_setting("agents_paused", False)
    db.audit("agentes.reanudar", "", {}, actor="asistente")
    return {"reply": "Agentes reanudados. La cola vuelve a ejecutarse.", "speak": "Agentes reanudados."}


def tool_specs() -> list[dict]:
    return [{"name": t["name"], "description": t["description"], "kind": t["kind"], "args": t["args"].model_json_schema().get("properties", {})} for t in TOOLS.values()]


HELP = ("Puedo: buscar oportunidades («busca oportunidades en …»), buscar leads («busca leads de … en …»), preparar propuestas, "
        "generar contenido («genera contenido para la marca …»), resumir lo pendiente, mostrar el estado de los trabajos, cancelar un trabajo, "
        "mostrar costos y cuotas, listar las fuentes usadas, pausar o reanudar todos los agentes y anotar tareas o capturas («anota …», «tarea: …»).")

_JOB_ID = re.compile(r"job_[0-9a-f]{12}")
_DELIV_ID = re.compile(r"ent_[0-9a-f]{12}")


def parse_command(text: str) -> tuple[str, dict] | None:
    """Comandos tipados deterministas (sin modelo). Devuelve (herramienta, argumentos) o None."""
    raw = text.strip()
    n = norm(raw)
    job = _JOB_ID.search(raw)
    deliv = _DELIV_ID.search(raw)
    if re.match(r"^(tarea|pendiente)\s*:?\s+", raw, flags=re.I) and n.split()[0] == "tarea":
        return "capturar", {"text": re.sub(r"^\S+\s*:?\s*", "", raw), "as_task": True}
    if m := re.match(r"^(anota|apunta|recuerda|captura)(?:\s+que)?\s*:?\s+(.+)$", raw, flags=re.I | re.S):
        return "capturar", {"text": m.group(2)}
    if re.search(r"\b(pausa|deten|para)\w*\s+(a\s+)?(todos\s+)?(los\s+)?agentes", n):
        return "pausar_agentes", {}
    if re.search(r"\b(reanuda|continua|activa)\w*\s+(a\s+)?(todos\s+)?(los\s+)?agentes", n):
        return "reanudar_agentes", {}
    if re.search(r"\bcancela", n):
        return "cancelar_trabajo", {"job_id": job.group(0) if job else ""}
    if m := re.search(r"busca\w*\s+(?:nuevas\s+)?oportunidades?\s+(?:de negocio\s+)?(?:en|de|sobre|para)?\s*(.+)", raw, flags=re.I):
        return "buscar_oportunidades", {"question": m.group(1).strip(" .")}
    if m := re.search(r"busca\w*\s+(?:leads|empresas|clientes|prospectos)\s+(?:de|del|en el sector|sobre|para)?\s*(.+)", raw, flags=re.I):
        rest = m.group(1).strip(" .")
        sector, _, loc = rest.partition(" en ")
        return "buscar_leads", {"sector": sector.strip(), "location": loc.strip()}
    if re.search(r"prepara\w*\s+(?:las\s+|unas\s+)?propuestas?", n):
        return "preparar_propuestas", {"lead_ids": re.findall(r"lea_[0-9a-f]{12}", raw)}
    if m := re.search(r"genera\w*\s+.*?contenido.*?\s+para\s+(?:la\s+marca\s+|esta\s+marca\s+)?(.+)", raw, flags=re.I):
        args = {"brand": m.group(1).strip(" .")}
        for obj in ("viralidad", "confianza", "captacion", "ventas"):
            if obj in n:
                args["objective"] = obj
        return "generar_contenido", args
    if "fuentes" in n:
        return "fuentes_usadas", {"deliverable_id": deliv.group(0) if deliv else ""}
    if re.search(r"\b(costos?|costes?|cuotas?|gasto|consumo)\b", n):
        return "costos_y_cuotas", {}
    if re.search(r"\b(resume|resumen|pendiente|pendientes|por aprobar|aprobaciones|decisiones)\b", n):
        return "resumen_pendientes", {}
    if job or re.search(r"\b(estado|trabajos?|progreso)\b", n):
        return "estado_trabajos", {"job_id": job.group(0) if job else ""}
    return None


def _run(space_id: str, name: str, args: dict) -> dict:
    spec = TOOLS[name]
    try:
        parsed = spec["args"].model_validate(args)
    except ValidationError as exc:
        e = exc.errors()[0]
        return {"reply": f"No pude ejecutar «{name}»: el argumento «{'.'.join(str(x) for x in e['loc'])}» no es válido ({e['msg']}).", "speak": "Faltan datos para esa orden.", "error": True}
    out = spec["fn"](space_id, parsed)
    out["tool"] = name
    return out


def _log(space_id: str, role: str, content: str, data: dict | None = None) -> None:
    db.execute("INSERT INTO messages(space_id,role,content,data,created_at) VALUES(?,?,?,?,?)", (space_id, role, content, dumps(data or {}), now_iso()))


def history(space_id: str, limit: int = 40) -> list[dict]:
    rows = db.query("SELECT * FROM messages WHERE space_id=? ORDER BY id DESC LIMIT ?", (space_id, limit))
    for r in rows:
        r["data"] = loads(r["data"], {})
    return list(reversed(rows))


def clear_history(space_id: str) -> None:
    db.execute("DELETE FROM messages WHERE space_id=?", (space_id,))


def handle(space_id: str, text: str, origin: str = "texto") -> dict:
    text = (text or "").strip()[:2000]
    if not text:
        return {"reply": "No recibí ninguna orden.", "speak": "No recibí ninguna orden.", "mode": "ninguno"}
    _log(space_id, "usuario", text, {"origen": origin})
    n = norm(text)
    if n in ("ayuda", "help") or "que puedes hacer" in n:
        out = {"reply": HELP, "speak": "Te muestro en pantalla lo que puedo hacer.", "mode": "comando"}
    elif cmd := parse_command(text):
        if cmd[0] == "capturar":
            cmd[1]["origin"] = origin
        out = _run(space_id, cmd[0], cmd[1])
        out["mode"] = "comando"
    else:
        out = _via_model(space_id, text)
    _log(space_id, "jarvis", out["reply"], {k: v for k, v in out.items() if k not in ("reply", "data")})
    return out


def _via_model(space_id: str, text: str) -> dict:
    """El modelo solo propone {tool, args}; se valida y ejecuta aquí. Su texto libre nunca se convierte en acción."""
    specs = json.dumps([{k: s[k] for k in ("name", "description", "args")} for s in tool_specs()], ensure_ascii=False)
    system = ("Eres Jarvis, coordinador de un sistema local de trabajo. Tono sereno, preciso y breve, con humor discreto. "
              "Decide si la petición del usuario corresponde a UNA de las herramientas disponibles. Responde solo con JSON: "
              "{\"tool\": nombre o null, \"args\": {…}, \"reply\": texto breve si no hay herramienta}. "
              "No afirmes haber hecho nada: las acciones las ejecuta el sistema. No inventes datos del usuario ni resultados. "
              f"Herramientas: {specs}")
    try:
        raw, meta = router.llm(router.Ctx(space_id=space_id, limits={"max_calls": 2, "max_tokens": 6000, "max_cost_usd": 0.05}),
                               system=system, user=text, json_mode=True, max_tokens=400)
    except router.RouterError as exc:
        return {"reply": f"No reconocí la orden como comando y no hay un modelo de texto disponible para interpretarla ({exc.message}) {HELP}",
                "speak": "No reconocí la orden. Te muestro los comandos disponibles.", "mode": "sin_modelo"}
    try:
        from .handlers.common import _extract_json
        choice = _extract_json(raw)
        name, args = choice.get("tool"), choice.get("args") or {}
        if not isinstance(args, dict):
            raise ValueError("args")
    except (ValueError, AttributeError):
        return {"reply": "El modelo respondió con un formato no válido y descarté su respuesta. Prueba con un comando directo. " + HELP,
                "speak": "No pude interpretar la orden.", "mode": "modelo", "error": True}
    if name in TOOLS:
        out = _run(space_id, name, args)
        out.update(mode="modelo", model=meta["connection"])
        return out
    reply = str(choice.get("reply") or "").strip()[:1200] or "No tengo una herramienta para eso. " + HELP
    return {"reply": reply, "speak": reply[:240], "mode": "modelo", "model": meta["connection"]}
