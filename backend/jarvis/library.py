"""Biblioteca de conocimiento: documentos Markdown en content/ (guías, habilidades, modelos…). Solo lectura."""
from __future__ import annotations
import json
import re
from pathlib import Path

from . import config
from .security import SecurityError, safe_join


def root() -> Path:
    return config.REPO_ROOT / "content"


def _title(path: Path) -> str:
    return path.stem.replace("_", " ")


def tree() -> list[dict]:
    out = []
    base = root()
    if not base.is_dir():
        return out
    for d in sorted(p for p in base.iterdir() if p.is_dir()):
        meta = {}
        if (d / "_meta.json").is_file():
            try:
                meta = json.loads((d / "_meta.json").read_text(encoding="utf-8"))
            except ValueError:
                meta = {}
        order = meta.get("orden") or []
        docs = [{"path": f"{d.name}/{f.name}", "title": _title(f)} for f in d.glob("*.md")]
        docs.sort(key=lambda x: (order.index(Path(x["path"]).name) if Path(x["path"]).name in order else 999, x["title"].lower()))
        files = [{"path": f"{d.name}/{f.name}", "name": f.name} for f in sorted(d.glob("*.pdf"))]
        out.append({"id": d.name, "title": meta.get("titulo") or d.name, "group": meta.get("grupo") or "Biblioteca", "description": meta.get("descripcion") or "",
                    "origin": meta.get("origen") or "", "docs": docs, "files": files, "position": meta.get("posicion", 50)})
    out.sort(key=lambda c: (c["position"], c["title"]))
    return out


def _resolve(rel: str, suffix: str) -> Path:
    p = safe_join(root(), rel)
    if p.suffix.lower() != suffix or not p.is_file():
        raise KeyError(rel)
    return p


def doc(rel: str) -> dict:
    p = _resolve(rel, ".md")
    return {"path": rel, "title": _title(p), "markdown": p.read_text(encoding="utf-8")}


def file_path(rel: str) -> Path:
    return _resolve(rel, ".pdf")


def search(q: str, limit: int = 30) -> list[dict]:
    q = (q or "").strip().lower()
    if len(q) < 2:
        return []
    hits = []
    for col in tree():
        for d in col["docs"]:
            text = (root() / d["path"]).read_text(encoding="utf-8")
            low = text.lower()
            n = low.count(q) + (5 if q in d["title"].lower() else 0)
            if n:
                i = max(low.find(q), 0)
                snippet = re.sub(r"\s+", " ", text[max(0, i - 70): i + 130]).strip()
                hits.append({"path": d["path"], "title": d["title"], "collection": col["title"], "matches": n, "snippet": snippet})
    hits.sort(key=lambda h: -h["matches"])
    return hits[:limit]
