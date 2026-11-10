"""Avisos al celular, órdenes por Telegram, pausa de agentes, misiones, biblioteca, acceso en red y compatibilidad con Gemma."""
import json

import httpx
import pytest

from jarvis import access, business, connections, db, jobs, library, notify, records, worker
from conftest import run_all


def _telegram(conn, fake, **options):
    sent = []

    def handler(req):
        if req.url.path.endswith("/sendMessage"):
            sent.append(json.loads(req.content))
            return httpx.Response(200, json={"ok": True, "result": {}})
        return httpx.Response(200, json={"ok": True, "result": handler.updates})

    handler.updates = []
    fake.custom["api.telegram.org"] = handler
    c = conn("telegram", name="Mi Telegram", secret="123:ABC", options={"chat_id": "777", **options})
    return c, sent, handler


def test_job_notifications_only_carry_status_and_respect_personal_space(fake, conn, space):
    biz, personal = space(), space("Personal", "personal", "solo_local")
    c, sent, _ = _telegram(conn, fake, events=["completed", "failed"])
    worker.HANDLERS["t_ok"] = lambda ctx: {"mensaje": "Listo"}
    worker.HANDLERS["t_bad"] = lambda ctx: (_ for _ in ()).throw(jobs.JobError("dato inválido"))
    worker.HANDLERS["t_wait"] = lambda ctx: (_ for _ in ()).throw(jobs.ApprovalRequired("falta aprobar"))
    j1, _ = jobs.enqueue(biz, "t_ok", "Investigar gatos", {})
    jobs.enqueue(biz, "t_bad", "Importar", {})
    jobs.enqueue(biz, "t_wait", "Enviar", {})          # evento «waiting» no suscrito
    jobs.enqueue(personal, "t_ok", "Diario privado", {})  # espacio personal: no sale
    run_all()
    texts = [m["text"] for m in sent]
    assert len(texts) == 2 and all(m["chat_id"] == "777" for m in sent)
    assert any("Investigar gatos" in t and "Completado" in t and j1["id"] in t for t in texts) and any("dato inválido" in t for t in texts)
    assert not any("Diario privado" in t or "Enviar" in t for t in texts)
    assert "123:ABC" in str(fake.calls[-1].url) and "123:ABC" not in json.dumps(db.query("SELECT * FROM usage")) + json.dumps(db.query("SELECT * FROM audit"))


def test_notification_failure_never_breaks_the_job(fake, conn, space):
    sid = space()
    conn("ntfy", name="Push", secret="", options={"topic": "jarvis-abc123"})
    fake.status["ntfy.sh"] = 500
    worker.HANDLERS["t_ok"] = lambda ctx: {"mensaje": "Listo"}
    j, _ = jobs.enqueue(sid, "t_ok", "X", {})
    run_all()
    assert jobs.get(j["id"])["status"] == "completed"
    assert connections.public(connections.list_all()[0])["status"] == "error"


def test_whatsapp_and_ntfy_payloads_and_validation(fake, conn, space):
    got = {}
    fake.custom["graph.facebook.com"] = lambda req: got.update(wa=(req.url.path, json.loads(req.content), req.headers["authorization"])) or httpx.Response(200, json={"messages": [{"id": "x"}]})
    fake.custom["ntfy.sh"] = lambda req: got.update(ntfy=(req.url.path, req.content.decode(), req.headers.get("title"))) or httpx.Response(200, json={})
    w = conn("whatsapp", secret="EAAtoken", options={"phone_number_id": "1055", "to": "+573001234567"})
    n = conn("ntfy", secret="", options={"topic": "jarvis-abc123"})
    assert connections.test(w["id"])["ok"] and connections.test(n["id"])["ok"]
    assert got["wa"][0].endswith("/1055/messages") and got["wa"][1]["to"] == "573001234567" and got["wa"][1]["messaging_product"] == "whatsapp" and got["wa"][2] == "Bearer EAAtoken"
    assert got["ntfy"][0] == "/jarvis-abc123" and "Prueba de conexión" in got["ntfy"][1]
    bad = conn("ntfy", secret="", options={"topic": "../admin"})
    assert connections.test(bad["id"])["status"] == "no_configurada"
    bad2 = conn("whatsapp", secret="x", options={"phone_number_id": "1/../2", "to": "1"})
    assert connections.test(bad2["id"])["ok"] is False


