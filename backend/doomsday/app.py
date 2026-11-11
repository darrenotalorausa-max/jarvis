"""API de Doomsday: el motor de Jarvis (conexiones, cola, registros, revisión, apps conectadas) más las rutas propias `/api/dd/*`.

Todas las rutas nuevas quedan fuera de la lista blanca de `access.allowed`: solo el propietario las alcanza.
"""
from __future__ import annotations
from datetime import date

from fastapi import APIRouter, Body, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse

from jarvis import api as japi
from jarvis import config, connections, connectors, db, jobs, records, review, secrets_store
from jarvis.providers.base import ProviderError
from jarvis.security import safe_join
from jarvis.util import new_id, now_iso

from . import VERSION, catalog, engine, integrations, kinds, plans, skills, tools, tools2  # noqa: F401

kinds.register()
integrations.register()
plans.register()
japi.JOB_TYPES["dd_plan"] = "Plan de acciones externas"
japi.JOB_TYPES["dd_run"] = "Orden de Doomsday"
japi.JOB_TYPES["dd_clip"] = "Recorte de clip"
app = japi.app
app.title = "Doomsday"
router = APIRouter(prefix="/api/dd")
DIST = config.REPO_ROOT / "frontend" / "dist-doomsday"


def ensure_seed() -> dict:
    """Crea una vez las cuatro capas del ecosistema como espacios aislados. Idempotente."""
    spaces = db.get_setting("dd_spaces", {}) or {}
    for key, (name, kind, _) in catalog.LAYERS.items():
        if key in spaces and db.one("SELECT id FROM spaces WHERE id=?", (spaces[key],)):
            continue
        sid = new_id("esp")
        db.execute("INSERT INTO spaces(id,name,kind,ai_policy,created_at,updated_at) VALUES(?,?,?,?,?,?)", (sid, name, kind, "nube_permitida", now_iso(), now_iso()))
        spaces[key] = sid
    db.set_setting("dd_spaces", spaces)
    if not db.get_setting("onboarded"):
        db.set_setting("onboarded", True)
    return spaces


def _space_of(mod: dict, space: str | None = None) -> str:
    spaces = ensure_seed()
    sid = space or spaces[mod["capa"]]
    row = db.one("SELECT id, kind FROM spaces WHERE id=? AND archived=0", (sid,))
    if not row:
        raise HTTPException(404, "El espacio no existe.")
    if row["kind"] != catalog.LAYERS[mod["capa"]][1]:
        # Un módulo solo trabaja en espacios de su capa: los datos de clientes, tiendas y personales no se cruzan.
        raise ValueError(f"El módulo {mod['id']} pertenece a la capa «{catalog.LAYERS[mod['capa']][0]}» y no puede usarse en ese espacio.")
    return sid


def _module(mid: str) -> dict:
    if mid not in catalog.MODULES:
        raise KeyError(mid)
    return catalog.MODULES[mid]


@router.get("/catalog")
def get_catalog():
    return {"version": VERSION, **catalog.public(), "espacios": ensure_seed(), "herramientas": tools.public(), "skills": skills.listing()}


@router.get("/overview")
def overview():
    """Actividad por módulo: registros en sus tipos, entregables y trabajos. Solo conteos."""
    spaces = ensure_seed()
    ent = {r["ref_id"]: r for r in db.query("SELECT ref_id, COUNT(*) total, SUM(CASE WHEN status IN ('borrador','en_revision') THEN 1 ELSE 0 END) por_revisar, MAX(updated_at) ultimo "
                                            "FROM deliverables WHERE kind='dd' AND archived=0 GROUP BY ref_id")}
    rec = {(r["space_id"], r["kind"]): r["c"] for r in db.query("SELECT space_id, kind, COUNT(*) c FROM records WHERE archived=0 GROUP BY space_id, kind")}
    mods = {}
    for mid, m in catalog.MODULES.items():
        e = ent.get(mid) or {}
        mods[mid] = {"registros": sum(rec.get((spaces[m["capa"]], k), 0) for k in m["kinds"]), "entregables": e.get("total", 0), "por_revisar": e.get("por_revisar") or 0, "ultimo": e.get("ultimo")}
    estado = {r["status"]: r["c"] for r in db.query("SELECT status, COUNT(*) c FROM jobs WHERE type IN ('dd_run','dd_clip','dd_plan','media_generate','connector_action') GROUP BY status")}
    actividad: dict[str, int] = {}
    for tabla, cond in (("jobs", "type IN ('dd_run','dd_clip','dd_plan')"), ("deliverables", "kind='dd'")):
        for r in db.query(f"SELECT substr(created_at,1,10) d, COUNT(*) c FROM {tabla} WHERE {cond} GROUP BY d ORDER BY d DESC LIMIT 90"):
            actividad[r["d"]] = actividad.get(r["d"], 0) + r["c"]
    return {"modulos": mods, "trabajos": estado, "actividad": actividad, "activos": sum(1 for v in mods.values() if v["registros"] or v["entregables"]),
            "por_revisar": sum(v["por_revisar"] for v in mods.values()), "skills_propias": sum(1 for s in skills.listing() if s["origen"] == "propia")}


