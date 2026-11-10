"""Texto bíblico cargado por el usuario (una traducción de dominio público o con licencia que él tenga). Jarvis no incluye ninguna.

Formatos admitidos:
  - JSON: {"Libro": {"1": {"1": "texto", …}, …}, …}  o  [{"book": "...", "chapter": 1, "verse": 1, "text": "..."}, …]
  - Texto: una línea por versículo, «Libro 1:1<tab o espacio>texto»
"""
from __future__ import annotations
import json
import re

from . import db
from .handlers.common import norm
from .security import SecurityError
from .util import now_iso

_LINE = re.compile(r"^\s*(.+?)\s+(\d+):(\d+)[\t ]+(.+)$")
_REF = re.compile(r"^\s*(.+?)\s+(\d+)(?::(\d+)(?:\s*-\s*(\d+))?)?\s*$")


def load(name: str, raw: str, title: str = "", license_: str = "") -> dict:
    name = re.sub(r"[^A-Za-z0-9_-]", "", name)[:20].upper()
    if not name:
        raise SecurityError("Indica una sigla para la traducción (letras y números).")
    rows, order = [], {}
    add = lambda b, c, v, t: rows.append((name, str(b).strip(), order.setdefault(str(b).strip(), len(order) + 1), int(c), int(v), str(t).strip()))
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            for b, chs in data.items():
                for c, vs in chs.items():
                    for v, t in vs.items():
                        add(b, c, v, t)
        else:
            for it in data:
                add(it["book"], it["chapter"], it["verse"], it["text"])
    except ValueError:
        for line in raw.splitlines():
            m = _LINE.match(line)
            if m:
                add(m.group(1), m.group(2), m.group(3), m.group(4))
    except (KeyError, TypeError, AttributeError):
        raise SecurityError("El JSON no tiene el formato esperado (libro → capítulo → versículo → texto).")
    if len(rows) < 10:
        raise SecurityError("No se reconocieron versículos. Revisa el formato del archivo.")
    with db.tx() as conn:
        conn.execute("DELETE FROM scripture WHERE translation=?", (name,))
        conn.executemany("INSERT OR REPLACE INTO scripture(translation,book,book_order,chapter,verse,text) VALUES(?,?,?,?,?,?)", rows)
        conn.execute("INSERT OR REPLACE INTO scripture_meta(translation,title,license,verses,loaded_at) VALUES(?,?,?,?,?)", (name, title[:120] or name, license_[:200], len(rows), now_iso()))
    return {"translation": name, "verses": len(rows), "books": len(order)}


def translations() -> list[dict]:
    return db.query("SELECT * FROM scripture_meta ORDER BY translation")


def remove(name: str) -> None:
    with db.tx() as conn:
        conn.execute("DELETE FROM scripture WHERE translation=?", (name,))
        conn.execute("DELETE FROM scripture_meta WHERE translation=?", (name,))


def _book(translation: str, wanted: str) -> str | None:
    books = [r["book"] for r in db.query("SELECT DISTINCT book, book_order FROM scripture WHERE translation=? ORDER BY book_order", (translation,))]
    w = norm(wanted)
    return next((b for b in books if norm(b) == w), None) or next((b for b in books if norm(b).startswith(w)), None)


def passage(translation: str, ref: str) -> dict:
    m = _REF.match(ref or "")
    if not m:
        raise SecurityError("Referencia no reconocida. Ejemplos: «Juan 3:16», «Salmos 23», «Romanos 8:28-30».")
    book = _book(translation, m.group(1))
    if not book:
        raise KeyError(ref)
    sql, params = "SELECT chapter, verse, text FROM scripture WHERE translation=? AND book=? AND chapter=?", [translation, book, int(m.group(2))]
    if m.group(3):
        sql += " AND verse BETWEEN ? AND ?"
        params += [int(m.group(3)), int(m.group(4) or m.group(3))]
    rows = db.query(sql + " ORDER BY verse", params)
    if not rows:
        raise KeyError(ref)
    return {"translation": translation, "book": book, "chapter": int(m.group(2)), "verses": rows, "reference": f"{book} {m.group(2)}" + (f":{m.group(3)}" + (f"-{m.group(4)}" if m.group(4) else "") if m.group(3) else "")}


def search(translation: str, q: str, limit: int = 60) -> dict:
    """Concordancia simple: versículos que contienen la palabra o frase."""
    q = (q or "").strip()
    if len(q) < 3:
        return {"total": 0, "results": []}
    like = f"%{q}%"
    total = db.one("SELECT COUNT(*) c FROM scripture WHERE translation=? AND text LIKE ?", (translation, like))["c"]
    rows = db.query("SELECT book, chapter, verse, text FROM scripture WHERE translation=? AND text LIKE ? ORDER BY book_order, chapter, verse LIMIT ?", (translation, like, limit))
    return {"total": total, "results": rows}
