"""Entregables versionados, comprobaciones automáticas, comentarios, aprobaciones ligadas a versión y exportación."""
from __future__ import annotations
import csv
import difflib
import io
import re
import shutil
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, Field, ValidationError

from . import config, db, files, records
from .security import sanitize_filename
from .util import canonical_json, dumps, iso_in, loads, new_id, now_iso, sha256_text

KINDS = {
    "dossier": {"label": "Expediente de oportunidad", "required": ["comprador", "hechos", "oportunidad", "riesgos", "validacion"]},
    "proposal": {"label": "Propuesta B2B", "required": ["observacion", "muestra", "oferta", "mensaje"]},
    "content_batch": {"label": "Lote de contenido", "required": ["brief", "piezas"]},
    "shopify": {"label": "Paquete Shopify", "required": ["posicionamiento", "faltantes", "archivos"]},
    "video": {"label": "Exportación de video", "required": ["archivos"]},
    "documento": {"label": "Documento", "required": []},
}
STATUSES = ["borrador", "en_revision", "cambios_solicitados", "aprobado", "rechazado"]
HUMAN_CHECKS = {
    "dossier": ["Que las fuentes digan realmente lo que resume cada hecho", "Vigencia de precios y ofertas observados", "Decisión de invertir tiempo o dinero en validar"],
    "proposal": ["Exactitud de la observación sobre la empresa", "Precio, plazos y alcance comprometidos", "Tono y pertinencia del mensaje antes de cualquier envío"],
    "content_batch": ["Veracidad de cada afirmación del guion", "Derechos sobre recursos y música", "Encaje con la voz de la marca y normas de cada plataforma"],
    "shopify": ["Exactitud de precio, condiciones y especificaciones", "Prueba en un tema duplicado: móvil, variantes y carrito", "Cumplimiento legal del mercado de venta"],
    "video": ["Derechos sobre el material de origen", "Cumplimiento de las reglas de la campaña o plataforma", "Calidad del encuadre y subtítulos"],
    "documento": ["Contenido y exactitud"],
}


class Section(BaseModel):
    key: str
    title: str
    type: Literal["text", "list", "table", "facts", "scores", "files"] = "text"
    body: str = ""
    items: list = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    rows: list[list] = Field(default_factory=list)
    note: str = ""


class Content(BaseModel):
    summary: str = ""
    sections: list[Section] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class ReviewError(ValueError):
    pass


def normalize(content: dict) -> dict:
    try:
        return Content.model_validate(content).model_dump()
    except ValidationError as exc:
        raise ReviewError(f"Contenido de entregable no válido: {exc.errors()[0]['msg']}")


def content_hash(content: dict) -> str:
    return sha256_text(canonical_json(content))


def _all_text(content: dict) -> str:
    parts = [content.get("summary", "")]
    for s in content["sections"]:
        parts += [s["body"], s["note"]]
        for it in s["items"]:
            parts.append(" ".join(str(v) for v in it.values()) if isinstance(it, dict) else str(it))
        for row in s["rows"]:
            parts.append(" ".join(str(c) for c in row))
    return "\n".join(parts)


_URL_RE = re.compile(r"https?://[^\s<>\]\)\"']+")


