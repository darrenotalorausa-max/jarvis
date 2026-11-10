"""Lanzador: migra la base, arranca el worker como proceso separado y sirve la API en loopback. Ctrl+C detiene ambos de forma limpia."""
from __future__ import annotations
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser

from . import config, db


def _port_free(host: str, port: int) -> bool:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) != 0


def main() -> int:
    config.ensure_dirs()
    applied = db.migrate()
    host, port = config.host(), config.port()
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}/"
    if not _port_free("127.0.0.1", port):
        print(f"[Jarvis] El puerto {port} ya está en uso. Si Jarvis ya está abierto, entra en {url}\n"
              f"         Si lo usa otro programa, define JARVIS_PORT con otro número y vuelve a iniciar.")
        return 2
    if host not in ("127.0.0.1", "localhost"):
        print(f"[Jarvis] AVISO: JARVIS_HOST={host} expone la aplicación fuera de este equipo. No hay autenticación: úsalo solo en redes de confianza.")
    print(f"[Jarvis] Base de datos: {config.db_path()}" + (f" (migraciones aplicadas: {applied})" if applied else ""))
    worker_log = open(config.logs_dir() / "worker.out.log", "a", encoding="utf-8")
    worker = subprocess.Popen([sys.executable, "-m", "jarvis.worker"], cwd=str(config.REPO_ROOT / "backend"), stdout=worker_log, stderr=subprocess.STDOUT, env={**os.environ, "JARVIS_RECOVER_ALL": "1"})
    stop = threading.Event()

    def watch():
        # Marca de vida del worker para la interfaz y aviso si se detiene.
        while not stop.wait(5):
            if worker.poll() is None:
                db.set_setting("worker_heartbeat", time.time())
            else:
                print(f"[Jarvis] El worker se detuvo (código {worker.returncode}). Revisa logs/worker.out.log y reinicia Jarvis.")
                return

    db.set_setting("worker_heartbeat", time.time())
    threading.Thread(target=watch, daemon=True).start()
    if not os.environ.get("JARVIS_NO_BROWSER"):
        threading.Timer(1.5, lambda: webbrowser.open(url)).start()
    print(f"[Jarvis] Abierto en {url}  (Ctrl+C para detener)")
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(config.logs_dir() / "api.log", encoding="utf-8")])
    try:
        uvicorn.run("jarvis.api:app", host=host, port=port, log_level="warning", access_log=False, timeout_graceful_shutdown=3)
    finally:
        stop.set()
        db.set_setting("worker_heartbeat", 0)
        if worker.poll() is None:
            worker.terminate()
            try:
                worker.wait(15)
            except subprocess.TimeoutExpired:
                worker.kill()
        worker_log.close()
        print("[Jarvis] Detenido. Tus datos están en la carpeta data/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
