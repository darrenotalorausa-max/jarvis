"""API HTTP local (FastAPI). Solo loopback por defecto, con validación de Host y Origin."""
from __future__ import annotations
import asyncio
import json
import logging
import platform
import sys
import time
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, Response, StreamingResponse

from . import access, assistant, backup, business, config, connections, db, economy, files, jobs, library, notify, records, review, router, secrets_store
from .handlers import clipping as clipping_h, opportunities as opp_h, video as video_h
from .jobs import JobError
from .providers.base import ProviderError
from .security import SecurityError, redact, safe_join, sanitize_filename
from .util import new_id, now_iso

log = logging.getLogger("jarvis.api")
app = FastAPI(title="Jarvis OS", version=config.APP_VERSION, docs_url=None, redoc_url=None, openapi_url=None)

SPACE_KINDS = {"personal": "Personal", "negocio": "Negocio", "marca": "Marca", "cliente": "Cliente"}
AI_POLICIES = {"solo_local": "Solo proveedores locales", "nube_permitida": "Nube permitida", "sin_ia": "Sin IA"}
JOB_TYPES = {
    "opportunity_research": "Investigación de oportunidades", "lead_search": "Búsqueda de leads", "lead_proposal": "Propuesta B2B",
    "content_batch": "Lote de contenido", "video_transcribe": "Transcripción de video", "video_suggest": "Sugerencia de momentos",
    "video_render": "Exportación de video", "shopify_package": "Paquete Shopify", "clipping_import_url": "Importar campaña de clipping",
    "external_export": "Envío externo",
}
SETTINGS_KEYS = {"user_name", "allow_paid", "onboarded", "voice", "min_cpm", "worker_concurrency", "business_types", "agents_paused"}


def _allowed_hosts() -> set[str]:
    p = config.port()
    return {f"127.0.0.1:{p}", f"localhost:{p}", "testserver"}


@app.middleware("http")
async def guard(request: Request, call_next):
    """Desde este equipo: validación de Host y Origin (DNS rebinding y peticiones de otras webs).
    Desde otro dispositivo (solo si se activó el acceso en red): además, sesión iniciada con el código de acceso."""
    host = request.headers.get("host", "")
    client = request.client.host if request.client else "127.0.0.1"
    remote = not access.is_loopback(client)
    path = request.url.path
    if remote:
        if not access.enabled():
            return JSONResponse({"detail": "El acceso desde otros dispositivos no está activado."}, status_code=403)
        if path.startswith("/api/") and path not in ("/api/login", "/api/health") and not access.valid_cookie(request.cookies.get(access.COOKIE)):
            return JSONResponse({"detail": "Introduce el código de acceso.", "kind": "login"}, status_code=401)
    elif host not in _allowed_hosts():
        return JSONResponse({"detail": "Host no permitido."}, status_code=403)
    origin = request.headers.get("origin")
    if origin and request.method not in ("GET", "HEAD", "OPTIONS"):
        ok = origin.split("://", 1)[-1] == host if remote else origin.split("://", 1)[-1] in _allowed_hosts()
        if not ok:
            return JSONResponse({"detail": "Origen no permitido."}, status_code=403)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    if path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/api/login")
def login(request: Request, body: dict = Body(...)):
    client = request.client.host if request.client else "127.0.0.1"
    token = access.login(client, str(body.get("code") or ""))
    resp = JSONResponse({"ok": True})
    resp.set_cookie(access.COOKIE, token, httponly=True, samesite="strict", max_age=30 * 24 * 3600)
    return resp


@app.exception_handler(KeyError)
async def on_missing(request: Request, exc: KeyError):
    return JSONResponse({"detail": "No encontrado."}, status_code=404)


@app.exception_handler(ValueError)  # incluye RecordError, ReviewError, SecurityError y validaciones
async def on_invalid(request: Request, exc: ValueError):
    return JSONResponse({"detail": redact(str(exc))[:600]}, status_code=400)


