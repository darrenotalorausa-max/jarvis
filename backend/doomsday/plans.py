"""Planes de acciones externas de Doomsday: varios pasos encadenados contra una app conectada, con UNA aprobación ligada al plan exacto.

Un plan se muestra completo antes de aprobarse (método, ruta y cuerpo de cada paso). La aprobación va ligada al hash de sus pasos y variables,
es de un solo uso y puede fijar una hora futura («programar»). Si se edita algo, el hash cambia y la aprobación deja de valer.
Nada de este archivo se ha validado con cuentas reales: las rutas siguen la documentación pública de cada plataforma.
"""
from __future__ import annotations
import hashlib
import json
import re
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Body, Request

from jarvis import connections, connectors, db, jobs, records, review, router as jrouter
from jarvis.connectors import A
from jarvis.jobs import ApprovalRequired, JobError
from jarvis.providers import base
from jarvis.providers.base import ProviderError
from jarvis.util import canonical_json, iso_in, now_iso, sha256_text
from jarvis.worker import handler

from . import content, engine, tools
from .integrations import _conn, _read, _space

router = APIRouter(prefix="/api/dd")

PRESETS = {
    "redes_meta": {"label": "Instagram y página de Facebook (publicar)", "base_url": "https://graph.facebook.com/v26.0", "auth": {"type": "bearer"},
                   "credential": "Token de página o de usuario del sistema con instagram_content_publish y pages_manage_posts.", "actions": []},
    "linkedin": {"label": "LinkedIn (publicar)", "base_url": "https://api.linkedin.com", "auth": {"type": "bearer"}, "headers": {"LinkedIn-Version": "202601", "X-Restli-Protocol-Version": "2.0.0"},
                 "credential": "Token OAuth con w_member_social.", "actions": []},
    "x": {"label": "X (publicar)", "base_url": "https://api.x.com", "auth": {"type": "bearer"}, "credential": "Token de usuario OAuth 2.0 con tweet.write.", "actions": []},
    "discord": {"label": "Discord (bot de tu servidor)", "base_url": "https://discord.com/api/v10", "auth": {"type": "header", "name": "Authorization"},
                "credential": "Escribe «Bot » seguido del token de tu bot (Discord Developer Portal → Bot). Invítalo a tu servidor con permisos de gestionar canales, roles y enviar mensajes.",
                "actions": [A("dd_miembros", "Miembros del servidor", "GET", "/guilds/{servidor}/members", query={"limit": "1000"})]},
    "oura": {"label": "Oura (sueño)", "base_url": "https://api.ouraring.com", "auth": {"type": "bearer"}, "credential": "Token de acceso personal de Oura.",
             "actions": [A("dd_sueno", "Sueño por día", "GET", "/v2/usercollection/sleep", query={"start_date": "{desde}", "end_date": "{hasta}"})]},
}
GMAIL_ACTIONS = [A("dd_lista", "Mensajes recientes", "GET", "/users/me/messages", query={"q": "{consulta}", "maxResults": "{limite}"}),
                 A("dd_mensaje", "Leer un mensaje", "GET", "/users/me/messages/{mensaje_id}", query={"format": "full"})]


def register() -> None:
    for k, v in PRESETS.items():
        connectors.PRESETS.setdefault(k, v)
    have = {a["id"] for a in connectors.PRESETS["gmail"]["actions"]}
    connectors.PRESETS["gmail"]["actions"] += [a for a in GMAIL_ACTIONS if a["id"] not in have]
    from jarvis import access
    # Única ruta de Doomsday que alcanza el rol «cliente»: aceptar un documento de su propio espacio.
    if ("POST", r"/api/dd/sign") not in access._CLIENT:
        access._CLIENT.append(("POST", r"/api/dd/sign"))


# ---------- Motor de planes

def P(label: str, method: str, path: str, body=None, save: dict | None = None, literal: bool = False, wait: dict | None = None) -> dict:
    return {"label": label, "method": method, "path": path, "body": body, "save": save or {}, "literal": literal, "wait": wait}


def plan_hash(conn: dict, p: dict) -> str:
    return sha256_text(canonical_json([conn["id"], conn["base_url"], p.get("steps"), p.get("variables"), p.get("after")]))


