"""Almacenamiento local de archivos con IDs y rutas controladas."""
from __future__ import annotations
import hashlib
import mimetypes
import shutil
from pathlib import Path

from . import config, db
from .security import SecurityError, safe_join, sanitize_filename
from .util import dumps, loads, new_id, now_iso

ALLOWED_EXT = {
    ".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi", ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac",
    ".png", ".jpg", ".jpeg", ".webp", ".gif", ".srt", ".vtt", ".txt", ".md", ".csv", ".json", ".pdf", ".html", ".htm", ".zip",
}


def _row(row):
    if row:
        row["meta"] = loads(row["meta"], {})
    return row


def get(file_id: str, space_id: str | None = None) -> dict | None:
    row = _row(db.one("SELECT * FROM files WHERE id=?", (file_id,)))
    if row and space_id and row["space_id"] != space_id:
        return None
    return row


def path_of(file_row: dict) -> Path:
    return safe_join(config.files_dir(), file_row["rel_path"])


def list_files(space_id: str, origin: str | None = None) -> list[dict]:
    sql, params = "SELECT * FROM files WHERE space_id=? AND archived=0", [space_id]
    if origin:
        sql += " AND origin=?"
        params.append(origin)
    return [_row(r) for r in db.query(sql + " ORDER BY created_at DESC", params)]


def check_name(name: str) -> str:
    clean = sanitize_filename(name)
    ext = Path(clean).suffix.lower()
    if ext not in ALLOWED_EXT:
        raise SecurityError(f"Tipo de archivo no permitido ({ext or 'sin extensión'}).")
    return clean


def new_path(space_id: str, name: str) -> tuple[str, str, Path]:
    file_id = new_id("fil")
    rel = f"{space_id}/{file_id}{Path(name).suffix.lower()}"
    dest = safe_join(config.files_dir(), rel)
    dest.parent.mkdir(parents=True, exist_ok=True)
    return file_id, rel, dest


def register(space_id: str, file_id: str, rel: str, name: str, *, origin: str = "upload", job_id: str | None = None, meta: dict | None = None) -> dict:
    path = safe_join(config.files_dir(), rel)
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    db.execute("INSERT INTO files(id,space_id,name,mime,size,sha256,rel_path,origin,job_id,meta,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
               (file_id, space_id, name, mime, path.stat().st_size, h.hexdigest(), rel, origin, job_id, dumps(meta or {}), now_iso()))
    return get(file_id)


def save_stream(space_id: str, name: str, stream, max_bytes: int = config.MAX_UPLOAD_BYTES, origin: str = "upload") -> dict:
    name = check_name(name)
    file_id, rel, dest = new_path(space_id, name)
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = stream.read(1 << 20)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise SecurityError(f"El archivo supera el tamaño máximo permitido ({max_bytes // (1024 * 1024)} MB).")
                out.write(chunk)
    except BaseException:
        dest.unlink(missing_ok=True)
        raise
    return register(space_id, file_id, rel, name, origin=origin)


def save_bytes(space_id: str, name: str, content: bytes, *, origin: str = "job", job_id: str | None = None, meta: dict | None = None) -> dict:
    name = check_name(name)
    file_id, rel, dest = new_path(space_id, name)
    dest.write_bytes(content)
    return register(space_id, file_id, rel, name, origin=origin, job_id=job_id, meta=meta)


def adopt(space_id: str, src: Path, name: str, *, job_id: str | None = None, meta: dict | None = None) -> dict:
    """Mueve al almacén un archivo generado en el directorio de trabajo."""
    name = check_name(name)
    file_id, rel, dest = new_path(space_id, name)
    shutil.move(str(src), dest)
    return register(space_id, file_id, rel, name, origin="job", job_id=job_id, meta=meta)


def set_meta(file_id: str, meta: dict) -> None:
    db.execute("UPDATE files SET meta=? WHERE id=?", (dumps(meta), file_id))


def archive(file_id: str) -> None:
    db.execute("UPDATE files SET archived=1 WHERE id=?", (file_id,))