@app.exception_handler(JobError)
async def on_job_error(request: Request, exc: JobError):
    return JSONResponse({"detail": redact(exc.message)}, status_code=400)


@app.exception_handler(ProviderError)
async def on_provider_error(request: Request, exc: ProviderError):
    return JSONResponse({"detail": exc.message, "status": exc.status}, status_code=502)


@app.exception_handler(router.RouterError)
async def on_router_error(request: Request, exc: router.RouterError):
    return JSONResponse({"detail": exc.message, "kind": exc.kind}, status_code=409)


def _space(space_id: str) -> dict:
    sp = db.one("SELECT * FROM spaces WHERE id=?", (space_id,))
    if not sp:
        raise HTTPException(404, "El espacio no existe.")
    return sp


def _user() -> str:
    return db.get_setting("user_name", "usuario") or "usuario"


# ---------- Arranque y ajustes

@app.get("/api/health")
def health():
    return {"ok": True, "version": config.APP_VERSION, "ts": now_iso()}


def _worker_alive() -> bool:
    hb = db.get_setting("worker_heartbeat")
    return bool(hb and time.time() - float(hb) < 20)


@app.get("/api/bootstrap")
def bootstrap():
    return {
        "version": config.APP_VERSION, "settings": {k: db.get_setting(k) for k in SETTINGS_KEYS},
        "spaces": db.query("SELECT * FROM spaces ORDER BY created_at"), "space_kinds": SPACE_KINDS, "ai_policies": AI_POLICIES,
        "schema": records.schema(), "providers": connections.PROVIDERS, "capabilities": connections.CAPABILITIES,
        "deliverable_kinds": {k: v["label"] for k, v in review.KINDS.items()}, "deliverable_statuses": review.STATUSES,
        "job_types": JOB_TYPES, "job_statuses": jobs.STATUS_LABELS, "secrets_backend": secrets_store.backend(),
        "ffmpeg": video_h.ffmpeg_status(), "video": {"presets": list(video_h.PRESETS), "framings": video_h.FRAMINGS, "modes": video_h.MODES},
        "worker_alive": _worker_alive(), "local_transcription": __import__("jarvis.providers.voice", fromlist=["x"]).local_whisper_available(),
    }


@app.patch("/api/settings")
def patch_settings(body: dict = Body(...)):
    for k, v in body.items():
        if k not in SETTINGS_KEYS:
            raise ValueError(f"Ajuste desconocido: {k}")
        if k == "allow_paid":
            db.audit("ajuste.gasto_pago", "", {"activado": bool(v)}, actor=_user())
        db.set_setting(k, v)
    return {k: db.get_setting(k) for k in SETTINGS_KEYS}


@app.get("/api/spaces")
def list_spaces():
    return db.query("SELECT * FROM spaces ORDER BY created_at")


@app.post("/api/spaces")
def create_space(body: dict = Body(...)):
    name, kind = (body.get("name") or "").strip(), body.get("kind") or "negocio"
    if not name or kind not in SPACE_KINDS:
        raise ValueError("Indica un nombre y un tipo de espacio válido.")
    policy = body.get("ai_policy") or "solo_local"
    if policy not in AI_POLICIES:
        raise ValueError("Política de IA no válida.")
    sid = new_id("esp")
    db.execute("INSERT INTO spaces(id,name,kind,ai_policy,notes,created_at,updated_at) VALUES(?,?,?,?,?,?,?)", (sid, name[:120], kind, policy, body.get("notes") or "", now_iso(), now_iso()))
    return _space(sid)


