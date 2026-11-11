"""Doomsday: los 100 módulos del Laboratorio Estratégico, dentro de Jarvis.

Jarvis y Doomsday son una sola aplicación: mismo proceso, misma base de datos y misma interfaz. Este paquete aporta los módulos
(catálogo, skills, herramientas, planes e integraciones); `jarvis/` sigue siendo el motor (conexiones, router, cola, revisión, acceso).
"""
VERSION = "0.2.0"
_loaded = False


def load() -> None:
    """Registra en el motor todo lo de Doomsday. Idempotente; lo llaman el worker y la API."""
    global _loaded
    if _loaded:
        return
    _loaded = True
    from . import bridge, engine, integrations, kinds, plans, tools2  # noqa: F401
    kinds.register()
    integrations.register()
    plans.register()
    bridge.register()