def test_telegram_commands_only_from_authorized_chat_and_never_twice(fake, conn, space):
    sid = space()
    c, sent, tg = _telegram(conn, fake, commands=True, space_id=sid)
    tg.updates = [{"update_id": 10, "message": {"chat": {"id": 999}, "text": "pausa los agentes"}},        # desconocido: ignorado
                  {"update_id": 11, "message": {"chat": {"id": 777}, "text": "tarea: llamar al proveedor"}}]
    assert notify.poll_commands() == 1
    assert [t["title"] for t in records.list_records(sid, "task")] == ["llamar al proveedor"]
    assert not db.get_setting("agents_paused", False) and len(sent) == 1 and "Tarea creada" in sent[0]["text"]
    assert db.get_setting(f"telegram_offset:{c['id']}") == 12
    tg.updates = []
    assert notify.poll_commands() == 0 and len(records.list_records(sid, "task")) == 1
    assert "offset=12" in str(fake.calls[-1].url)
    connections.update(c["id"], {"options": {"chat_id": "777", "commands": False, "space_id": sid}})
    tg.updates = [{"update_id": 12, "message": {"chat": {"id": 777}, "text": "tarea: otra"}}]
    assert notify.poll_commands() == 0                                              # órdenes desactivadas: ni se consulta


def test_pause_all_agents_blocks_claims_until_resumed(space, client):
    sid = space()
    worker.HANDLERS["t_ok"] = lambda ctx: {"mensaje": "ok"}
    j, _ = jobs.enqueue(sid, "t_ok", "X", {})
    r = client.post("/api/assistant", json={"space": sid, "text": "Pausa todos los agentes"}).json()
    assert r["tool"] == "pausar_agentes" and db.get_setting("agents_paused") is True
    assert worker.run_once() is None and jobs.get(j["id"])["status"] == "pending"
    assert business.summary(sid)["agentes"] == {"pausados": True, "en_ejecucion": 0, "en_cola": 1, "en_espera": 0}
    assert client.patch("/api/settings", json={"agents_paused": False}).status_code == 200
    run_all()
    assert jobs.get(j["id"])["status"] == "completed"


def test_mission_cannot_be_verified_without_criterion_and_evidence(space, client):
    sid = space()
    base = {"business": "ecom", "section": "A_base_estable", "action": "Configurar política de devoluciones"}
    m = records.create(sid, "mission", "Política de devoluciones", base)
    with pytest.raises(records.RecordError, match="evidencia"):
        records.update(m["id"], sid, {"status": "completada_verificada"})
    with pytest.raises(records.RecordError):
        records.update(m["id"], sid, {"status": "completada_verificada", "data": {"closure": "Publicada y enlazada en el pie"}})
    assert client.patch(f"/api/records/{m['id']}", json={"space": sid, "status": "completada_verificada"}).status_code == 400
    ok = records.update(m["id"], sid, {"status": "completada_verificada", "data": {"closure": "Publicada y enlazada en el pie", "evidence": "https://tienda.test/politicas"}})
    assert ok["status"] == "completada_verificada"
    with pytest.raises(records.RecordError):                                        # tampoco al crear
        records.create(sid, "mission", "Atajo", base, status="completada_verificada")
    records.create(sid, "mission", "Sin aplicar", {**base, "business": "b2b"}, status="no_aplica")
    s = client.get("/api/business/summary", params={"space": sid}).json()
    ecom = next(b for b in s["negocios"] if b["id"] == "ecom")
    b2b = next(b for b in s["negocios"] if b["id"] == "b2b")
    clip = next(b for b in s["negocios"] if b["id"] == "clip")
    assert ecom["avance"] == 1.0 and ecom["por_seccion"]["A_base_estable"] == {"total": 1, "verificadas": 1}
    assert b2b["avance"] is None and clip["avance"] is None and clip["economia"] is None      # sin datos ≠ 0
    assert s["manual"]["importado"] is False and "No se ha inventado" in s["manual"]["nota"] and s["transversal"]["clipping"] is None