def create_plan(conn: dict, space_id: str, module: str, title: str, steps: list[dict], variables: dict | None = None, after: list[dict] | None = None) -> dict:
    root = conn["base_url"].rstrip("/")
    for s in steps:
        if s["method"] not in ("POST", "PUT", "PATCH", "DELETE", "GET") or not s["path"].startswith("/") or "://" in s["path"] or ".." in s["path"]:
            raise ValueError("Paso de plan no válido.")
    params = {"module": module, "connection_id": conn["id"], "steps": steps, "variables": variables or {}, "after": after or []}
    job, created = jobs.enqueue(space_id, "dd_plan", title[:200], params, max_attempts=1)
    return {"job": job, "created": created, "pasos": [{"paso": s["label"], "metodo": s["method"], "url": root + s["path"], "cuerpo": s["body"]} for s in steps]}


def _send(conn: dict, step: dict, variables: dict) -> dict:
    action = {"id": "paso", "label": step["label"], "method": step["method"], "path": step["path"], "query": {}, "body": None}
    req = connectors.build(conn, action, variables)
    body = step["body"] if step.get("literal") else connectors._fill(step["body"], variables) if step["body"] is not None else None
    headers, params = {"Accept": "application/json", **(conn["options"].get("headers") or {})}, {}
    connectors._auth(conn, headers, params)
    with base.client(conn.get("timeout_s") or 30) as cli:
        resp = base.send(cli, step["method"], req["url"], f"{conn['name']} · {step['label']}", params=params, headers=headers, **({"json": body} if body is not None else {}))
    try:
        return resp.json() if resp.content else {}
    except ValueError:
        return {}


def _dig(data, path: str):
    for k in path.split("."):
        data = data.get(k) if isinstance(data, dict) else None
    return data


@handler("dd_plan")
def dd_plan(ctx):
    p = ctx.params
    conn = connections.get(p.get("connection_id") or "")
    if not conn or conn["provider"] != "api" or not conn["enabled"] or not conn["terms_accepted"]:
        raise JobError("La conexión no existe o no está habilitada.")
    conn["options"] = connectors.validate_options(conn["options"])
    key = f"dd_plan_approval:{ctx.id}"
    approval = db.get_setting(key)
    if not approval or approval.get("hash") != plan_hash(conn, p) or approval.get("expires_at", "") < now_iso():
        raise ApprovalRequired("Plan pendiente de tu aprobación: revisa cada paso en el panel del módulo y apruébalo para ejecutarlo.")
    db.execute("DELETE FROM settings WHERE key=?", (key,))  # de un solo uso
    variables, hechos = dict(p.get("variables") or {}), []
    for i, step in enumerate(p["steps"], 1):
        ctx.stage("plan", i / (len(p["steps"]) + 1), f"Paso {i} de {len(p['steps'])}: {step['label']}")
        try:
            if step.get("wait"):
                w = step["wait"]
                for _ in range(int(w.get("tries") or 20)):
                    if str(_dig(_send(conn, {**step, "method": "GET", "body": None}, variables), w["field"])) == str(w["value"]):
                        break
                    ctx.check_cancel()
                    jrouter.SLEEP(float(w.get("seconds") or 6))
                else:
                    raise ProviderError("timeout", f"{step['label']}: la plataforma no terminó de procesar a tiempo.")
            else:
                data = _send(conn, step, variables)
                for var, path in (step.get("save") or {}).items():
                    val = _dig(data, path)
                    if val in (None, ""):
                        raise ProviderError("response", f"{step['label']}: la respuesta no trajo «{path}».")
                    variables[var] = str(val)
        except ProviderError as exc:
            db.audit("dd_plan.fallo", ctx.id, {"paso": i, "hechos": hechos, "error": exc.message[:300]}, actor=approval.get("user") or "usuario")
            raise JobError(f"Falló el paso {i} («{step['label']}»): {exc.message} " + (f"Ya se ejecutaron: {', '.join(hechos)}. Revísalos en la plataforma." if hechos else "No se ejecutó ningún paso."))
        hechos.append(step["label"])
    for a in p.get("after") or []:
        rec = records.get(a["record_id"], ctx.space_id)
        if rec:
            records.update(rec["id"], ctx.space_id, {k: v for k, v in a.items() if k in ("status", "data")})
    db.audit("dd_plan.ejecutado", conn["id"], {"modulo": p.get("module"), "pasos": hechos, "aprobado_por": approval.get("user")}, actor=approval.get("user") or "usuario")
    return {"mensaje": f"Plan ejecutado: {len(hechos)} pasos.", "pasos": hechos, "ids": {k: v for k, v in variables.items() if k not in (p.get("variables") or {})}}