@router.post("/run")
def run(body: dict = Body(...)):
    mod = _module(body.get("module") or "")
    act = engine.find_action(mod, body.get("action") or "orden")
    inputs = engine.clean_inputs(act, body.get("inputs") or {})
    if act["id"] == "orden" and not str(inputs.get("orden") or "").strip():
        raise ValueError("Escribe la orden.")
    job, created = jobs.enqueue(_space_of(mod, body.get("space")), "dd_run", f"{mod['id']} · {act['label']}", {"module": mod["id"], "action": act["id"], "inputs": inputs},
                                limits=body.get("limits"))
    return {"job": job, "created": created}


@router.post("/tools/{tool_id}")
def run_tool(tool_id: str, body: dict = Body(default={})):
    mod = _module(body.get("module") or "")
    if tool_id not in mod["tools"]:
        raise KeyError(tool_id)
    sid = _space_of(mod, body.get("space"))
    res = tools.run(tool_id, sid, {**(body.get("inputs") or {}), "_module": mod["id"]})
    if body.get("guardar") and (res.get("secciones") or res.get("tablas")):
        res["deliverable_id"] = plans.save_tool_result(sid, mod, res)["id"]
    return res


# ---------- Skills (X06)

@router.get("/skills/{skill_id}")
def get_skill(skill_id: str):
    return skills.get(skill_id)


@router.put("/skills/{skill_id}")
def put_skill(skill_id: str, body: dict = Body(...)):
    return skills.save(skill_id, str(body.get("texto") or ""), str(body.get("nota") or ""))


@router.delete("/skills/{skill_id}")
def delete_skill(skill_id: str):
    return skills.restore(skill_id)


@router.post("/skills/import")
def import_skills(files: list[UploadFile] = File(...)):
    return skills.import_files([(f.filename or "", f.file.read(2_000_000)) for f in files[:60]])


# ---------- Bóveda de accesos (P02): el secreto vive en el almacén cifrado, nunca en SQLite ni en respuestas de listado

def _vault_rec(rec_id: str) -> dict:
    rec = records.get(rec_id)
    if not rec or rec["kind"] != "dd_acceso":
        raise KeyError(rec_id)
    return rec


@router.post("/vault")
def vault_add(body: dict = Body(...)):
    secreto = str(body.get("secreto") or "")
    if not secreto:
        raise ValueError("Escribe la contraseña o el token a guardar.")
    rec = records.create(_space_of(_module("P02"), body.get("space")), "dd_acceso", str(body.get("titulo") or ""),
                         {k: body.get(k) for k in ("coleccion", "usuario", "url", "tiene_2fa", "compartido_con") if body.get(k) not in (None, "")})
    secrets_store.set_secret(f"dd_vault:{rec['id']}", secreto)
    db.audit("dd_boveda_alta", rec["id"], {"titulo": rec["title"]})
    return rec


@router.post("/vault/{rec_id}/reveal")
def vault_reveal(rec_id: str):
    rec = _vault_rec(rec_id)
    if rec["status"] == "revocado":
        raise ValueError("Este acceso está revocado.")
    db.audit("dd_boveda_revelado", rec_id, {"titulo": rec["title"]})
    return {"secreto": secrets_store.get_secret(f"dd_vault:{rec_id}") or ""}