@app.patch("/api/spaces/{space_id}")
def patch_space(space_id: str, body: dict = Body(...)):
    _space(space_id)
    sets, params = [], []
    for k in ("name", "notes"):
        if k in body:
            sets.append(f"{k}=?")
            params.append(str(body[k])[:500])
    if "ai_policy" in body:
        if body["ai_policy"] not in AI_POLICIES:
            raise ValueError("Política de IA no válida.")
        sets.append("ai_policy=?")
        params.append(body["ai_policy"])
        db.audit("espacio.politica_ia", space_id, {"politica": body["ai_policy"]}, actor=_user())
    if "archived" in body:
        sets.append("archived=?")
        params.append(int(bool(body["archived"])))
    if sets:
        db.execute(f"UPDATE spaces SET {','.join(sets)}, updated_at=? WHERE id=?", (*params, now_iso(), space_id))
    return _space(space_id)


@app.get("/api/overview")
def overview(space: str):
    _space(space)
    return {"pendientes": assistant.pending_summary(space), "disponibilidad": router.availability(space), "worker_alive": _worker_alive(),
            "trabajos": jobs.list_jobs(space, limit=8), "clipping_alertas": len(clipping_h.summary(space)["alertas"])}


# ---------- Registros

@app.get("/api/records")
def list_records(space: str, kind: str, archived: bool = False, project_id: str | None = None, brand_id: str | None = None,
                 status: str | None = None, q: str | None = None):
    _space(space)
    if kind not in records.KINDS:
        raise ValueError("Tipo de registro desconocido.")
    return records.list_records(space, kind, archived=archived, project_id=project_id, brand_id=brand_id, status=status, q=q)


@app.post("/api/records")
def create_record(body: dict = Body(...)):
    data = body.get("data") or {}
    if body.get("kind") == "video_project":
        data = video_h.validate_project(data, body.get("space"))
    return records.create(body.get("space"), body.get("kind"), body.get("title") or "", data, status=body.get("status"),
                          project_id=body.get("project_id"), brand_id=body.get("brand_id"))


