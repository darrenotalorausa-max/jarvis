"""Credenciales solo del lado servidor.

Preferencia: almacén del sistema operativo (keyring: Credential Manager en Windows, Keychain en macOS,
Secret Service en Linux). Si no hay almacén disponible se usa un archivo en el perfil del usuario,
fuera de la carpeta de datos y de los respaldos; esa situación se muestra en la interfaz.
"""
from __future__ import annotations
import json
import os
from pathlib import Path

SERVICE = "jarvis-os"


def _file_path() -> Path:
    return Path(os.environ.get("JARVIS_SECRETS_FILE") or Path.home() / ".jarvis_os" / "secrets.json")


def _keyring():
    if os.environ.get("JARVIS_SECRETS_BACKEND") == "file":
        return None
    try:
        import keyring
        kr = keyring.get_keyring()
        if getattr(kr, "priority", 0) <= 0 or "fail" in type(kr).__module__:
            return None
        return keyring
    except Exception:
        return None


def backend() -> dict:
    if _keyring():
        return {"kind": "sistema", "label": "Almacén de credenciales del sistema operativo", "protected": True}
    return {"kind": "archivo", "label": f"Archivo local sin cifrar en {_file_path()} (no hay almacén del sistema disponible)", "protected": False}


def _read_file() -> dict:
    try:
        return json.loads(_file_path().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _write_file(data: dict) -> None:
    p = _file_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, p)


def set_secret(name: str, value: str) -> None:
    kr = _keyring()
    if kr:
        try:
            kr.set_password(SERVICE, name, value)
            return
        except Exception:
            pass
    data = _read_file()
    data[name] = value
    _write_file(data)


def get_secret(name: str) -> str | None:
    kr = _keyring()
    if kr:
        try:
            v = kr.get_password(SERVICE, name)
            if v:
                return v
        except Exception:
            pass
    return _read_file().get(name)


def delete_secret(name: str) -> None:
    kr = _keyring()
    if kr:
        try:
            kr.delete_password(SERVICE, name)
        except Exception:
            pass
    data = _read_file()
    if name in data:
        del data[name]
        _write_file(data)


def mask(value: str | None) -> str:
    if not value:
        return ""
    return "••••" + value[-4:] if len(value) >= 12 else "••••"