@router.delete("/vault/{rec_id}")
def vault_revoke(rec_id: str):
    rec = _vault_rec(rec_id)
    secrets_store.delete_secret(f"dd_vault:{rec_id}")
    db.audit("dd_boveda_revocado", rec_id, {"titulo": rec["title"]})
    return records.update(rec_id, rec["space_id"], {"status": "revocado"})


# ---------- Núcleo de datos (G01): lectura desde una app conectada → registros. Leer no requiere aprobación.

SHOPIFY_STATUS = {"fulfilled": "confirmado", "partial": "confirmado", None: "pendiente", "restocked": "devuelto"}


@router.post("/sync/shopify")
def sync_shopify(body: dict = Body(...)):
    conn = connections.get(str(body.get("connection_id") or ""))
    if not conn or conn["provider"] != "api" or not conn["enabled"] or not conn["terms_accepted"]:
        raise ValueError("Elige una conexión de Shopify habilitada (Apps conectadas → plantilla Shopify).")
    conn["options"] = connectors.validate_options(conn["options"])
    sid = _space_of(_module("G01"), body.get("space"))
    try:
        res = connectors.execute(conn, "pedidos", {"limite": str(min(int(body.get("limite") or 250), 250))})
    except ProviderError as exc:
        connections.record_error(conn, exc)
        raise
    orders = (res.get("json") or {}).get("orders")
    if not isinstance(orders, list):
        raise ValueError("La conexión no devolvió una lista de pedidos. Comprueba que usa la plantilla de Shopify y tiene permiso de lectura de pedidos.")
    known = {r["data"].get("ref") for r in records.list_records(sid, "dd_pedido", limit=20000)}
    nuevos = 0
    for o in orders:
        ref = str(o.get("name") or o.get("id") or "")
        if not ref or ref in known:
            continue
        estado = "cancelado" if o.get("cancelled_at") else SHOPIFY_STATUS.get(o.get("fulfillment_status"), "pendiente")
        items = o.get("line_items") or []
        ship = (o.get("shipping_address") or {})
        records.create(sid, "dd_pedido", ref, {"ref": ref, "fecha": str(o.get("created_at") or "")[:10], "tienda": conn["name"],
                                                "producto": (items[0].get("title") if items else None), "unidades": sum(int(i.get("quantity") or 0) for i in items) or 1,
                                                "precio": o.get("total_price"), "ciudad": ship.get("city"), "campana": (o.get("source_name") or None),
                                                "tel_hash": plans.phone_hash(o.get("phone") or ship.get("phone") or "")}, status=estado)
        nuevos += 1
    db.audit("dd_sync_shopify", conn["id"], {"leidos": len(orders), "nuevos": nuevos})
    return {"leidos": len(orders), "nuevos": nuevos, "nota": "Shopify no informa la entrega COD ni el costo: completa estado, costo y fletes (a mano o importando el archivo de tu operador logístico)."}


@router.post("/habits/check")
def habit_check(body: dict = Body(...)):
    """Marca un hábito como cumplido hoy (H09, R03). Idempotente por día."""
    mod = _module(body.get("module") or "H09")
    sid, hoy, nombre = _space_of(mod, body.get("space")), date.today().isoformat(), str(body.get("habito") or "")
    if not nombre:
        raise ValueError("Indica el hábito.")
    if not any(r["data"].get("habito") == nombre and r["data"].get("fecha") == hoy for r in records.list_records(sid, "dd_habito_registro", limit=5000)):
        records.create(sid, "dd_habito_registro", f"{nombre} · {hoy}", {"habito": nombre, "fecha": hoy})
    return tools.run("habitos", sid)


# El comodín de la interfaz de Jarvis debe quedar al final: se retira, se añaden las rutas de Doomsday y se registra el propio.
app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/{full_path:path}"]
app.include_router(router)
app.include_router(integrations.router)
app.include_router(plans.router)


@app.get("/{full_path:path}")
def frontend(full_path: str):
    if full_path.startswith("api/"):
        raise HTTPException(404, "No encontrado.")
    if DIST.is_dir():
        target = safe_join(DIST, full_path) if full_path else DIST / "doomsday.html"
        if target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "doomsday.html", headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("La interfaz de Doomsday no está compilada. Ejecuta scripts/setup.sh (o SETUP_JARVIS.cmd).", status_code=503)