@app.get("/api/records/export.csv")
def export_records(space: str, kind: str):
    _space(space)
    text = records.export_csv(space, kind)
    out = config.exports_dir() / sanitize_filename(space) / f"{kind}-{now_iso()[:10]}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text, encoding="utf-8-sig")
    return PlainTextResponse(text, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{kind}.csv"'})


@app.post("/api/records/import")
def import_records(body: dict = Body(...)):
    _space(body.get("space"))
    text = body.get("text") or ""
    if len(text) > 20_000_000:
        raise ValueError("El CSV supera el tamaño máximo (20 MB).")
    if not body.get("mapping"):
        headers, rows = records.parse_csv(text)
        return {"columnas": headers, "filas": len(rows), "muestra": rows[:5]}
    return records.import_csv(body["space"], body.get("kind"), text, body["mapping"], commit=bool(body.get("commit")),
                              defaults=body.get("defaults"), project_id=body.get("project_id"), skip_duplicates=body.get("skip_duplicates", True))


@app.get("/api/records/{record_id}")
def get_record(record_id: str, space: str):
    rec = records.get(record_id, space)
    if not rec:
        raise KeyError(record_id)
    return rec


@app.patch("/api/records/{record_id}")
def patch_record(record_id: str, body: dict = Body(...)):
    space = body.pop("space", None)
    rec = records.get(record_id, space)
    if not rec:
        raise KeyError(record_id)
    if rec["kind"] == "video_project" and "data" in body:
        body["data"] = video_h.validate_project(body["data"], space)
    return records.update(record_id, space, body)


# ---------- Conexiones y router

@app.get("/api/connections")
def list_connections():
    return [connections.public(c) for c in connections.list_all()]


@app.post("/api/connections")
def create_connection(body: dict = Body(...)):
    return connections.create(body)


@app.patch("/api/connections/{conn_id}")
def patch_connection(conn_id: str, body: dict = Body(...)):
    return connections.update(conn_id, body)


@app.delete("/api/connections/{conn_id}")
def delete_connection(conn_id: str):
    connections.delete(conn_id)
    return {"ok": True}


@app.post("/api/connections/{conn_id}/test")
def test_connection(conn_id: str):
    return connections.test(conn_id)


@app.get("/api/connections/{conn_id}/models")
def connection_models(conn_id: str):
    return {"items": connections.models(conn_id)}


@app.get("/api/availability")
def availability(space: str):
    return router.availability(space)


@app.get("/api/usage")
def usage():
    out = router.usage_summary()
    out["recientes"] = db.query("""SELECT u.ts, u.capability, u.category, u.provider, u.model, u.tokens_in, u.tokens_out, u.est_cost_usd, u.cost_basis,
                                   u.duration_ms, u.cached, u.state, u.error, u.job_id, c.name connection FROM usage u
                                   LEFT JOIN connections c ON c.id=u.connection_id ORDER BY u.id DESC LIMIT 60""")
    return out


@app.get("/api/diagnostics")
def diagnostics():
    counts = {t: db.one(f"SELECT COUNT(*) c FROM {t}")["c"] for t in ("spaces", "records", "deliverables", "jobs", "files", "sources", "cache")}
    by_status = {r["status"]: r["c"] for r in db.query("SELECT status, COUNT(*) c FROM jobs GROUP BY status")}
    return {"version": config.APP_VERSION, "python": sys.version.split()[0], "sistema": f"{platform.system()} {platform.release()}",
            "esquema": db.schema_version(), "ffmpeg": video_h.ffmpeg_status(), "worker_activo": _worker_alive(), "secretos": secrets_store.backend(),
            "escucha": f"{config.host()}:{config.port()}", "solo_loopback": config.host() in ("127.0.0.1", "localhost"),
            "acceso_red": {"activo": access.enabled(), "direcciones": access.lan_urls() if access.enabled() else []},
            "directorios": {"datos": str(config.data_dir()), "exportaciones": str(config.exports_dir()), "logs": str(config.logs_dir())},
            "conteos": counts, "trabajos_por_estado": by_status,
            "auditoria": db.query("SELECT ts, actor, action, target FROM audit ORDER BY id DESC LIMIT 30")}


@app.post("/api/cache/clear")
def clear_cache(body: dict = Body(default={})):
    if body.get("space"):
        n = db.execute("DELETE FROM cache WHERE space_id=?", (body["space"],))
    else:
        n = db.execute("DELETE FROM cache")
    return {"eliminadas": n}


# ---------- Trabajos

@app.get("/api/jobs")
def list_jobs(space: str | None = None, status: str | None = None, limit: int = 100):
    return jobs.list_jobs(space, status, min(limit, 300))


@app.post("/api/jobs")
def create_job(body: dict = Body(...)):
    space, type_ = body.get("space"), body.get("type")
    _space(space)
    if type_ not in JOB_TYPES:
        raise ValueError("Tipo de trabajo no soportado.")
    params = body.get("params") or {}
    if not isinstance(params, dict) or len(json.dumps(params)) > 200_000:
        raise ValueError("Parámetros no válidos.")
    title = (body.get("title") or JOB_TYPES[type_])[:200]
    job, created = jobs.enqueue(space, type_, title, params, limits=body.get("limits"), idempotency_key=body.get("idempotency_key"))
    return {"job": job, "created": created}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    job = jobs.get(job_id)
    if not job:
        raise KeyError(job_id)
    job["events"] = jobs.events(job_id)
    return job


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str):
    return jobs.request_cancel(job_id)


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: str):
    return jobs.retry(job_id)


@app.get("/api/events")
async def events(request: Request):
    """SSE: empuja cambios de trabajos leyendo la tabla de eventos. No mantiene ninguna llamada a modelos abierta.
    Es asíncrono para cerrarse de inmediato cuando el cliente se desconecta o el servidor se detiene."""
    async def stream():
        last = (await run_in_threadpool(db.one, "SELECT COALESCE(MAX(id),0) m FROM job_events") or {"m": 0})["m"]
        yield "retry: 3000\n\n"
        idle = 0
        while not await request.is_disconnected():
            rows = await run_in_threadpool(db.query, "SELECT job_id, MAX(id) mid FROM job_events WHERE id>? GROUP BY job_id", (last,))
            if rows:
                idle = 0
                for r in rows:
                    last = max(last, r["mid"])
                    job = await run_in_threadpool(jobs.get, r["job_id"])
                    if job:
                        yield f"event: job\ndata: {json.dumps(job, ensure_ascii=False)}\n\n"
            else:
                idle += 1
                if idle % 15 == 0:
                    yield ": latido\n\n"
            await asyncio.sleep(1)
    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