@router.get("/plans")
def plans(module: str = ""):
    out = []
    for j in db.query("SELECT id FROM jobs WHERE type='dd_plan' AND status IN ('waiting_approval','pending') ORDER BY created_at DESC LIMIT 60"):
        job = jobs.get(j["id"])
        if module and job["params"].get("module") != module:
            continue
        conn = connections.get(job["params"]["connection_id"])
        root = (conn or {}).get("base_url", "").rstrip("/")
        out.append({"id": job["id"], "modulo": job["params"].get("module"), "titulo": job["title"], "estado": job["status"], "programado": job.get("resume_at"), "conexion": (conn or {}).get("name"), "espacio": job["space_id"],
                    "pasos": [{"paso": s["label"], "metodo": s["method"], "url": root + s["path"], "cuerpo": s["body"]} for s in job["params"]["steps"]], "variables": job["params"]["variables"]})
    return out


@router.post("/plans/{job_id}/approve")
def plan_approve(job_id: str, body: dict = Body(default={})):
    job = jobs.get(job_id)
    if not job or job["type"] != "dd_plan" or job["status"] != "waiting_approval":
        raise ValueError("Este plan no está esperando aprobación.")
    conn = connections.get(job["params"]["connection_id"])
    if not conn:
        raise KeyError(job_id)
    conn["options"] = connectors.validate_options(conn["options"])
    at = None
    if body.get("at"):
        try:
            at = datetime.fromisoformat(str(body["at"]))
            at = (at if at.tzinfo else at.astimezone()).astimezone(timezone.utc)
        except ValueError:
            raise ValueError("Fecha y hora no válidas.")
        if at < datetime.now(timezone.utc) or at > datetime.now(timezone.utc) + timedelta(days=60):
            raise ValueError("La programación debe estar entre ahora y 60 días.")
    user = db.get_setting("user_name", "usuario") or "usuario"
    expires = (at + timedelta(hours=6)).isoformat(timespec="seconds") if at else iso_in(3600)
    db.set_setting(f"dd_plan_approval:{job_id}", {"hash": plan_hash(conn, job["params"]), "user": user, "expires_at": expires})
    db.audit("dd_plan.aprobar", job_id, {"conexion": conn["id"], "programado": at.isoformat() if at else None}, actor=user)
    out = jobs.retry(job_id)
    if at:
        db.execute("UPDATE jobs SET resume_at=?, message=? WHERE id=?", (at.isoformat(timespec="seconds"), f"Aprobado y programado para {at.isoformat(timespec='minutes')} UTC", job_id))
        out = jobs.get(job_id)
    return out


# ---------- C05 · publicar en redes