def run_checks(kind: str, content: dict, space_id: str) -> dict:
    """Solo lo verificable de forma determinista. No certifica la verdad del contenido."""
    out = []

    def add(cid, label, result, detail=""):
        out.append({"id": cid, "label": label, "result": result, "detail": detail})

    by_key = {s["key"]: s for s in content["sections"]}
    missing = []
    for key in KINDS.get(kind, KINDS["documento"])["required"]:
        s = by_key.get(key)
        if not s or not (s["body"].strip() or s["items"] or s["rows"]):
            missing.append(key)
    add("campos", "Secciones obligatorias con contenido", "fail" if missing else "ok", ("Faltan o están vacías: " + ", ".join(missing)) if missing else "")

    text = _all_text(content)
    pending = sorted(set(re.findall(r"\[(?:pendiente|por definir|precio por definir)[^\]]*\]", text, flags=re.I)))
    add("pendientes", "Sin marcadores por completar", "warn" if pending else "ok", ", ".join(pending[:6]))

    bad_urls = []
    for u in set(_URL_RE.findall(text)):
        host = urlsplit(u.rstrip(".,;")).hostname or ""
        if "." not in host:
            bad_urls.append(u)
    add("enlaces", "Formato de enlaces", "fail" if bad_urls else "ok",
        ("Enlaces mal formados: " + ", ".join(bad_urls[:5])) if bad_urls else "Solo se comprueba el formato; no se visitó cada enlace.")

    known = {r["id"] for r in db.query("SELECT id FROM sources WHERE space_id=?", (space_id,))}
    facts = [it for s in content["sections"] if s["type"] == "facts" for it in s["items"] if isinstance(it, dict)]
    unsourced = [f.get("claim", "")[:80] for f in facts if f.get("kind") == "hecho" and not f.get("source_ids")]
    unknown = sorted({sid for f in facts for sid in f.get("source_ids", []) if sid not in known} | {sid for sid in content["source_ids"] if sid not in known})
    if facts or content["source_ids"]:
        add("fuentes", "Hechos con fuente registrada", "fail" if (unsourced or unknown) else "ok",
            "; ".join(filter(None, [("Sin fuente: " + " | ".join(unsourced[:4])) if unsourced else "", ("Fuentes no registradas: " + ", ".join(unknown[:4])) if unknown else ""])))
        nums = [f.get("claim", "")[:80] for f in facts if re.search(r"\d", f.get("claim", "")) and not f.get("evidence")]
        add("cifras", "Cifras acompañadas de cita de evidencia", "warn" if nums else "ok", " | ".join(nums[:4]))
    elif kind == "dossier":
        add("fuentes", "Hechos con fuente registrada", "fail", "El expediente no registra fuentes.")

    file_ids = [it.get("file_id") for s in content["sections"] if s["type"] == "files" for it in s["items"] if isinstance(it, dict)]
    lost = [fid for fid in file_ids if not files.get(fid, space_id)]
    if file_ids:
        add("archivos", "Archivos adjuntos presentes", "fail" if lost else "ok", ("No encontrados: " + ", ".join(lost)) if lost else "")

    asset_ids = content["meta"].get("asset_ids") or []
    if asset_ids:
        unconfirmed = []
        for aid in asset_ids:
            rec = records.get(aid, space_id)
            if not rec or rec["data"].get("permission") == "sin_confirmar":
                unconfirmed.append(rec["title"] if rec else aid)
        add("permisos", "Permisos de uso registrados para los recursos de marca", "warn" if unconfirmed else "ok",
            ("Sin permiso confirmado: " + ", ".join(unconfirmed[:5])) if unconfirmed else "")

    return {"ejecutado": now_iso(), "automaticas": out, "requiere_persona": HUMAN_CHECKS.get(kind, HUMAN_CHECKS["documento"]),
            "nota": "Las comprobaciones automáticas validan estructura, formato y registro de fuentes y permisos. No certifican la veracidad."}


def _deliv(row):
    if row:
        row["archived"] = bool(row["archived"])
        row["kind_label"] = KINDS.get(row["kind"], KINDS["documento"])["label"]
    return row


def get(deliverable_id: str, space_id: str | None = None) -> dict | None:
    row = _deliv(db.one("SELECT * FROM deliverables WHERE id=?", (deliverable_id,)))
    if row and space_id and row["space_id"] != space_id:
        return None
    return row


def get_version(deliverable_id: str, version: int | None = None) -> dict | None:
    d = get(deliverable_id)
    if not d:
        return None
    row = db.one("SELECT * FROM deliverable_versions WHERE deliverable_id=? AND version=?", (deliverable_id, version or d["current_version"]))
    if row:
        row["content"] = loads(row["content"], {})
        row["checks"] = loads(row["checks"], {})
    return row


def detail(deliverable_id: str, space_id: str) -> dict | None:
    d = get(deliverable_id, space_id)
    if not d:
        return None
    d["version"] = get_version(deliverable_id)
    d["versions"] = db.query("SELECT version, author, note, content_hash, created_at FROM deliverable_versions WHERE deliverable_id=? ORDER BY version DESC", (deliverable_id,))
    d["comments"] = db.query("SELECT * FROM comments WHERE deliverable_id=? ORDER BY created_at", (deliverable_id,))
    d["approvals"] = [dict(a, valid=_is_valid(a, d, d["version"])) for a in db.query("SELECT * FROM approvals WHERE deliverable_id=? ORDER BY created_at DESC", (deliverable_id,))]
    src_ids = d["version"]["content"].get("source_ids") or []
    d["sources"] = db.query(f"SELECT id,url,title,provider,query,snippet,published_at,fetched_at,status,note FROM sources WHERE id IN ({','.join('?' * len(src_ids))})", src_ids) if src_ids else []
    return d


