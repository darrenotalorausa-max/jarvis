"""Rutas y ajustes base. Todo se resuelve en tiempo de llamada para que las pruebas puedan aislar JARVIS_HOME."""
from __future__ import annotations
import os
from pathlib import Path

APP_VERSION = "0.1.0"
REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_env_file() -> None:
    """Lee .env de la raíz (opcional). Solo acepta variables JARVIS_* y no pisa las ya definidas. Nunca contiene credenciales."""
    path = REPO_ROOT / ".env"
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            key = key.strip()
            if key.startswith("JARVIS_") and key not in os.environ:
                os.environ[key] = value.strip().strip('"').strip("'")


_load_env_file()


def home() -> Path:
    return Path(os.environ.get("JARVIS_HOME") or REPO_ROOT)


def data_dir() -> Path:
    return home() / "data"


def files_dir() -> Path:
    return data_dir() / "files"


def work_dir() -> Path:
    return data_dir() / "work"


def exports_dir() -> Path:
    return home() / "exports"


def logs_dir() -> Path:
    return home() / "logs"


def db_path() -> Path:
    return data_dir() / "jarvis.db"


def host() -> str:
    # Loopback por defecto. Exponer a la red exige cambiarlo de forma explícita.
    return os.environ.get("JARVIS_HOST", "127.0.0.1")


def port() -> int:
    return int(os.environ.get("JARVIS_PORT", "8765"))


def ensure_dirs() -> None:
    for d in (data_dir(), files_dir(), work_dir(), exports_dir(), logs_dir()):
        d.mkdir(parents=True, exist_ok=True)


MAX_UPLOAD_BYTES = int(os.environ.get("JARVIS_MAX_UPLOAD_MB", "2048")) * 1024 * 1024