@router.post("/social/publish")
def social_publish(body: dict = Body(...)):
    conn, red = _conn(body.get("connection_id")), body.get("red")
    sid = _space("C05", body.get("space"))
    rec = records.get(str(body.get("record_id") or ""), sid)
    texto = str(body.get("texto") or (rec["data"].get("texto") if rec else "") or "").strip()
    media, cuenta = str(body.get("media_url") or "").strip(), str(body.get("cuenta") or "").strip()
    if not texto:
        raise ValueError("Escribe el texto de la publicación o elige una pieza con texto.")
    if media and not re.match(r"^https://\S+$", media):
        raise ValueError("El archivo debe ser una URL https pública (la red lo descarga desde ahí).")
    v = {"texto": texto[:2200], "cuenta": cuenta, **({"media": media} if media else {})}
    video = media.lower().split("?")[0].endswith((".mp4", ".mov"))
    if red == "instagram":
        if not media or not cuenta:
            raise ValueError("Instagram necesita el ID de la cuenta profesional y una imagen o video por URL pública.")
        cont = {"caption": "{texto}", **({"video_url": "{media}", "media_type": "REELS"} if video else {"image_url": "{media}"})}
        steps = [P("Crear el contenedor", "POST", "/{cuenta}/media", cont, {"creacion": "id"})]
        if video:
            steps.append(P("Esperar a que Instagram procese el video", "GET", "/{creacion}?fields=status_code", wait={"field": "status_code", "value": "FINISHED", "tries": 30, "seconds": 8}))
        steps.append(P("Publicar", "POST", "/{cuenta}/media_publish", {"creation_id": "{creacion}"}, {"publicacion": "id"}))
    elif red == "facebook":
        if not cuenta:
            raise ValueError("Indica el ID de la página.")
        steps = [P("Publicar en la página", "POST", "/{cuenta}/photos", {"url": "{media}", "caption": "{texto}"}, {"publicacion": "id"}) if media and not video
                 else P("Publicar en la página", "POST", "/{cuenta}/feed", {"message": "{texto}", **({"link": "{media}"} if media else {})}, {"publicacion": "id"})]
    elif red == "linkedin":
        if not cuenta.startswith("urn:li:"):
            raise ValueError("Indica tu URN de autor de LinkedIn (urn:li:person:… u organization).")
        steps = [P("Publicar", "POST", "/rest/posts", {"author": "{cuenta}", "commentary": "{texto}", "visibility": "PUBLIC", "lifecycleState": "PUBLISHED", "isReshareDisabledByAuthor": False,
                                                       "distribution": {"feedDistribution": "MAIN_FEED", "targetEntities": [], "thirdPartyDistributionChannels": []}})]
    elif red == "x":
        v["texto"] = texto[:280]
        steps = [P("Publicar", "POST", "/2/tweets", {"text": "{texto}"}, {"publicacion": "data.id"})]
    else:
        raise ValueError("Red no soportada. Disponibles: instagram, facebook, linkedin, x. TikTok y YouTube exigen subir el archivo y no se publican desde aquí.")
    after = [{"record_id": rec["id"], "status": "publicado", "data": {"fecha": date.today().isoformat()}}] if rec and rec["kind"] == "dd_pieza" else []
    return create_plan(conn, sid, "C05", f"Publicar en {red}: {texto[:50]}", steps, v, after)


# ---------- M02 · lanzar anuncios en Meta (todo se crea EN PAUSA)

