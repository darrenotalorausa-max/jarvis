"""Las cuatro capas de datos como espacios aislados. Sin dependencias de la API: lo usan la API, el worker y el asistente."""
from __future__ import annotations

from jarvis import db
from jarvis.util import new_id, now_iso

from . import catalog


def ensure_seed() -> dict:
    """Asigna las cuatro capas a espacios. Idempotente. Si Jarvis ya tiene un espacio del tipo de una capa (por ejemplo «Personal» o tu negocio),
    la capa lo reutiliza en vez de crear otro: así los datos de Jarvis y los módulos de Doomsday viven juntos. Solo crea lo que falte."""
    spaces = db.get_setting("dd_spaces", {}) or {}
    for key, (name, kind, _) in catalog.LAYERS.items():
        if key in spaces and db.one("SELECT id FROM spaces WHERE id=?", (spaces[key],)):
            continue
        usados = [v for k, v in spaces.items() if k != key]
        prev = next((r for r in db.query("SELECT id FROM spaces WHERE kind=? AND archived=0 ORDER BY created_at, rowid", (kind,)) if r["id"] not in usados), None)
        if prev:
            spaces[key] = prev["id"]
            continue
        sid = new_id("esp")
        db.execute("INSERT INTO spaces(id,name,kind,ai_policy,created_at,updated_at) VALUES(?,?,?,?,?,?)", (sid, name, kind, "nube_permitida", now_iso(), now_iso()))
        spaces[key] = sid
    db.set_setting("dd_spaces", spaces)
    return spaces


def space_for(mod: dict, current: str | None = None) -> str:
    """Espacio donde trabaja un módulo: el actual si es de su capa; si no, el espacio general de esa capa. Nunca cruza capas."""
    kind = catalog.LAYERS[mod["capa"]][1]
    if current:
        row = db.one("SELECT kind FROM spaces WHERE id=? AND archived=0", (current,))
        if row and row["kind"] == kind:
            return current
    return ensure_seed()[mod["capa"]]
