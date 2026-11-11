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


def _window(url: str) -> None:
    import webview
    webview.create_window("Jarvis OS", url, width=1480, height=920, min_size=(980, 640), background_color="#07090c")
    webview.start()


def _desktop(server, url: str) -> bool:
    """Abre Jarvis en una ventana propia de aplicación (pywebview: WebView2 en Windows, WebKit en macOS).
    Devuelve False si no está disponible, para caer al navegador."""
    try:
        import webview
    except Exception:
        print("[Jarvis] La ventana de aplicación no está disponible en este equipo (falta pywebview); se abre en el navegador.")
        return False
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    try:
        _window(url)
    except Exception as exc:
        print(f"[Jarvis] No se pudo abrir la ventana de aplicación ({type(exc).__name__}); se abre en el navegador.")
        webbrowser.open(url)
        try:
            thread.join()
        except KeyboardInterrupt:
            pass
    server.should_exit = True
    thread.join(timeout=8)
    return True


def main() -> int:
    app_mode = "--app" in sys.argv
    config.ensure_dirs()
    if sys.stdout is None or sys.stderr is None:
        # Iniciado sin consola (acceso directo con pythonw): los mensajes van a un archivo.
        sys.stdout = sys.stderr = open(config.logs_dir() / "launcher.log", "a", encoding="utf-8", buffering=1)
    applied = db.migrate()
    host, port = config.host(), config.port()
    url = f"http://{'127.0.0.1' if host in ('0.0.0.0', '127.0.0.1') else host}:{port}/"
    if not _port_free("127.0.0.1", port):
        if app_mode:
            # Jarvis ya está en marcha: se abre otra ventana sobre la misma instancia.
            try:
                _window(url)
            except Exception:
                webbrowser.open(url)
            return 0
        print(f"[Jarvis] El puerto {port} ya está en uso. Si Jarvis ya está abierto, entra en {url}\n"
              f"         Si lo usa otro programa, define JARVIS_PORT con otro número y vuelve a iniciar.")
        return 2
    from . import access
    if access.exposed():
        if not access.enabled():
            print(f"[Jarvis] No se inicia: JARVIS_HOST={host} abre Jarvis a tu red, y eso exige definir JARVIS_ACCESS_CODE\n"
                  f"         (10 caracteres o más) en el archivo .env. Sin código de acceso, deja JARVIS_HOST sin definir.")
            return 2
        print("[Jarvis] ACCESO EN RED ACTIVADO: otros dispositivos de tu red pueden entrar con el código de acceso.\n"
              "         La conexión no va cifrada: úsalo solo en tu red de casa, nunca en redes públicas.")
        for u in access.lan_urls():
            print(f"[Jarvis] Desde tu celular (misma wifi): {u}")
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
    import uvicorn
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(config.logs_dir() / "api.log", encoding="utf-8")])
    from . import api
    server = uvicorn.Server(uvicorn.Config(api.app, host=host, port=port, log_level="warning", access_log=False, timeout_graceful_shutdown=3))
    api.app.state.shutdown = lambda: setattr(server, "should_exit", True)
    try:
        if app_mode and _desktop(server, url):
            pass  # la ventana se cerró: se detiene todo abajo
        else:
            if app_mode or not os.environ.get("JARVIS_NO_BROWSER"):
                threading.Timer(1.5, lambda: webbrowser.open(url)).start()
            print(f"[Jarvis] Abierto en {url}  (Ctrl+C para detener)")
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
        print("[Jarvis] Detenido. Tus datos están en la carpeta data/.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