@router.post("/ads/launch")
def ads_launch(body: dict = Body(...)):
    conn, sid = _conn(body.get("connection_id")), _space("M02", body.get("space"))
    cuenta, pagina, pixel = (str(body.get(k) or "").strip() for k in ("cuenta", "pagina_id", "pixel_id"))
    cuenta = cuenta if cuenta.startswith("act_") else f"act_{cuenta}" if cuenta else ""
    try:
        presupuesto = int(round(float(body.get("presupuesto_diario")) * (1 if body.get("moneda_sin_centavos") else 100)))
    except (TypeError, ValueError):
        raise ValueError("Indica el presupuesto diario.")
    if not cuenta or not pagina or not pixel or not re.match(r"^https://\S+$", str(body.get("destino") or "")) or presupuesto <= 0:
        raise ValueError("Faltan datos: cuenta publicitaria, página, píxel, URL de destino https y presupuesto diario.")
    crea = [c for c in (records.get(i, sid) for i in (body.get("creativos") or [])[:30]) if c and c["kind"] == "dd_creativo" and c["status"] == "aprobado"]
    if not crea:
        raise ValueError("Elige creativos en estado «aprobado».")
    faltan = [c["title"] for c in crea if not re.match(r"^https://\S+$", str(c["data"].get("imagen_url") or ""))]
    if faltan:
        raise ValueError("Estos creativos no tienen «URL de la imagen» (https pública): " + ", ".join(faltan[:6]) + ". Los anuncios de video se suben desde el Administrador de anuncios.")
    hall = [f"{c['title']}: {h[1]}" for c in crea for h in tools.scan_cumplimiento(f"{c['data'].get('hook') or ''} {c['data'].get('guion') or ''}") if h[0] == "alta"]
    if hall:
        raise ValueError("Cumplimiento: corrige antes de lanzar → " + "; ".join(hall[:5]))
    producto, hoy = str(body.get("producto") or crea[0]["data"].get("producto") or "producto"), date.today().strftime("%y%m%d")
    pais = str(body.get("pais") or "CO").upper()[:2]
    nombre = f"{hoy}_{re.sub(r'[^A-Za-z0-9]+', '', producto)[:20]}_{pais}"
    steps = [P("Crear campaña (en pausa)", "POST", "/{cuenta}/campaigns", {"name": nombre, "objective": "OUTCOME_SALES", "status": "PAUSED", "special_ad_categories": []}, {"campana": "id"}),
             P("Crear conjunto de anuncios (en pausa)", "POST", "/{cuenta}/adsets",
               {"name": f"{nombre}_abierto", "campaign_id": "{campana}", "daily_budget": str(presupuesto), "billing_event": "IMPRESSIONS", "optimization_goal": "OFFSITE_CONVERSIONS",
                "bid_strategy": "LOWEST_COST_WITHOUT_CAP", "promoted_object": {"pixel_id": pixel, "custom_event_type": "PURCHASE"}, "targeting": {"geo_locations": {"countries": [pais]}}, "status": "PAUSED"},
               {"conjunto": "id"})]
    after = []
    for i, c in enumerate(crea, 1):
        d = c["data"]
        link = f"{body['destino']}{'&' if '?' in body['destino'] else '?'}utm_source=meta&utm_campaign={nombre}&utm_content={re.sub(r'[^A-Za-z0-9_]+', '-', c['title'])}"
        steps.append(P(f"Crear creativo {c['title']}", "POST", "/{cuenta}/adcreatives",
                       {"name": c["title"], "object_story_spec": {"page_id": pagina, "link_data": {"link": link, "message": (d.get("guion") or d.get("hook") or "")[:1200], "name": (d.get("hook") or c["title"])[:80],
                                                                                                    "picture": d["imagen_url"], "call_to_action": {"type": "SHOP_NOW"}}}}, {f"creativo{i}": "id"}))
        steps.append(P(f"Crear anuncio {c['title']} (en pausa)", "POST", "/{cuenta}/ads", {"name": c["title"], "adset_id": "{conjunto}", "creative": {"creative_id": "{creativo" + str(i) + "}"}, "status": "PAUSED"}))
        after.append({"record_id": c["id"], "status": "publicado", "data": {"plataforma": "meta"}})
    return create_plan(conn, sid, "M02", f"Lanzar en Meta: {nombre} ({len(crea)} anuncios, en pausa)", steps, {"cuenta": cuenta}, after)


# ---------- M08 · eventos de servidor: compras ENTREGADAS hacia Meta (API de conversiones)

def phone_hash(raw: str, pais: str = "57") -> str | None:
    """Solo se guarda el hash SHA-256 del teléfono normalizado (como pide la API de conversiones). El número nunca se almacena."""
    d = re.sub(r"\D", "", str(raw or ""))
    if len(d) < 8:
        return None
    if len(d) <= 10:
        d = pais + d
    return hashlib.sha256(d.encode()).hexdigest()


