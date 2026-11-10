"""Respaldo y restauración. Los secretos no viven en la base de datos ni en data/, así que nunca entran en un respaldo."""
from __future__ import annotations
import hashlib
import json
import shutil
import sqlite3
import zipfile
from pathlib import Path

from . import config, db
from .security import SecurityError
from .util import now, now_iso

FORMAT = "jarvis-os-backup"


def backups_dir() -> Path:
    d = config.exports_dir() / "backups"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _sha(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def create(include_files: bool = True, label: str = "manual") -> dict:
    stamp = now().strftime("%Y%m%d-%H%M%S")
    out = backups_dir() / f"jarvis-backup-{label}-{stamp}.zip"
    tmp_db = config.work_dir() / f"backup-{stamp}.db"
    src = db.connect()
    try:
        dst = sqlite3.connect(tmp_db)
        with dst:
            src.backup(dst)  # copia consistente aunque haya escrituras en curso
        dst.close()
    finally:
        src.close()
    manifest = {"formato": FORMAT, "version_app": config.APP_VERSION, "version_esquema": db.schema_version(), "creado": now_iso(),
                "incluye_archivos": include_files, "incluye_secretos": False, "db_sha256": _sha(tmp_db), "archivos": []}
    counts = {t: db.one(f"SELECT COUNT(*) c FROM {t}")["c"] for t in ("spaces", "records", "deliverables", "jobs", "files", "connections")}
    manifest["conteos"] = counts
    try:
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as z:
            z.write(tmp_db, "db/jarvis.db")
            if include_files:
                root = config.files_dir()
                for p in sorted(root.rglob("*")):
                    if p.is_file():
                        rel = p.relative_to(root).as_posix()
                        manifest["archivos"].append({"ruta": rel, "bytes": p.stat().st_size, "sha256": _sha(p)})
                        z.write(p, f"files/{rel}")
            z.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    finally:
        tmp_db.unlink(missing_ok=True)
    db.audit("respaldo.crear", out.name, {"archivos": len(manifest["archivos"])})
    return {"archivo": out.name, "ruta": str(out), "bytes": out.stat().st_size, "manifiesto": {k: v for k, v in manifest.items() if k != "archivos"},
            "archivos_incluidos": len(manifest["archivos"])}


def list_backups() -> list[dict]:
    return [{"archivo": p.name, "bytes": p.stat().st_size, "modificado": p.stat().st_mtime} for p in sorted(backups_dir().glob("*.zip"), reverse=True)]


def inspect(path: Path) -> dict:
    """Valida un respaldo sin aplicarlo. Lanza SecurityError si no es seguro o íntegro."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError):
        raise SecurityError("El archivo no es un respaldo ZIP válido.")
    with z:
        names = z.namelist()
        for n in names:
            if n.startswith("/") or ".." in Path(n).parts or "\\" in n:
                raise SecurityError("El respaldo contiene rutas no permitidas.")
        if "manifest.json" not in names or "db/jarvis.db" not in names:
            raise SecurityError("El respaldo no contiene manifiesto o base de datos.")
        try:
            manifest = json.loads(z.read("manifest.json"))
        except ValueError:
            raise SecurityError("El manifiesto del respaldo está dañado.")
        if manifest.get("formato") != FORMAT:
            raise SecurityError("El archivo no es un respaldo de Jarvis OS.")
        if int(manifest.get("version_esquema", 0)) > max(v for v, _ in db.available_migrations()):
            raise SecurityError("El respaldo procede de una versión más nueva de Jarvis OS; actualiza la aplicación antes de restaurar.")
        if hashlib.sha256(z.read("db/jarvis.db")).hexdigest() != manifest.get("db_sha256"):
            raise SecurityError("La base de datos del respaldo no coincide con su huella: archivo dañado o alterado.")
        listed = {a["ruta"]: a for a in manifest.get("archivos", [])}
        present = {n[len("files/"):] for n in names if n.startswith("files/") and not n.endswith("/")}
        if present != set(listed):
            raise SecurityError("Los archivos del respaldo no coinciden con el manifiesto.")
        for rel, meta in listed.items():
            h = hashlib.sha256()
            with z.open(f"files/{rel}") as fh:
                for chunk in iter(lambda: fh.read(1 << 20), b""):
                    h.update(chunk)
            if h.hexdigest() != meta["sha256"]:
                raise SecurityError(f"El archivo {rel} del respaldo está dañado.")
    current = {t: db.one(f"SELECT COUNT(*) c FROM {t}")["c"] for t in ("spaces", "records", "deliverables", "jobs", "files", "connections")}
    return {"valido": True, "manifiesto": {k: v for k, v in manifest.items() if k != "archivos"}, "archivos": len(listed), "datos_actuales": current,
            "aviso": "Restaurar reemplaza TODOS los datos actuales por los del respaldo. Antes se guarda automáticamente una copia de seguridad del estado actual. "
                     "Las credenciales no forman parte del respaldo: tendrás que volver a introducirlas si este equipo no las conserva."}


def restore(path: Path, confirm: bool) -> dict:
    info = inspect(path)
    if not confirm:
        raise SecurityError("La restauración requiere confirmación explícita.")
    safety = create(include_files=True, label="antes-de-restaurar")
    tmp = config.work_dir() / f"restore-{now().strftime('%Y%m%d%H%M%S')}"
    tmp.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(path) as z:
            z.extract("db/jarvis.db", tmp)
            if info["manifiesto"].get("incluye_archivos"):
                for n in z.namelist():
                    if n.startswith("files/") and not n.endswith("/"):
                        z.extract(n, tmp)
        # Sustituye el contenido de la base activa mediante la API de copia de SQLite (segura con otras conexiones abiertas).
        src = sqlite3.connect(tmp / "db" / "jarvis.db")
        dst = db.connect()
        try:
            src.backup(dst)
        finally:
            src.close()
            dst.close()
        if info["manifiesto"].get("incluye_archivos"):
            old = config.files_dir()
            trash = config.work_dir() / f"files-reemplazados-{now().strftime('%Y%m%d%H%M%S')}"
            if old.exists():
                shutil.move(str(old), trash)
            new = tmp / "files"
            if new.exists():
                shutil.move(str(new), old)
            else:
                old.mkdir(parents=True, exist_ok=True)
            shutil.rmtree(trash, ignore_errors=True)
        db.migrate()
        # Lo que estaba en ejecución en el momento del respaldo vuelve a la cola de forma explícita.
        db.execute("UPDATE jobs SET status='pending', worker_id=NULL, message='Recuperado tras restaurar un respaldo' WHERE status='running'")
        db.audit("respaldo.restaurar", path.name, {"copia_previa": safety["archivo"]})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return {"restaurado": True, "copia_de_seguridad_previa": safety["archivo"], "manifiesto": info["manifiesto"]}
