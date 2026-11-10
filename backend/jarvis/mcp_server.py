"""Servidor MCP por stdio. Permite que un cliente MCP (Claude Desktop, Claude Code, etc.) use las herramientas internas de Jarvis.

Uso:  python -m jarvis.mcp_server [id_o_nombre_de_espacio]
Solo expone las herramientas del asistente (consultar, lanzar trabajos, anotar, pausar agentes). Ninguna envía, publica ni gasta.
Los espacios personales no se exponen.
"""
from __future__ import annotations
import json
import sys

from . import assistant, config, db

PROTOCOL = "2024-11-05"


def _space(arg: str | None) -> dict:
    rows = db.query("SELECT * FROM spaces WHERE archived=0 AND kind!='personal' ORDER BY created_at")
    if arg:
        rows = [r for r in rows if r["id"] == arg or r["name"].lower() == arg.lower()]
    if not rows:
        raise SystemExit("No hay ningún espacio de negocio disponible para MCP.")
    return rows[0]


def handle(msg: dict, space: dict) -> dict | None:
    method, mid = msg.get("method"), msg.get("id")
    ok = lambda result: {"jsonrpc": "2.0", "id": mid, "result": result}
    if method == "initialize":
        return ok({"protocolVersion": PROTOCOL, "capabilities": {"tools": {}}, "serverInfo": {"name": "jarvis-os", "version": config.APP_VERSION},
                   "instructions": f"Herramientas de Jarvis OS sobre el espacio «{space['name']}». Los trabajos se ejecutan en la cola local; consulta su estado con estado_trabajos."})
    if method == "tools/list":
        return ok({"tools": [{"name": t["name"], "description": t["description"], "inputSchema": {"type": "object", **{k: v for k, v in t["args"].model_json_schema().items() if k in ("properties", "required")}}}
                             for t in assistant.TOOLS.values()]})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        if name not in assistant.TOOLS:
            return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32602, "message": f"Herramienta desconocida: {name}"}}
        out = assistant._run(space["id"], name, params.get("arguments") or {})
        db.audit("mcp.herramienta", name, {"error": bool(out.get("error"))}, actor="mcp")
        return ok({"content": [{"type": "text", "text": out["reply"]}], "isError": bool(out.get("error"))})
    if method == "ping":
        return ok({})
    if mid is None:
        return None  # notificaciones (p. ej. notifications/initialized)
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Método no soportado: {method}"}}


def main() -> None:
    db.migrate()
    space = _space(sys.argv[1] if len(sys.argv) > 1 else None)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            reply = handle(json.loads(line), space)
        except ValueError:
            reply = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "JSON no válido"}}
        if reply is not None:
            sys.stdout.write(json.dumps(reply, ensure_ascii=False) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