# ---------- Archivos

@app.get("/api/files")
def list_files(space: str, origin: str | None = None):
    _space(space)
    return files.list_files(space, origin)


@app.post("/api/files")
def upload_file(space: str = Form(...), file: UploadFile = File(...)):
    _space(space)
    row = files.save_stream(space, file.filename or "archivo", file.file)
    if Path(row["name"]).suffix.lower() in video_h.VIDEO_EXT | {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}:
        try:
            files.set_meta(row["id"], video_h.probe(files.path_of(row)))
        except JobError as exc:
            files.set_meta(row["id"], {"probe_error": exc.message})
    return files.get(row["id"])


@app.get("/api/files/{file_id}/download")
def download_file(file_id: str, space: str, inline: bool = False):
    f = files.get(file_id, space)
    if not f:
        raise KeyError(file_id)
    safe_inline = inline and (f["mime"] or "").split("/")[0] in ("video", "audio", "image") and f["mime"] != "image/svg+xml"
    return FileResponse(files.path_of(f), media_type=f["mime"] if safe_inline else "application/octet-stream", filename=f["name"],
                        content_disposition_type="inline" if safe_inline else "attachment")


@app.get("/api/files/{file_id}/preview")
def preview_html(file_id: str, space: str):
    """Vista previa HTML generada por Jarvis (paquete Shopify), servida aislada: sin scripts ni acceso al origen."""
    f = files.get(file_id, space)
    if not f or f["origin"] != "job" or not f["name"].endswith(".html"):
        raise KeyError(file_id)
    return Response(files.path_of(f).read_bytes(), media_type="text/html; charset=utf-8",
                    headers={"Content-Security-Policy": "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:"})


@app.post("/api/files/{file_id}/describe")
def describe_image(file_id: str, body: dict = Body(...)):
    """Descripción de una imagen con un modelo con visión. La imagen solo sale del equipo si la política del espacio lo permite."""
    import base64
    space = body.get("space")
    f = files.get(file_id, space)
    if not f or f["mime"] not in ("image/png", "image/jpeg", "image/webp", "image/gif"):
        raise ValueError("El archivo no es una imagen compatible (PNG, JPEG, WebP o GIF).")
    if f["size"] > 8 * 1024 * 1024:
        raise ValueError("La imagen supera 8 MB.")
    data = base64.b64encode(files.path_of(f).read_bytes()).decode()
    text, meta = router.llm(router.Ctx(space_id=space, limits={"max_calls": 1, "max_tokens": 20000, "max_cost_usd": 0.2}),
                            system="Describe en español, de forma objetiva y breve, lo que se ve en la imagen. No identifiques personas ni inventes contexto.",
                            user=str(body.get("question") or "Describe esta imagen para catalogarla.")[:500], images=[(f["mime"], data)], max_tokens=400)
    return {"text": text.strip(), "connection": meta["connection"], "model": meta.get("model")}


@app.delete("/api/files/{file_id}")
def archive_file(file_id: str, space: str):
    if not files.get(file_id, space):
        raise KeyError(file_id)
    files.archive(file_id)
    return {"ok": True, "nota": "Archivado: deja de listarse, pero no se borra del disco."}


@app.get("/api/exports/file")
def export_file(path: str):
    p = safe_join(config.exports_dir(), path)
    if not p.is_file():
        raise KeyError(path)
    return FileResponse(p, media_type="application/octet-stream", filename=p.name)


