"""Lanzador de Doomsday: migra su base, arranca su worker y sirve su API en loopback (puerto 8766). Ctrl+C detiene ambos.

Uso: `python -m doomsday.launch [--app]` desde `backend/`. Con --app se abre en ventana propia si pywebview está disponible.
"""
from __future__ import annotations
import logging
import os
import subprocess
import sys
import threading
import time
import webbrowser

from . import env  # noqa: F401  (antes que jarvis)
from jarvis import access, config, db
from jarvis import launch as jlaunch


def main() -> int:
    app_mode = "--app" in sys.argv
    config.ensure_dirs()
    applied = db.migrate()
    host, port = config.host(), config.port()
    url = f"http://127.0.0.1:{port}/"
    if not jlaunch._port_free("127.0.0.1", port):
        print(f"[Doomsday] El puerto {port} ya está en uso. Si Doomsday ya está abierto, entra en {url}\n"
              f"           Si lo usa otro programa, define DOOMSDAY_PORT con otro número.")
        return 2
    if access.exposed() and not access.enabled():
        print("[Doomsday] No se inicia: abrirlo a la red exige definir JARVIS_ACCESS_CODE (10 caracteres o más) en .env.")
        return 2
    print(f"[Doomsday] Base de datos: {config.db_path()}" + (f" (migraciones aplicadas: {applied})" if applied else ""))
    from . import app as dd_app
    dd_app.ensure_seed()
    worker_log = open(config.logs_dir() / "worker.out.log", "a", encoding="utf-8")
    worker = subprocess.Popen([sys.executable, "-m", "doomsday.worker"], cwd=str(config.REPO_ROOT / "backend"), stdout=worker_log, stderr=subprocess.STDOUT,
                              env={**os.environ, "JARVIS_RECOVER_ALL": "1"})
    stop = threading.Event()

    def watch():
        while not stop.wait(5):
            if worker.poll() is None:
                db.set_setting("worker_heartbeat", time.time())
            else:
                print(f"[Doomsday] El worker se detuvo (código {worker.returncode}). Revisa logs/worker.out.log y reinicia.")
                return

    db.set_setting("worker_heartbeat", time.time())
    threading.Thread(target=watch, daemon=True).start()
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(config.logs_dir() / "api.log", encoding="utf-8")])
    server = uvicorn.Server(uvicorn.Config(dd_app.app, host=host, port=port, log_level="warning", access_log=False, timeout_graceful_shutdown=3))
    dd_app.app.state.shutdown = lambda: setattr(server, "should_exit", True)
    jlaunch.WINDOW_TITLE = "Doomsday"
    try:
        if not (app_mode and jlaunch._desktop(server, url)):
            if app_mode or not os.environ.get("JARVIS_NO_BROWSER"):
                threading.Timer(1.5, lambda: webbrowser.open(url)).start()
            print(f"[Doomsday] Abierto en {url}  (Ctrl+C para detener)")
            server.run()
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
        print(f"[Doomsday] Detenido. Tus datos están en {config.home()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