def test_library_serves_guides_and_blocks_traversal(client):
    tree = client.get("/api/library").json()
    ids = {c["id"]: c for c in tree}
    assert {"conexiones", "mente", "cuerpo", "espiritu", "economia", "habilidades", "disparadores", "negocios", "herramientas"} <= set(ids)
    assert len(ids["habilidades"]["docs"]) == 18 and len(ids["disparadores"]["docs"]) == 18 and ids["conexiones"]["docs"][0]["title"].startswith("IA gratis")
    doc = client.get("/api/library/doc", params={"path": ids["conexiones"]["docs"][0]["path"]}).json()
    assert "aistudio.google.com" in doc["markdown"] and "Gemma" in doc["markdown"]
    assert client.get("/api/library/search", params={"q": "repetición espaciada"}).json()
    for bad in ("../backend/jarvis/api.py", "conexiones/../../README_START_HERE.md", "conexiones/_meta.json", "/etc/passwd"):
        assert client.get("/api/library/doc", params={"path": bad}).status_code in (400, 404)
    assert client.get("/api/library/file", params={"path": ids["negocios"]["files"][0]["path"]}).headers["content-type"] == "application/pdf"
    assert library.search("x") == []


def test_network_access_requires_code_and_session(monkeypatch, space):
    from fastapi.testclient import TestClient
    from jarvis.api import app
    phone = TestClient(app, client=("192.168.1.50", 50000), base_url="http://192.168.1.20:8765")
    assert phone.get("/api/bootstrap").status_code == 403                           # por defecto: cerrado a la red
    monkeypatch.setenv("JARVIS_HOST", "0.0.0.0")
    assert not access.enabled() and phone.get("/api/bootstrap").status_code == 403  # expuesto sin código: sigue cerrado
    monkeypatch.setenv("JARVIS_ACCESS_CODE", "corto")
    assert not access.enabled()
    monkeypatch.setenv("JARVIS_ACCESS_CODE", "codigo-largo-de-casa")
    access._failures.clear()
    r = phone.get("/api/bootstrap")
    assert r.status_code == 401 and r.json()["kind"] == "login"
    assert phone.post("/api/login", json={"code": "malo"}).status_code == 400
    assert phone.post("/api/login", json={"code": "codigo-largo-de-casa"}, headers={"origin": "http://evil.example"}).status_code == 403
    ok = phone.post("/api/login", json={"code": "codigo-largo-de-casa"})
    assert ok.status_code == 200 and "httponly" in ok.headers["set-cookie"].lower() and "codigo-largo" not in ok.headers["set-cookie"]
    assert phone.get("/api/bootstrap").status_code == 200
    intruder = TestClient(app, client=("192.168.1.66", 50001), base_url="http://192.168.1.20:8765")
    for _ in range(5):
        assert intruder.post("/api/login", json={"code": "x"}).status_code == 400
    assert "Demasiados intentos" in intruder.post("/api/login", json={"code": "codigo-largo-de-casa"}).json()["detail"]
    assert intruder.get("/api/records", params={"space": space(), "kind": "task"}).status_code == 401


def test_gemma_on_gemini_api_retries_without_system_instruction_or_json_mode(fake, conn, space):
    from jarvis import router
    seen = []

    def gemini(req):
        body = json.loads(req.content)
        seen.append(body)
        if "systemInstruction" in body or "responseMimeType" in body["generationConfig"]:
            return httpx.Response(400, json={"error": {"message": "Developer instruction is not enabled for models/gemma-3-27b-it"}})
        return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": '{"ok": true}'}]}}], "usageMetadata": {"promptTokenCount": 9, "candidatesTokenCount": 3}})

    fake.custom["generativelanguage.googleapis.com"] = gemini
    conn("gemini", name="Gemma", model="gemma-3-27b-it", capabilities=["texto", "extraccion"], secret="AIzaPRUEBA1234567890abcd")
    text, meta = router.llm(router.Ctx(space()), system="Eres un extractor.", user="Devuelve JSON.", json_mode=True)
    assert text == '{"ok": true}' and len(seen) == 2
    assert "Eres un extractor." in seen[1]["contents"][0]["parts"][0]["text"] and "systemInstruction" not in seen[1]