# ---------- Entregables, revisión y aprobación

@app.get("/api/deliverables")
def list_deliverables(space: str, status: str | None = None, kind: str | None = None, archived: bool = False):
    _space(space)
    return review.list_deliverables(space, status=status, kind=kind, archived=archived)


@app.post("/api/deliverables")
def create_deliverable(body: dict = Body(...)):
    _space(body.get("space"))
    kind = body.get("kind") or "documento"
    content = body.get("content") or review.TEMPLATES.get(kind, review.TEMPLATES["documento"])()
    return review.create(body["space"], kind, body.get("title") or review.KINDS[kind]["label"], content, author=_user(),
                         project_id=body.get("project_id"), brand_id=body.get("brand_id"), ref_id=body.get("ref_id"))


@app.get("/api/deliverables/{did}")
def get_deliverable(did: str, space: str, version: int | None = None):
    d = review.detail(did, space)
    if not d:
        raise KeyError(did)
    if version and version != d["current_version"]:
        d["viewing"] = review.get_version(did, version)
    return d


@app.post("/api/deliverables/{did}/versions")
def new_version(did: str, body: dict = Body(...)):
    review.add_version(did, body.get("space"), body.get("content") or {}, author=_user(), note=body.get("note") or "Edición manual", title=body.get("title"))
    return review.detail(did, body.get("space"))


@app.post("/api/deliverables/{did}/status")
def deliverable_status(did: str, body: dict = Body(...)):
    if body.get("status") not in ("borrador", "en_revision"):
        raise ValueError("Usa aprobar o rechazar para esos estados.")
    review.set_status(did, body.get("space"), body["status"])
    return review.detail(did, body.get("space"))


@app.post("/api/deliverables/{did}/archive")
def deliverable_archive(did: str, body: dict = Body(...)):
    if not review.get(did, body.get("space")):
        raise KeyError(did)
    db.execute("UPDATE deliverables SET archived=?, updated_at=? WHERE id=?", (int(bool(body.get("archived", True))), now_iso(), did))
    return {"ok": True}


@app.post("/api/deliverables/{did}/comments")
def deliverable_comment(did: str, body: dict = Body(...)):
    kind = body.get("kind") or "comentario"
    if kind not in ("comentario", "cambio_solicitado"):
        raise ValueError("Tipo de comentario no válido.")
    review.comment(did, body.get("space"), body.get("body") or "", kind=kind, author=_user())
    return review.detail(did, body.get("space"))


@app.post("/api/deliverables/{did}/approve")
def deliverable_approve(did: str, body: dict = Body(...)):
    review.approve(did, body.get("space"), version=int(body.get("version") or 0), user=_user(), action=body.get("action") or "version",
                   destination=body.get("destination") or "", scope=body.get("scope") or "", expires_hours=float(body.get("expires_hours") or 72))
    if body.get("action") == "envio_externo":
        # Reanuda envíos que estuvieran esperando exactamente esta aprobación.
        for j in jobs.list_jobs(body.get("space"), "waiting_approval"):
            if j["type"] == "external_export" and j["params"].get("deliverable_id") == did:
                jobs.retry(j["id"])
    return review.detail(did, body.get("space"))


@app.post("/api/deliverables/{did}/reject")
def deliverable_reject(did: str, body: dict = Body(...)):
    review.reject(did, body.get("space"), body.get("reason") or "", _user())
    return review.detail(did, body.get("space"))


@app.post("/api/approvals/{aid}/revoke")
def revoke_approval(aid: str):
    review.revoke(aid)
    return {"ok": True}


@app.post("/api/deliverables/{did}/export")
def deliverable_export(did: str, body: dict = Body(...)):
    return review.export(did, body.get("space"), body.get("format") or "md")


@app.get("/api/deliverables/{did}/diff")
def deliverable_diff(did: str, space: str, a: int, b: int):
    return review.diff(did, space, a, b)