def list_deliverables(space_id: str, *, status: str | None = None, kind: str | None = None, archived: bool = False) -> list[dict]:
    sql, params = "SELECT * FROM deliverables WHERE space_id=? AND archived=?", [space_id, int(archived)]
    for col, val in (("status", status), ("kind", kind)):
        if val:
            sql += f" AND {col}=?"
            params.append(val)
    return [_deliv(r) for r in db.query(sql + " ORDER BY updated_at DESC", params)]


def create(space_id: str, kind: str, title: str, content: dict, *, author: str = "usuario", job_id: str | None = None,
           project_id: str | None = None, brand_id: str | None = None, ref_id: str | None = None, note: str = "Versión inicial") -> dict:
    if kind not in KINDS:
        raise ReviewError("Tipo de entregable desconocido.")
    content = normalize(content)
    did = new_id("ent")
    with db.tx() as conn:
        conn.execute("INSERT INTO deliverables(id,space_id,kind,title,status,current_version,project_id,brand_id,job_id,ref_id,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                     (did, space_id, kind, title[:300], "borrador", 1, project_id, brand_id, job_id, ref_id, now_iso(), now_iso()))
        conn.execute("INSERT INTO deliverable_versions(id,deliverable_id,version,content,content_hash,author,note,checks,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (new_id("ver"), did, 1, dumps(content), content_hash(content), author, note, dumps(run_checks(kind, content, space_id)), now_iso()))
    return get(did)


def add_version(deliverable_id: str, space_id: str, content: dict, *, author: str = "usuario", note: str = "", title: str | None = None) -> dict:
    """Cualquier cambio de contenido crea una versión nueva e invalida las aprobaciones anteriores."""
    d = get(deliverable_id, space_id)
    if not d:
        raise KeyError(deliverable_id)
    content = normalize(content)
    current = get_version(deliverable_id)
    if content_hash(content) == current["content_hash"] and (title is None or title == d["title"]):
        return d
    version = d["current_version"] + 1
    with db.tx() as conn:
        conn.execute("INSERT INTO deliverable_versions(id,deliverable_id,version,content,content_hash,author,note,checks,created_at) VALUES(?,?,?,?,?,?,?,?,?)",
                     (new_id("ver"), deliverable_id, version, dumps(content), content_hash(content), author, note, dumps(run_checks(d["kind"], content, space_id)), now_iso()))
        conn.execute("UPDATE deliverables SET current_version=?, status='borrador', title=COALESCE(?,title), updated_at=? WHERE id=?", (version, title, now_iso(), deliverable_id))
        conn.execute("UPDATE approvals SET revoked_at=?, revoke_reason='El contenido cambió (nueva versión)' WHERE deliverable_id=? AND revoked_at IS NULL", (now_iso(), deliverable_id))
    return get(deliverable_id)


def set_status(deliverable_id: str, space_id: str, status: str) -> dict:
    if status not in STATUSES or not get(deliverable_id, space_id):
        raise ReviewError("Estado o entregable no válido.")
    db.execute("UPDATE deliverables SET status=?, updated_at=? WHERE id=?", (status, now_iso(), deliverable_id))
    return get(deliverable_id)


def comment(deliverable_id: str, space_id: str, body: str, *, kind: str = "comentario", author: str = "usuario") -> dict:
    d = get(deliverable_id, space_id)
    if not d or not body.strip():
        raise ReviewError("Comentario vacío o entregable inexistente.")
    cid = new_id("com")
    db.execute("INSERT INTO comments(id,deliverable_id,version,author,body,kind,created_at) VALUES(?,?,?,?,?,?,?)",
               (cid, deliverable_id, d["current_version"], author, body.strip(), kind, now_iso()))
    if kind == "cambio_solicitado":
        set_status(deliverable_id, space_id, "cambios_solicitados")
    return db.one("SELECT * FROM comments WHERE id=?", (cid,))


def approve(deliverable_id: str, space_id: str, *, version: int, user: str, action: str = "version", destination: str = "",
            scope: str = "", expires_hours: float = 72) -> dict:
    """La aprobación queda ligada a usuario, acción, versión (hash), destino, alcance y caducidad."""
    d = get(deliverable_id, space_id)
    if not d:
        raise KeyError(deliverable_id)
    if version != d["current_version"]:
        raise ReviewError(f"Solo se puede aprobar la versión vigente (v{d['current_version']}); pediste v{version}.")
    if action not in ("version", "envio_externo"):
        raise ReviewError("Acción de aprobación no reconocida.")
    if action == "envio_externo" and not destination:
        raise ReviewError("Una aprobación de envío externo debe indicar el destino.")
    v = get_version(deliverable_id)
    aid = new_id("apr")
    db.execute("INSERT INTO approvals(id,deliverable_id,version,content_hash,user,action,destination,scope,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
               (aid, deliverable_id, version, v["content_hash"], user, action, destination, scope, iso_in(expires_hours * 3600), now_iso()))
    if action == "version":
        set_status(deliverable_id, space_id, "aprobado")
    db.audit("aprobacion.crear", deliverable_id, {"version": version, "accion": action, "destino": destination}, actor=user)
    return db.one("SELECT * FROM approvals WHERE id=?", (aid,))


def _is_valid(a: dict, d: dict, v: dict) -> bool:
    return (not a["revoked_at"] and a["version"] == d["current_version"] and a["content_hash"] == v["content_hash"]
            and (not a["expires_at"] or a["expires_at"] > now_iso()))


def find_valid_approval(deliverable_id: str, action: str, destination: str = "") -> dict | None:
    d, v = get(deliverable_id), get_version(deliverable_id)
    if not d or not v:
        return None
    for a in db.query("SELECT * FROM approvals WHERE deliverable_id=? AND action=? ORDER BY created_at DESC", (deliverable_id, action)):
        if _is_valid(a, d, v) and a["destination"] == destination:
            return a
    return None


def revoke(approval_id: str, reason: str = "Revocada por el usuario") -> None:
    db.execute("UPDATE approvals SET revoked_at=?, revoke_reason=? WHERE id=? AND revoked_at IS NULL", (now_iso(), reason, approval_id))


def reject(deliverable_id: str, space_id: str, reason: str, user: str) -> dict:
    comment(deliverable_id, space_id, reason or "Rechazado", kind="rechazo", author=user)
    db.execute("UPDATE approvals SET revoked_at=?, revoke_reason='Entregable rechazado' WHERE deliverable_id=? AND revoked_at IS NULL", (now_iso(), deliverable_id))
    return set_status(deliverable_id, space_id, "rechazado")


# ---------- Render y exportación

def render_markdown(d: dict, v: dict, sources: list[dict] | None = None) -> str:
    c = v["content"]
    out = [f"# {d['title']}", "", f"_{KINDS.get(d['kind'], KINDS['documento'])['label']} · versión {v['version']} · {v['created_at']} · estado: {d['status']}_", ""]
    if c.get("summary"):
        out += [c["summary"], ""]
    for s in c["sections"]:
        out += [f"## {s['title']}", ""]
        if s["body"]:
            out += [s["body"], ""]
        if s["type"] == "list":
            out += [f"- {it}" for it in s["items"]] + [""]
        elif s["type"] == "facts":
            for it in s["items"]:
                tag = {"hecho": "HECHO", "hipotesis": "HIPÓTESIS", "desconocido": "DESCONOCIDO"}.get(it.get("kind"), "NOTA")
                line = f"- **[{tag}]** {it.get('claim', '')}"
                if it.get("signal"):
                    line += f" _(señal: {it['signal']})_"
                out.append(line)
                if it.get("evidence"):
                    out.append(f"  - Evidencia: «{it['evidence']}»")
                if it.get("source_ids"):
                    out.append(f"  - Fuentes: {', '.join(it['source_ids'])}")
                if it.get("limitations"):
                    out.append(f"  - Limitaciones: {it['limitations']}")
            out.append("")
        elif s["type"] == "scores":
            out += [f"- **{it.get('label')}**: {it.get('value')}/5 — {it.get('rationale', '')}" for it in s["items"]] + [""]
        elif s["type"] == "table" and s["columns"]:
            esc = lambda x: str(x if x is not None else "").replace("|", "\\|").replace("\n", "<br>")
            out.append("| " + " | ".join(esc(x) for x in s["columns"]) + " |")
            out.append("|" + "---|" * len(s["columns"]))
            out += ["| " + " | ".join(esc(x) for x in row) + " |" for row in s["rows"]] + [""]
        elif s["type"] == "files":
            out += [f"- {it.get('name')} ({it.get('file_id')}){' — ' + it['note'] if it.get('note') else ''}" for it in s["items"]] + [""]
        if s["note"]:
            out += [f"> {s['note']}", ""]
    if sources:
        out += ["## Fuentes consultadas", ""]
        for src in sources:
            pub = f", publicada {src['published_at']}" if src.get("published_at") else ", fecha de publicación no disponible"
            out.append(f"- `{src['id']}` [{src.get('title') or src.get('url')}]({src.get('url')}) — consultada {src.get('fetched_at')}{pub}; estado: {src.get('status')}")
        out.append("")
    return "\n".join(out)


def export(deliverable_id: str, space_id: str, fmt: str = "md") -> dict:
    """Exportación local (reversible, no requiere aprobación). Devuelve rutas dentro de exports/."""
    d = detail(deliverable_id, space_id)
    if not d:
        raise KeyError(deliverable_id)
    v = d["version"]
    base = config.exports_dir() / sanitize_filename(space_id) / f"{deliverable_id}_v{v['version']}"
    base.mkdir(parents=True, exist_ok=True)
    slug = sanitize_filename(d["title"]).replace(" ", "_")[:60] or "entregable"
    written = []
    if fmt == "md":
        p = base / f"{slug}.md"
        p.write_text(render_markdown(d, v, d["sources"]), encoding="utf-8")
        written.append(p)
    elif fmt == "json":
        p = base / f"{slug}.json"
        p.write_text(dumps({"entregable": {k: d[k] for k in ("id", "kind", "title", "status", "current_version", "project_id", "brand_id", "ref_id")},
                            "version": {k: v[k] for k in ("version", "content_hash", "author", "created_at")}, "contenido": v["content"],
                            "fuentes": d["sources"], "comprobaciones": v["checks"]}), encoding="utf-8")
        written.append(p)
    elif fmt == "csv":
        for s in v["content"]["sections"]:
            if s["type"] == "table" and s["columns"]:
                buf = io.StringIO()
                w = csv.writer(buf)
                w.writerow(s["columns"])
                w.writerows(s["rows"])
                p = base / f"{slug}_{sanitize_filename(s['key'])}.csv"
                p.write_text(buf.getvalue(), encoding="utf-8-sig")
                written.append(p)
        if not written:
            raise ReviewError("Este entregable no contiene tablas exportables a CSV.")
    elif fmt == "archivos":
        for s in v["content"]["sections"]:
            if s["type"] == "files":
                for it in s["items"]:
                    f = files.get(it.get("file_id"), space_id)
                    if f:
                        p = base / sanitize_filename(f["name"])
                        shutil.copyfile(files.path_of(f), p)
                        written.append(p)
        if not written:
            raise ReviewError("Este entregable no tiene archivos adjuntos.")
    else:
        raise ReviewError("Formato de exportación no soportado.")
    db.audit("entregable.exportar", deliverable_id, {"formato": fmt, "version": v["version"]})
    root = config.exports_dir()
    return {"formato": fmt, "version": v["version"], "archivos": [str(p.relative_to(root)).replace("\\", "/") for p in written], "carpeta": str(base)}


def diff(deliverable_id: str, space_id: str, a: int, b: int) -> dict:
    d = get(deliverable_id, space_id)
    va, vb = get_version(deliverable_id, a), get_version(deliverable_id, b)
    if not d or not va or not vb:
        raise KeyError(deliverable_id)
    la, lb = render_markdown(d, va).splitlines()[3:], render_markdown(d, vb).splitlines()[3:]
    lines = list(difflib.unified_diff(la, lb, f"v{a}", f"v{b}", lineterm="", n=2))
    return {"a": a, "b": b, "diff": lines, "iguales": va["content_hash"] == vb["content_hash"]}


TEMPLATES = {
    "proposal": lambda: {"summary": "", "sections": [
        {"key": "observacion", "title": "Observación verificable", "type": "text", "body": "[pendiente: observación con su fuente]"},
        {"key": "muestra", "title": "Muestra gratuita limitada", "type": "list", "items": ["Entregable: [pendiente]", "Tiempo máximo: [pendiente]", "Revisiones: [pendiente]", "Límites: [pendiente]"]},
        {"key": "oferta", "title": "Oferta pagada", "type": "list", "items": ["Problema: [pendiente]", "Objetivo: [pendiente]", "Entregables: [pendiente]", "Exclusiones: [pendiente]", "Insumos necesarios: [pendiente]", "Plazo: [pendiente]", "Revisiones: [pendiente]", "Criterio de aceptación: [pendiente]", "Precio: [precio por definir]"]},
        {"key": "mensaje", "title": "Mensaje (borrador, no enviado)", "type": "text", "body": "[pendiente]"}]},
    "documento": lambda: {"summary": "", "sections": [{"key": "contenido", "title": "Contenido", "type": "text", "body": ""}]},
}