@router.post("/capi/send")
def capi_send(body: dict = Body(...)):
    conn, sid = _conn(body.get("connection_id")), _space("M08", body.get("space"))
    pixel = re.sub(r"\D", "", str(body.get("pixel_id") or ""))
    if not pixel:
        raise ValueError("Indica el ID del píxel.")
    moneda = str(body.get("moneda") or "COP").upper()[:3]
    pend = [o for o in records.list_records(sid, "dd_pedido", status="entregado", limit=20000) if o["data"].get("tel_hash") and not o["data"].get("capi_enviado") and o["data"].get("fecha")]
    limite = (date.today() - timedelta(days=7)).isoformat()
    recientes = [o for o in pend if o["data"]["fecha"] >= limite][:200]
    if not recientes:
        raise ValueError(f"No hay compras entregadas de los últimos 7 días con teléfono en hash y sin enviar. Pendientes más antiguas: {len(pend)} (la plataforma solo acepta eventos de hasta 7 días). "
                         "El hash del teléfono se crea al importar la exportación logística con su columna de teléfono.")
    eventos = [{"event_name": "Purchase", "event_time": int(datetime.fromisoformat(o["data"]["fecha"] + "T12:00:00+00:00").timestamp()), "event_id": str(o["data"].get("ref") or o["id"]),
                "action_source": "system_generated", "user_data": {"ph": [o["data"]["tel_hash"]]}, "custom_data": {"currency": moneda, "value": float(o["data"].get("precio") or 0),
                                                                                                                  "content_name": o["data"].get("producto") or ""}} for o in recientes]
    after = [{"record_id": o["id"], "data": {"capi_enviado": True}} for o in recientes]
    return {**create_plan(conn, sid, "M08", f"Enviar {len(eventos)} compras entregadas a Meta (píxel {pixel})", [P("Enviar eventos de compra", "POST", f"/{pixel}/events", {"data": eventos}, literal=True)], {}, after),
            "eventos": len(eventos), "valor": sum(e["custom_data"]["value"] for e in eventos)}


# ---------- R08 · Discord: aplicar la estructura y dar la bienvenida

@router.post("/discord/apply")
def discord_apply(body: dict = Body(...)):
    conn, sid = _conn(body.get("connection_id")), _space("R08", body.get("space"))
    serv, canal = re.sub(r"\D", "", str(body.get("servidor") or "")), re.sub(r"\D", "", str(body.get("canal_mensajes") or ""))
    if not serv:
        raise ValueError("Indica el ID del servidor.")
    orden = {"canal": 0, "rol": 1}
    items = sorted(records.list_records(sid, "dd_comunidad", status="borrador", limit=200), key=lambda c: (orden.get(c["data"].get("tipo"), 2), c["created_at"]))
    steps, after = [], []
    for c in items:
        t, nombre = c["data"].get("tipo"), c["title"][:90]
        if t == "rol":
            steps.append(P(f"Crear rol «{nombre}»", "POST", f"/guilds/{serv}/roles", {"name": nombre, "mentionable": True}, literal=True))
        elif t == "canal":
            steps.append(P(f"Crear canal «{nombre}»", "POST", f"/guilds/{serv}/channels", {"name": re.sub(r"[^a-z0-9áéíóúñ]+", "-", nombre.lower()).strip("-")[:90], "type": 0, "topic": (c["data"].get("contenido") or "")[:900]}, literal=True))
        elif t in ("bienvenida", "regla", "recurso") and canal and c["data"].get("contenido"):
            steps.append(P(f"Publicar «{nombre}»", "POST", f"/channels/{canal}/messages", {"content": f"**{nombre}**\n{c['data']['contenido']}"[:1900]}, literal=True))
        else:
            continue
        after.append({"record_id": c["id"], "status": "activo"})
    if not steps:
        raise ValueError("No hay elementos en borrador que aplicar (o falta el ID del canal para los mensajes). Crea canales, roles, reglas y bienvenida en «Datos».")
    return create_plan(conn, sid, "R08", f"Aplicar la estructura al servidor de Discord ({len(steps)} cambios)", steps[:40], {}, after[:40])