@app.post("/api/deliverables/{did}/convert")
def deliverable_convert(did: str, body: dict = Body(...)):
    return opp_h.convert(did, body.get("space"), body.get("target") or "")


@app.post("/api/deliverables/{did}/send")
def deliverable_send(did: str, body: dict = Body(...)):
    """Crea el trabajo de envío externo. No envía nada hasta que exista una aprobación específica y vigente."""
    space = body.get("space")
    d = review.get(did, space)
    conn = connections.get(body.get("connection_id") or "")
    if not d or not conn or conn["provider"] != "webhook":
        raise ValueError("Entregable o destino no válido.")
    job, created = jobs.enqueue(space, "external_export", f"Envío externo: {d['title'][:80]}", {"deliverable_id": did, "connection_id": conn["id"]}, max_attempts=1)
    return {"job": job, "created": created, "destination": conn["base_url"]}


# ---------- Video

@app.get("/api/video/preview")
def video_preview(space: str, file: str, t: float = 0, preset: str = "9:16", framing: str = "recorte", fx: float = 0.5, fy: float = 0.5):
    f = files.get(file, space)
    if not f:
        raise KeyError(file)
    return Response(video_h.preview_frame(f, t, preset, framing, fx, fy), media_type="image/png")


@app.get("/api/video/{project_id}/subtitles")
def video_subtitles(project_id: str, space: str, file: str, fmt: str = "srt"):
    rec = records.get(project_id, space)
    if not rec or rec["kind"] != "video_project":
        raise KeyError(project_id)
    cues = (rec["data"].get("subtitles") or {}).get(file) or []
    text = video_h.to_vtt(cues) if fmt == "vtt" else video_h.to_srt(cues)
    return PlainTextResponse(text, headers={"Content-Disposition": f'attachment; filename="subtitulos.{"vtt" if fmt == "vtt" else "srt"}"'})


@app.post("/api/video/{project_id}/subtitles")
def video_import_subtitles(project_id: str, body: dict = Body(...)):
    space = body.get("space")
    rec = records.get(project_id, space)
    if not rec or rec["kind"] != "video_project":
        raise KeyError(project_id)
    cues = video_h.parse_subtitles(body.get("text") or "")
    if not cues:
        raise ValueError("No se encontraron subtítulos válidos (formatos admitidos: SRT y VTT).")
    data = dict(rec["data"])
    data["subtitles"] = {**(data.get("subtitles") or {}), body.get("file"): cues}
    return records.update(project_id, space, {"data": video_h.validate_project(data, space)})


@app.get("/api/video/{project_id}/manifest")
def video_manifest(project_id: str, space: str):
    rec = records.get(project_id, space)
    if not rec or rec["kind"] != "video_project":
        raise KeyError(project_id)
    data = video_h.validate_project(rec["data"], space)
    outs = [f for f in (files.get(i, space) for i in rec["data"].get("outputs") or []) if f]
    return JSONResponse(video_h.build_manifest(rec, data, space, outs), headers={"Content-Disposition": 'attachment; filename="manifiesto.json"'})


# ---------- Biblioteca de conocimiento y Centro de negocios

@app.get("/api/library")
def library_tree():
    return library.tree()


@app.get("/api/library/doc")
def library_doc(path: str):
    return library.doc(path)


@app.get("/api/library/file")
def library_file(path: str):
    p = library.file_path(path)
    return FileResponse(p, media_type="application/pdf", filename=p.name)


@app.get("/api/library/search")
def library_search(q: str):
    return library.search(q)


@app.get("/api/business/summary")
def business_summary(space: str):
    _space(space)
    return business.summary(space)


@app.post("/api/notify/test")
def notify_test(body: dict = Body(default={})):
    """Envía un aviso de prueba a todos los canales habilitados (acción explícita del usuario)."""
    sent = notify.send("Aviso de prueba: Jarvis puede escribirte a este canal.", space_id=body.get("space"))
    return {"enviados": sent}


# ---------- Clipping y economía

