"""Fusión de datos: trae a la base única lo que se guardó cuando Doomsday corría aparte (carpeta `doomsday_home/`).

Solo añade: copia filas cuyo identificador no existe todavía y archivos que faltan. No borra ni pisa nada, y la carpeta antigua queda intacta.
"""
from __future__ import annotations
import shutil
import sqlite3
from pathlib import Path

from jarvis import config, db
from jarvis.util import loads, now_iso

TABLES = ("spaces", "connections", "records", "files", "sources", "deliverables", "deliverable_versions", "comments")


def import_old_home(old: Path | None = None) -> list[str]:
    old = old or config.REPO_ROOT / "doomsday_home"
    old_db = old / "data" / "jarvis.db"
    if not old_db.is_file() or old.resolve() == config.home().resolve() or db.get_setting("dd_fusion"):
        return []
    db.migrate()
    conn = db.connect()
    counts: dict[str, int] = {}
    try:
        conn.execute("ATTACH DATABASE ? AS viejo", (str(old_db),))
        v_new = conn.execute("SELECT MAX(version) v FROM main.schema_migrations").fetchone()["v"]
        try:
            v_old = conn.execute("SELECT MAX(version) v FROM viejo.schema_migrations").fetchone()["v"]
        except sqlite3.Error:
            v_old = None
        if v_old != v_new:
            return [f"No se importaron los datos antiguos de Doomsday: su base es de otra versión ({v_old} frente a {v_new}). Siguen intactos en {old}."]
        conn.execute("BEGIN IMMEDIATE")
        for t in TABLES:
            before = conn.execute(f"SELECT COUNT(*) c FROM main.{t}").fetchone()["c"]
            conn.execute(f"INSERT OR IGNORE INTO main.{t} SELECT * FROM viejo.{t}")
            counts[t] = conn.execute(f"SELECT COUNT(*) c FROM main.{t}").fetchone()["c"] - before
        capas = conn.execute("SELECT value FROM viejo.settings WHERE key='dd_spaces'").fetchone()
        if capas and not conn.execute("SELECT 1 FROM main.settings WHERE key='dd_spaces'").fetchone():
            conn.execute("INSERT INTO main.settings(key,value) VALUES('dd_spaces',?)", (capas["value"],))
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()
    copied = 0
    for sub, dest in (("data/files", config.files_dir()), ("skills", config.home() / "skills")):
        src = old / sub
        if src.is_dir():
            for f in src.rglob("*"):
                target = dest / f.relative_to(src)
                if f.is_file() and not target.exists():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(f, target)
                    copied += 1
    db.set_setting("dd_fusion", {"fecha": now_iso(), "origen": str(old), **counts, "archivos": copied})
    db.audit("dd_fusion", str(old), {**counts, "archivos": copied})
    total = sum(counts.values())
    capas_txt = ", ".join(sorted((loads(capas["value"], {}) or {}).keys())) if capas else ""
    return [f"Datos de Doomsday importados a la base única: {counts['records']} registros, {counts['deliverables']} entregables, {counts['spaces']} espacios, "
            f"{counts['connections']} conexiones y {copied} archivos ({total} filas en total{'; capas: ' + capas_txt if capas_txt else ''}). La carpeta {old} queda intacta."]
