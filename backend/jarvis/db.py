"""SQLite con migraciones SQL numeradas. Una conexión corta por operación (seguro entre hilos y procesos)."""
from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from . import config
from .util import now_iso

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect() -> sqlite3.Connection:
    config.ensure_dirs()
    conn = sqlite3.connect(config.db_path(), timeout=15, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=15000")
    return conn


@contextmanager
def tx(immediate: bool = False):
    conn = connect()
    try:
        conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield conn
        conn.execute("COMMIT")
    except BaseException:
        try:
            conn.execute("ROLLBACK")
        except sqlite3.Error:
            pass
        raise
    finally:
        conn.close()


def query(sql: str, params=()) -> list[dict]:
    conn = connect()
    try:
        return [dict(r) for r in conn.execute(sql, params).fetchall()]
    finally:
        conn.close()


def one(sql: str, params=()) -> dict | None:
    rows = query(sql, params)
    return rows[0] if rows else None


def execute(sql: str, params=()) -> int:
    with tx() as conn:
        cur = conn.execute(sql, params)
        return cur.lastrowid or cur.rowcount


def schema_version() -> int:
    conn = connect()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY, name TEXT, applied_at TEXT)")
        row = conn.execute("SELECT MAX(version) v FROM schema_migrations").fetchone()
        return row["v"] or 0
    finally:
        conn.close()


def available_migrations() -> list[tuple[int, Path]]:
    out = []
    for p in sorted(MIGRATIONS_DIR.glob("*.sql")):
        out.append((int(p.name.split("_")[0]), p))
    return out


def migrate() -> list[int]:
    """Aplica migraciones pendientes en orden. Cada una es atómica."""
    current = schema_version()
    applied = []
    for version, path in available_migrations():
        if version <= current:
            continue
        conn = connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            for stmt in _split_sql(path.read_text(encoding="utf-8")):
                conn.execute(stmt)
            conn.execute("INSERT INTO schema_migrations(version,name,applied_at) VALUES(?,?,?)", (version, path.name, now_iso()))
            conn.execute("COMMIT")
            applied.append(version)
        except BaseException:
            conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()
    return applied


def _split_sql(text: str) -> list[str]:
    lines = [l for l in text.splitlines() if not l.strip().startswith("--")]
    return [s.strip() for s in "\n".join(lines).split(";") if s.strip()]


def get_setting(key: str, default=None):
    from .util import loads
    row = one("SELECT value FROM settings WHERE key=?", (key,))
    return loads(row["value"], default) if row else default


def set_setting(key: str, value) -> None:
    from .util import dumps
    execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, dumps(value)))


def audit(action: str, target: str = "", detail: dict | None = None, actor: str = "usuario") -> None:
    from .util import dumps
    execute("INSERT INTO audit(ts,actor,action,target,detail) VALUES(?,?,?,?,?)", (now_iso(), actor, action, target, dumps(detail or {})))