@app.get("/api/clipping/summary")
def clipping_summary(space: str, min_cpm: float | None = None):
    _space(space)
    return clipping_h.summary(space, min_cpm)


@app.get("/api/economy/summary")
def economy_summary(space: str):
    _space(space)
    return economy.summary(space)


# ---------- Jarvis: texto y voz

@app.post("/api/assistant")
def assistant_message(body: dict = Body(...)):
    _space(body.get("space"))
    origin = body.get("origin") if body.get("origin") in ("texto", "voz") else "texto"
    return assistant.handle(body["space"], body.get("text") or "", origin)


@app.get("/api/assistant/history")
def assistant_history(space: str):
    return assistant.history(space)


@app.delete("/api/assistant/history")
def assistant_clear(space: str):
    assistant.clear_history(space)
    return {"ok": True}


@app.get("/api/assistant/tools")
def assistant_tools():
    return {"tools": assistant.tool_specs(), "ayuda": assistant.HELP}


@app.post("/api/voice/transcribe")
def voice_transcribe(space: str = Form(...), audio: UploadFile = File(...), language: str = Form("es")):
    """Transcribe una orden hablada. El audio se guarda solo de forma temporal y se elimina siempre al terminar."""
    _space(space)
    tmp = config.work_dir() / f"voz-{new_id('tmp')}.webm"
    try:
        size = 0
        with open(tmp, "wb") as out:
            while chunk := audio.file.read(1 << 20):
                size += len(chunk)
                if size > 25 * 1024 * 1024:
                    raise ValueError("La grabación supera 25 MB.")
                out.write(chunk)
        result, meta = router.transcribe(router.Ctx(space_id=space, limits={"max_calls": 1, "max_tokens": 1, "max_cost_usd": 0.2}), tmp, language or None)
        return {"text": result["text"].strip(), "connection": meta["connection"], "audio_conservado": False}
    finally:
        tmp.unlink(missing_ok=True)


@app.post("/api/voice/speak")
def voice_speak(body: dict = Body(...)):
    _space(body.get("space"))
    text = (body.get("text") or "").strip()[:600]
    if not text:
        raise ValueError("Texto vacío.")
    audio, _ = router.tts(router.Ctx(space_id=body["space"], limits={"max_calls": 1, "max_tokens": 1, "max_cost_usd": 0.2}), text)
    return Response(audio, media_type="audio/mpeg")


# ---------- Respaldo y restauración

@app.get("/api/backups")
def list_backups():
    return {"items": backup.list_backups(), "carpeta": str(backup.backups_dir())}


@app.post("/api/backups")
def create_backup(body: dict = Body(default={})):
    return backup.create(include_files=bool(body.get("include_files", True)))


def _save_upload(file: UploadFile) -> Path:
    tmp = config.work_dir() / f"restaurar-{new_id('tmp')}.zip"
    with open(tmp, "wb") as out:
        while chunk := file.file.read(1 << 20):
            out.write(chunk)
    return tmp


@app.post("/api/backups/inspect")
def inspect_backup(file: UploadFile = File(...)):
    tmp = _save_upload(file)
    try:
        return backup.inspect(tmp)
    finally:
        tmp.unlink(missing_ok=True)


@app.post("/api/backups/restore")
def restore_backup(file: UploadFile = File(...), confirm: str = Form("")):
    tmp = _save_upload(file)
    try:
        return backup.restore(tmp, confirm == "RESTAURAR")
    finally:
        tmp.unlink(missing_ok=True)


# ---------- Interfaz

DIST = config.REPO_ROOT / "frontend" / "dist"


@app.get("/{full_path:path}")
def frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "No encontrado.")
    if DIST.is_dir():
        target = safe_join(DIST, full_path) if full_path else DIST / "index.html"
        if target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html", headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("La interfaz no está compilada. Ejecuta el instalador (SETUP_JARVIS.cmd o scripts/setup.sh).", status_code=503)
