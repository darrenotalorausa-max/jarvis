"""Entorno de Doomsday. Debe importarse antes que `jarvis`: fija su propia carpeta de datos y su propio puerto.

Doomsday nunca comparte base de datos con Jarvis. Variables: DOOMSDAY_HOME (carpeta) y DOOMSDAY_PORT (puerto, 8766 por defecto).
"""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
os.environ["JARVIS_HOME"] = os.environ.get("DOOMSDAY_HOME") or str(REPO_ROOT / "doomsday_home")
os.environ["JARVIS_PORT"] = os.environ.get("DOOMSDAY_PORT") or "8766"
