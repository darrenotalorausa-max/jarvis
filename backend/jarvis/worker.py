"""Worker: proceso separado que ejecuta la cola. Concurrencia limitada, latido, cancelación cooperativa y recuperación."""
from __future__ import annotations
import logging
import os
import signal
import subprocess
import tempfile
import threading
import time
import traceback

from . import config, db, jobs
from .jobs import ApprovalRequired, Cancelled, JobError
from .router import Ctx, RouterError
from .security import redact
from .util import iso_in

log = logging.getLogger("jarvis.worker")
HANDLERS: dict = {}
HEAVY_TYPES = ("video_render", "video_transcribe", "video_suggest")  # un solo trabajo pesado de FFmpeg a la vez
HEARTBEAT_SECONDS = 5


def handler(type_: str):
    def deco(fn):
        HANDLERS[type_] = fn
        return fn
    return deco


def load_handlers() -> None:
    from .handlers import opportunities, leads, content, video, shopify, clipping, exports  # noqa: F401


class JobCtx:
    def __init__(self, job: dict):
        self.job = job
        self.id = job["id"]
        self.params = job["params"]
        self.space_id = job["space_id"]
        self.router = Ctx(space_id=job["space_id"], job_id=job["id"], limits=job["limits"])
        self._cancel = threading.Event()
        self._started = time.monotonic()

    def stage(self, name: str, progress: float, message: str = "") -> None:
        self.check_cancel()
        jobs.set_progress(self.id, name, progress, message)

    def log(self, message: str, data: dict | None = None) -> None:
        jobs.add_event(self.id, "log", redact(message), data=data)

    def check_cancel(self) -> None:
        if self._cancel.is_set():
            raise Cancelled()
        max_s = self.job["limits"].get("max_seconds")
        if max_s and time.monotonic() - self._started > max_s:
            raise JobError(f"El trabajo superó su duración máxima configurada ({int(max_s)} s).")

    def run_proc(self, args: list[str], cwd: str | None = None, timeout: float | None = None, tail: int = 3000) -> tuple[int, str]:
        """Ejecuta un binario con lista de argumentos (sin shell). Cancela el proceso si se cancela el trabajo."""
        with tempfile.TemporaryFile() as err:
            proc = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=err, stdin=subprocess.DEVNULL, cwd=cwd)
            started = time.monotonic()
            try:
                while proc.poll() is None:
                    if self._cancel.is_set() or (timeout and time.monotonic() - started > timeout):
                        proc.terminate()
                        try:
                            proc.wait(5)
                        except subprocess.TimeoutExpired:
                            proc.kill()
                        if self._cancel.is_set():
                            raise Cancelled()
                        raise JobError("El proceso superó el tiempo máximo y se detuvo.")
                    time.sleep(0.2)
            finally:
                if proc.poll() is None:
                    proc.kill()
            err.seek(0)
            out = err.read()[-tail:].decode("utf-8", "replace")
        return proc.returncode, out