@router.post("/discord/welcome")
def discord_welcome(body: dict = Body(...)):
    conn, sid = _conn(body.get("connection_id")), _space("R08", body.get("space"))
    serv, canal = re.sub(r"\D", "", str(body.get("servidor") or "")), re.sub(r"\D", "", str(body.get("canal_mensajes") or ""))
    if not serv or not canal:
        raise ValueError("Indica el ID del servidor y el del canal de bienvenida.")
    data = _read(conn, PRESETS["discord"]["actions"][0], {"servidor": serv})
    miembros = [m for m in (data if isinstance(data, list) else []) if not (m.get("user") or {}).get("bot")]
    key = f"dd_discord_vistos:{serv}"
    vistos = set(db.get_setting(key, []) or [])
    nuevos = [m for m in miembros if m["user"]["id"] not in vistos]
    primera = not vistos
    db.set_setting(key, sorted({m["user"]["id"] for m in miembros}))
    if primera:
        return {"nuevos": 0, "nota": f"Primera lectura: {len(miembros)} miembros registrados. A partir de ahora se detectan los que entren."}
    if not nuevos:
        return {"nuevos": 0, "nota": "No hay miembros nuevos desde la última revisión."}
    bien = next((c for c in records.list_records(sid, "dd_comunidad", limit=200) if c["data"].get("tipo") == "bienvenida" and c["data"].get("contenido")), None)
    texto = (bien["data"]["contenido"] if bien else "¡Bienvenido! Preséntate y cuéntanos qué te trae por aquí.")[:1500]
    steps = [P(f"Dar la bienvenida a {m['user'].get('global_name') or m['user'].get('username')}", "POST", f"/channels/{canal}/messages", {"content": f"<@{m['user']['id']}> {texto}"}, literal=True) for m in nuevos[:25]]
    return {**create_plan(conn, sid, "R08", f"Bienvenida a {len(steps)} miembros nuevos", steps), "nuevos": len(nuevos)}


# ---------- S01 · subir las secciones del tema a una tienda

@router.post("/theme/upload")
def theme_upload(body: dict = Body(...)):
    conn, sid = _conn(body.get("connection_id")), _space("S01", body.get("space"))
    theme = re.sub(r"\D", "", str(body.get("tema_id") or ""))
    keys = [k for k in (body.get("secciones") or list(content.SECTIONS)) if k in content.SECTIONS]
    if not theme or not keys:
        raise ValueError("Indica el ID del tema (usa un duplicado, no el publicado) y al menos una sección.")
    steps = [P(f"Subir sections/{k}.liquid", "PUT", f"/themes/{theme}/assets.json", {"asset": {"key": f"sections/{k}.liquid", "value": content.SECTIONS[k]["liquid"]}}, literal=True) for k in keys]
    return create_plan(conn, sid, "S01", f"Subir {len(keys)} secciones al tema {theme}", steps)


# ---------- Lecturas: Gmail (P03, V05) y Oura (H02)

def _header(msg: dict, name: str) -> str:
    return next((h.get("value") or "" for h in (msg.get("payload") or {}).get("headers") or [] if (h.get("name") or "").lower() == name), "")


@router.post("/sync/gmail")
def sync_gmail(body: dict = Body(...)):
    conn = _conn(body.get("connection_id"))
    sid = _space("V05" if body.get("module") == "V05" else "P03", body.get("space"))
    lista = _read(conn, GMAIL_ACTIONS[0], {"consulta": str(body.get("consulta") or "is:unread newer_than:3d -category:promotions"), "limite": "25"})
    known = {m["data"].get("ref") for m in records.list_records(sid, "dd_mensaje", limit=20000)}
    nuevos = 0
    for item in (lista.get("messages") or [])[:25]:
        if item.get("id") in known:
            continue
        msg = _read(conn, GMAIL_ACTIONS[1], {"mensaje_id": item["id"]})
        fecha = datetime.fromtimestamp(int(msg.get("internalDate") or 0) / 1000, timezone.utc).date().isoformat() if msg.get("internalDate") else None
        records.create(sid, "dd_mensaje", (_header(msg, "subject") or "(sin asunto)")[:200], {"canal": "correo", "remitente": _header(msg, "from")[:200], "fecha": fecha,
                                                                                          "texto": (msg.get("snippet") or "")[:2000], "ref": item["id"]})
        nuevos += 1
    db.audit("dd_sync_gmail", conn["id"], {"nuevos": nuevos})
    return {"leidos": len(lista.get("messages") or []), "nuevos": nuevos, "nota": "Entran el remitente, el asunto y el extracto de cada correo. Usa «Clasificar la bandeja» para ordenarlos."}


