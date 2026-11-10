"""Cola persistente de trabajos en SQLite."""
from __future__ import annotations

from . import db
from .router import DEFAULT_LIMITS
from .util import canonical_json, dumps, iso_in, loads, new_id, now_iso, sha256_text

ACTIVE = ("pending", "running", "waiting_config", "waiting_quota", "waiting_approval")
TERMINAL = ("completed", "failed", "cancelled")
STATUS_LABELS = {
    "pending": "Pendiente", "running": "Ejecutando", "waiting_config": "Esperando configuración",
    "waiting_quota": "Esperando cuota", "waiting_approval": "Esperando aprobación",
    "completed": "Completado", "failed": "Fallido", "cancelled": "Cancelado",
}
STALE_SECONDS = 45


class Cancelled(Exception):
    pass


class JobError(Exception):
    """Error explicable al usuario. retryable=False evita reintentos inútiles."""

    def __init__(self, message: str, retryable: bool = False):
        super().__init__(message)
        self.message, self.retryable = message, retryable


class ApprovalRequired(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def _row(row: dict | None) -> dict | None:
    if not row:
        return None
    for k in ("params", "result", "limits", "usage"):
        row[k] = loads(row[k], {} if k != "result" else None)
    row["status_label"] = STATUS_LABELS.get(row["status"], row["status"])
    row["cancel_requested"] = bool(row["cancel_requested"])
    return row


def get(job_id: str) -> dict | None:
    return _row(db.one("SELECT * FROM jobs WHERE id=?", (job_id,)))


def list_jobs(space_id: str | None = None, status: str | None = None, limit: int = 100) -> list[dict]:
    sql, params = "SELECT * FROM jobs WHERE 1=1", []
    if space_id:
        sql += " AND space_id=?"
        params.append(space_id)
    if status == "active":
        sql += f" AND status IN ({','.join('?' * len(ACTIVE))})"
        params += ACTIVE
    elif status:
        sql += " AND status=?"
        params.append(status)
    return [_row(r) for r in db.query(sql + " ORDER BY created_at DESC, rowid DESC LIMIT ?", (*params, limit))]


def add_event(job_id: str, kind: str, message: str, stage: str | None = None, data: dict | None = None) -> None:
    db.execute("INSERT INTO job_events(job_id,ts,kind,stage,message,data) VALUES(?,?,?,?,?,?)",
               (job_id, now_iso(), kind, stage, message, dumps(data or {})))


def events(job_id: str, after: int = 0) -> list[dict]:
    rows = db.query("SELECT * FROM job_events WHERE job_id=? AND id>? ORDER BY id", (job_id, after))
    for r in rows:
        r["data"] = loads(r["data"], {})
    return rows


def enqueue(space_id: str, type_: str, title: str, params: dict, *, idempotency_key: str | None = None,
            limits: dict | None = None, max_attempts: int = 2) -> tuple[dict, bool]:
    """Devuelve (trabajo, creado). Si ya existe uno activo equivalente, lo reutiliza en vez de duplicar."""
    key = idempotency_key or sha256_text(canonical_json([space_id, type_, params]))
    lim = {**DEFAULT_LIMITS, **{k: v for k, v in (limits or {}).items() if k in DEFAULT_LIMITS and v}}
    with db.tx(immediate=True) as conn:
        row = conn.execute(f"SELECT id FROM jobs WHERE idempotency_key=? AND status IN ({','.join('?' * len(ACTIVE))})", (key, *ACTIVE)).fetchone()
        if row:
            job_id, created = row["id"], False
        else:
            job_id, created = new_id("job"), True
            conn.execute("INSERT INTO jobs(id,space_id,type,title,params,status,idempotency_key,limits,max_attempts,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                         (job_id, space_id, type_, title, dumps(params), "pending", key, dumps(lim), max_attempts, now_iso(), now_iso()))
    if created:
        add_event(job_id, "estado", "Trabajo creado y en cola")
    return get(job_id), created


def claim(worker_id: str, exclude_types: tuple[str, ...] = ()) -> dict | None:
    with db.tx(immediate=True) as conn:
        sql = "SELECT id FROM jobs WHERE (status='pending' OR (status='waiting_quota' AND resume_at IS NOT NULL AND resume_at<=?)) AND (resume_at IS NULL OR resume_at<=?)"
        params: list = [now_iso(), now_iso()]
        if exclude_types:
            sql += f" AND type NOT IN ({','.join('?' * len(exclude_types))})"
            params += exclude_types
        row = conn.execute(sql + " ORDER BY created_at, rowid LIMIT 1", params).fetchone()
        if not row:
            return None
        conn.execute("UPDATE jobs SET status='running', worker_id=?, heartbeat_at=?, started_at=COALESCE(started_at,?), attempts=attempts+1, resume_at=NULL, error=NULL, updated_at=? WHERE id=?",
                     (worker_id, now_iso(), now_iso(), now_iso(), row["id"]))
        job_id = row["id"]
    add_event(job_id, "estado", "Ejecución iniciada")
    return get(job_id)


def heartbeat(job_id: str) -> bool:
    """Actualiza el latido y devuelve True si se pidió cancelar."""
    db.execute("UPDATE jobs SET heartbeat_at=? WHERE id=? AND status='running'", (now_iso(), job_id))
    row = db.one("SELECT cancel_requested FROM jobs WHERE id=?", (job_id,))
    return bool(row and row["cancel_requested"])


def set_progress(job_id: str, stage: str, progress: float, message: str = "") -> None:
    db.execute("UPDATE jobs SET stage=?, progress=?, message=?, updated_at=? WHERE id=?", (stage, max(0.0, min(1.0, progress)), message, now_iso(), job_id))
    add_event(job_id, "etapa", message or stage, stage, {"progress": round(progress, 3)})


def finish(job_id: str, status: str, *, result=None, error: str | None = None, message: str = "", resume_at: str | None = None, usage: dict | None = None) -> None:
    terminal = status in TERMINAL
    db.execute("""UPDATE jobs SET status=?, result=COALESCE(?,result), error=?, message=?, resume_at=?, usage=COALESCE(?,usage),
                  finished_at=?, progress=CASE WHEN ?='completed' THEN 1 ELSE progress END, cancel_requested=0, worker_id=NULL, updated_at=? WHERE id=?""",
               (status, dumps(result) if result is not None else None, error, message, resume_at, dumps(usage) if usage else None,
                now_iso() if terminal else None, status, now_iso(), job_id))
    add_event(job_id, "estado", f"{STATUS_LABELS[status]}" + (f": {error or message}" if (error or message) else ""))


def request_cancel(job_id: str) -> dict:
    job = get(job_id)
    if not job:
        raise KeyError(job_id)
    if job["status"] in TERMINAL:
        return job
    if job["status"] == "running":
        db.execute("UPDATE jobs SET cancel_requested=1, message='Cancelación solicitada', updated_at=? WHERE id=?", (now_iso(), job_id))
        add_event(job_id, "estado", "Cancelación solicitada; se detendrá en el siguiente punto seguro")
    else:
        finish(job_id, "cancelled", message="Cancelado por el usuario antes de ejecutarse")
    return get(job_id)


def retry(job_id: str) -> dict:
    job = get(job_id)
    if not job:
        raise KeyError(job_id)
    if job["status"] in ("running", "pending"):
        return job
    try:
        db.execute("UPDATE jobs SET status='pending', attempts=0, error=NULL, resume_at=NULL, finished_at=NULL, cancel_requested=0, message='Reintento solicitado', updated_at=? WHERE id=?", (now_iso(), job_id))
    except Exception:
        raise JobError("Ya existe un trabajo activo equivalente; no se duplicó.")
    add_event(job_id, "estado", "Reintento solicitado por el usuario")
    return get(job_id)


def recover_stale(stale_seconds: int = STALE_SECONDS) -> list[str]:
    """Trabajos que quedaron 'ejecutando' sin latido (cierre o caída): vuelven a la cola o fallan si agotaron intentos."""
    cutoff = iso_in(-stale_seconds)
    recovered = []
    for row in db.query("SELECT id, attempts, max_attempts FROM jobs WHERE status='running' AND (heartbeat_at IS NULL OR heartbeat_at<?)", (cutoff,)):
        if row["attempts"] >= row["max_attempts"]:
            finish(row["id"], "failed", error="El trabajo se interrumpió (cierre o caída del worker) y agotó sus reintentos.")
        else:
            db.execute("UPDATE jobs SET status='pending', worker_id=NULL, message='Recuperado tras interrupción', updated_at=? WHERE id=?", (now_iso(), row["id"]))
            add_event(row["id"], "estado", "Recuperado tras interrupción del worker; vuelve a la cola")
        recovered.append(row["id"])
    return recovered