def execute(job: dict) -> str:
    """Ejecuta un trabajo ya reclamado y lo deja en su estado final o de espera. Devuelve el estado."""
    ctx = JobCtx(job)
    stop = threading.Event()

    def beat():
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                if jobs.heartbeat(job["id"]):
                    ctx._cancel.set()
            except Exception:
                pass

    if jobs.heartbeat(job["id"]):
        ctx._cancel.set()
    t = threading.Thread(target=beat, daemon=True)
    t.start()
    status = "failed"
    try:
        fn = HANDLERS.get(job["type"])
        if not fn:
            raise JobError(f"Tipo de trabajo no soportado: {job['type']}")
        result = fn(ctx) or {}
        ctx.check_cancel()
        status = "completed"
        jobs.finish(job["id"], status, result=result, message=result.get("mensaje", "Completado"), usage=ctx.router.summary())
    except Cancelled:
        status = "cancelled"
        jobs.finish(job["id"], status, message="Cancelado por el usuario", usage=ctx.router.summary())
    except ApprovalRequired as exc:
        status = "waiting_approval"
        jobs.finish(job["id"], status, message=exc.message, usage=ctx.router.summary())
    except RouterError as exc:
        if exc.kind == "quota":
            status = "waiting_quota"
            jobs.finish(job["id"], status, message=exc.message, resume_at=exc.resume_at or iso_in(900), usage=ctx.router.summary())
        elif exc.kind in ("needs_config", "policy"):
            status = "waiting_config"
            jobs.finish(job["id"], status, message=exc.message, usage=ctx.router.summary())
        else:
            jobs.finish(job["id"], "failed", error=exc.message, usage=ctx.router.summary())
    except JobError as exc:
        if exc.retryable and job["attempts"] < job["max_attempts"]:
            status = "pending"
            db.execute("UPDATE jobs SET status='pending', resume_at=?, message=?, worker_id=NULL WHERE id=?",
                       (iso_in(10 * job["attempts"]), f"Reintento programado: {exc.message}", job["id"]))
            jobs.add_event(job["id"], "estado", f"Fallo recuperable; reintento programado: {exc.message}")
        else:
            jobs.finish(job["id"], "failed", error=redact(exc.message), usage=ctx.router.summary())
    except Exception as exc:  # error inesperado: un reintento con espera, luego fallo
        log.error("Trabajo %s falló: %s", job["id"], redact(traceback.format_exc()))
        if job["attempts"] < job["max_attempts"]:
            status = "pending"
            db.execute("UPDATE jobs SET status='pending', resume_at=?, message=?, worker_id=NULL WHERE id=?",
                       (iso_in(15 * job["attempts"]), "Error inesperado; reintento programado", job["id"]))
            jobs.add_event(job["id"], "estado", f"Error inesperado ({type(exc).__name__}); reintento programado")
        else:
            jobs.finish(job["id"], "failed", error=redact(f"Error inesperado: {type(exc).__name__}: {exc}")[:500], usage=ctx.router.summary())
    finally:
        stop.set()
    try:
        from . import notify
        final = jobs.get(job["id"])
        if final and final["status"] != "pending":
            notify.job_event(final)
    except Exception:
        log.warning("No se pudo enviar el aviso del trabajo %s", job["id"])
    return status


def run_once(worker_id: str = "test") -> str | None:
    """Reclama y ejecuta un trabajo de forma síncrona (usado en pruebas y diagnósticos)."""
    load_handlers()
    job = jobs.claim(worker_id)
    if not job:
        return None
    execute(job)
    return job["id"]


def run_forever(stop: threading.Event | None = None, poll: float = 1.0) -> None:
    load_handlers()
    stop = stop or threading.Event()
    worker_id = f"w{os.getpid()}"
    max_concurrent = max(1, int(os.environ.get("JARVIS_WORKER_CONCURRENCY") or db.get_setting("worker_concurrency", 2)))
    running: dict[str, tuple[threading.Thread, str]] = {}
    jobs.recover_stale(0 if os.environ.get("JARVIS_RECOVER_ALL") else jobs.STALE_SECONDS)
    last_recover = time.monotonic()
    last_beat = 0.0
    last_poll = 0.0
    log.info("Worker %s iniciado (concurrencia %d)", worker_id, max_concurrent)
    while not stop.is_set():
        for jid in [j for j, (th, _) in running.items() if not th.is_alive()]:
            running.pop(jid)
        if time.monotonic() - last_recover > 30:
            jobs.recover_stale()
            last_recover = time.monotonic()
        if time.monotonic() - last_poll > 4:
            last_poll = time.monotonic()
            try:
                from . import notify
                notify.poll_commands()
            except Exception:
                log.warning("Fallo al leer órdenes remotas")
        if time.monotonic() - last_beat > 5:
            db.set_setting("worker_heartbeat", time.time())
            last_beat = time.monotonic()
        if len(running) < max_concurrent:
            heavy_busy = any(t in HEAVY_TYPES for _, t in running.values())
            job = jobs.claim(worker_id, exclude_types=HEAVY_TYPES if heavy_busy else ())
            if job:
                th = threading.Thread(target=execute, args=(job,), daemon=True)
                running[job["id"]] = (th, job["type"])
                th.start()
                continue
        stop.wait(poll)
    # Detención limpia: pide cancelación cooperativa y devuelve a la cola lo que no termine.
    for jid, (th, _) in running.items():
        th.join(timeout=8)
        if th.is_alive():
            db.execute("UPDATE jobs SET status='pending', worker_id=NULL, message='Devuelto a la cola por cierre del worker' WHERE id=? AND status='running'", (jid,))


def main() -> None:
    config.ensure_dirs()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s",
                        handlers=[logging.FileHandler(config.logs_dir() / "worker.log", encoding="utf-8"), logging.StreamHandler()])
    db.migrate()
    stop = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stop.set())
    run_forever(stop)


if __name__ == "__main__":
    # Al ejecutarse con "python -m" este archivo es el módulo __main__; los manejadores se registran en jarvis.worker.
    # Se delega en el módulo importado para que ambos compartan el mismo registro.
    from jarvis.worker import main as _main
    _main()