@router.post("/sync/oura")
def sync_oura(body: dict = Body(...)):
    conn, sid = _conn(body.get("connection_id")), _space("H02", body.get("space"))
    desde = (date.today() - timedelta(days=max(1, min(60, int(body.get("dias") or 14))))).isoformat()
    res = _read(conn, PRESETS["oura"]["actions"][0], {"desde": desde, "hasta": date.today().isoformat()})
    known = {s["data"].get("fecha") for s in records.list_records(sid, "dd_sueno", limit=5000)}
    por_dia: dict[str, dict] = {}
    for s in res.get("data") or []:
        if s.get("day") and (s.get("type") in (None, "long_sleep")):
            prev = por_dia.get(s["day"])
            if not prev or (s.get("total_sleep_duration") or 0) > (prev.get("total_sleep_duration") or 0):
                por_dia[s["day"]] = s
    nuevos = 0
    for dia, s in por_dia.items():
        if dia not in known and s.get("total_sleep_duration"):
            records.create(sid, "dd_sueno", dia, {"fecha": dia, "horas": round(s["total_sleep_duration"] / 3600, 2), "calidad": round((s.get("efficiency") or 0) / 10, 1) or None, "notas": "Oura"})
            nuevos += 1
    return {"dias": len(por_dia), "nuevos": nuevos}


# ---------- V08 · aceptación electrónica simple por el cliente

@router.post("/sign")
def sign(request: Request, body: dict = Body(...)):
    """El cliente acepta un documento APROBADO de su propio espacio. Queda constancia de quién, cuándo, desde dónde y de la huella exacta del texto.
    Es una aceptación electrónica simple, no una firma certificada."""
    sid, nombre = str(body.get("space") or ""), str(body.get("nombre") or "").strip()
    d = review.detail(str(body.get("deliverable_id") or ""), sid)
    if not d or d["kind"] != "dd" or (d["version"]["content"].get("meta") or {}).get("modulo") != "V08":
        raise KeyError("documento")
    if d["status"] != "aprobado":
        raise ValueError("Este documento aún no está listo para aceptarse.")
    if len(nombre) < 5 or body.get("acepto") is not True:
        raise ValueError("Escribe tu nombre completo y marca que aceptas el documento.")
    huella = d["version"]["content_hash"]
    if any(f["data"].get("huella") == huella for f in records.list_records(sid, "dd_firma", limit=2000)):
        raise ValueError("Esta versión del documento ya fue aceptada.")
    user = getattr(request.state, "user", None) or {"username": "propietario"}
    rec = records.create(sid, "dd_firma", f"{nombre} · {d['title']}"[:290], {"entregable": d["id"], "version": d["version"]["version"], "huella": huella, "nombre": nombre, "usuario": user["username"],
                                                                         "fecha": now_iso(), "ip": request.client.host if request.client else ""})
    review.comment(d["id"], sid, f"Aceptado electrónicamente por {nombre} (usuario {user['username']}). Versión {d['version']['version']}, huella {huella[:16]}…", author=user["username"])
    for c in records.list_records(sid, "dd_contrato", limit=500):
        if c["status"] in ("borrador", "enviado") and c["title"].split(" · ")[0].lower() in d["title"].lower():
            records.update(c["id"], sid, {"status": "firmado", "data": {"firma": date.today().isoformat()}})
    db.audit("dd_firma", d["id"], {"nombre": nombre, "version": d["version"]["version"], "huella": huella}, actor=user["username"])
    return {"ok": True, "constancia": rec["id"], "huella": huella}


# ---------- Guardar el resultado de una herramienta como entregable revisable

def save_tool_result(space_id: str, mod: dict, res: dict) -> dict:
    secs = [{"key": "resumen", "title": "Resumen", "type": "text", "body": res.get("resumen") or res["titulo"]}]
    secs += [{"key": f"s{i}", "title": s["titulo"][:200], "type": "text", "body": s["contenido"]} for i, s in enumerate(res.get("secciones") or [], 1)]
    secs += engine._tool_sections(res)
    return review.create(space_id, "dd", f"{mod['id']} · {res.get('titulo_doc') or res['titulo']}"[:300],
                         {"summary": (res.get("resumen") or "")[:1200], "sections": secs, "meta": {"modulo": mod["id"], "accion": res["herramienta"], "sin_ia": True}},
                         author="doomsday", ref_id=mod["id"])
