"""Worker de Doomsday: la cola del motor con el manejador `dd_run` y la ronda horaria del monitor de tiendas (G07)."""
from __future__ import annotations
import logging
import threading

from . import env  # noqa: F401  (fija carpeta y puerto de Doomsday antes de cargar el motor)
from jarvis import worker as jworker

from . import engine, integrations, kinds, plans, tools, tools2  # noqa: F401  (registra tipos y manejadores)

log = logging.getLogger("doomsday.worker")
STORE_CHECK_SECONDS = 3600


def _store_loop(stop: threading.Event) -> None:
    while not stop.wait(STORE_CHECK_SECONDS):
        try:
            tools.run_store_checks()
        except Exception:
            log.warning("Fallo en la ronda del monitor de tiendas")


def main() -> None:
    kinds.register()
    integrations.register()
    plans.register()
    stop = threading.Event()
    threading.Thread(target=_store_loop, args=(stop,), daemon=True).start()
    try:
        jworker.main()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
