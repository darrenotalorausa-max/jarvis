"""Claude por SDK oficial, conector universal, OAuth, monitores, importadores, tutor, notas, texto bíblico, usuarios con rol, MCP y API externa."""
import json
import os
import subprocess
import sys
from datetime import date, timedelta

import httpx
import pytest

from jarvis import access, config, connections, connectors, db, imports, jobs, monitors, records, review, scripture
from conftest import run_all


# ---------- Claude (SDK oficial de Anthropic)

@pytest.fixture
def claude(conn, monkeypatch):
    import httpx2
    from jarvis.providers import llm
    state = {"calls": [], "status": 200, "stop": "end_turn"}

    def handler(req):
        state["calls"].append(req)
        if state["status"] != 200:
            return httpx2.Response(state["status"], json={"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}})
        if req.url.path.endswith("/models"):
            return httpx2.Response(200, json={"data": [{"id": "claude-opus-5-5", "type": "model", "display_name": "Claude Opus 5.5", "created_at": "2026-01-01T00:00:00Z"}], "has_more": False, "first_id": "claude-opus-5-5", "last_id": "claude-opus-5-5"})
        return httpx2.Response(200, json={"id": "msg_1", "type": "message", "role": "assistant", "model": "claude-opus-5-5", "content": [{"type": "text", "text": "ok"}],
                                           "stop_reason": state["stop"], "stop_sequence": None, "usage": {"input_tokens": 12, "output_tokens": 4}})

    monkeypatch.setattr(llm, "ANTHROPIC_TRANSPORT", httpx2.MockTransport(handler))
    c = conn("anthropic", name="Claude", model="claude-opus-5-5", capabilities=["texto", "extraccion"], secret="sk-ant-prueba-000000000000")
    return c, state


def test_claude_through_official_sdk(claude, space):
    from jarvis import router
    c, st = claude
    assert connections.models(c["id"]) == ["claude-opus-5-5"]
    assert connections.test(c["id"])["ok"] is True
    text, meta = router.llm(router.Ctx(space()), system="Eres breve.", user="hola")
    body = json.loads(st["calls"][-1].content)
    assert text == "ok" and body["system"] == "Eres breve." and body["max_tokens"] >= 16000 and "temperature" not in body
    h = st["calls"][-1].headers
    assert "sk-ant-prueba-000000000000" in (h.get("x-api-key") or h.get("authorization") or "") and db.one("SELECT tokens_in, tokens_out FROM usage WHERE state='ok'") == {"tokens_in": 12, "tokens_out": 4}
    st["stop"] = "refusal"
    with pytest.raises(router.RouterError) as e:
        router.llm(router.Ctx(space()), system="s", user="u")
    assert "declinó" in e.value.message and len([x for x in st["calls"] if x.url.path.endswith("/messages")]) == 3   # sin cambio automático de modelo
    st.update(status=401, stop="end_turn")
    assert connections.test(c["id"])["status"] == "credencial_invalida"


# ---------- Conector universal

def _stripe(conn, fake, **opts):
    seen = []
    fake.custom["api.stripe.com"] = lambda req: seen.append(req) or httpx.Response(200, json={"object": "list", "data": [{"id": "ch_1", "amount": 1200}]})
    p = connectors.PRESETS["stripe"]
    c = conn("api", name="Stripe", base_url=p["base_url"], secret="rk_live_SECRETO123456789", options={"preset": "stripe", "auth": p["auth"], "actions": p["actions"], **opts})
    return c, seen


def test_universal_connector_reads_and_stays_inside_base_url(fake, conn, client):
    c, seen = _stripe(conn, fake)
    out = client.post(f"/api/apps/{c['id']}/run", json={"action": "cobros", "variables": {"limite": 5}}).json()
    assert out["status"] == 200 and out["json"]["data"][0]["id"] == "ch_1" and out["request"]["url"] == "https://api.stripe.com/v1/charges"
    assert seen[-1].headers["authorization"] == "Bearer rk_live_SECRETO123456789" and seen[-1].url.params["limit"] == "5"
    assert "SECRETO" not in json.dumps(out)
    assert connections.test(c["id"])["ok"] is True
    for bad in ({"path": "https://evil.test/x"}, {"path": "/../../admin"}, {"path": "sin-barra"}, {"path": "/x", "method": "TRACE"}):
        with pytest.raises(ValueError):
            connectors.validate_options({"auth": {"type": "bearer"}, "actions": [{"id": "x", "method": "GET", **bad}]})
    gh = conn("api", name="GH", base_url="https://api.github.com", secret="t", options={"auth": {"type": "bearer"}, "actions": [{"id": "issues", "method": "GET", "path": "/repos/{propietario}/{repo}/issues"}]})
    r = client.post(f"/api/apps/{gh['id']}/run", json={"action": "issues", "variables": {"propietario": "../../user", "repo": "x"}})
    assert r.status_code == 502 and "no es válido" in r.json()["detail"] and fake.count("api.github.com") == 0
    assert connectors.validate_options({"auth": {"type": "none"}, "actions": [{"id": "borrar", "method": "DELETE", "path": "/x"}]})["actions"][0]["write"] is True


def test_write_actions_need_exact_one_time_approval(fake, conn, space, client):
    sid = space()
    sent = []
    fake.custom["tienda.myshopify.com"] = lambda req: sent.append(json.loads(req.content)) or httpx.Response(201, json={"product": {"id": 9}})
    p = connectors.PRESETS["shopify"]
    c = conn("api", name="Shopify", base_url="https://tienda.myshopify.com/admin/api/2024-10", secret="shpat_x", options={"auth": p["auth"], "actions": p["actions"]})
    body = {"space": sid, "action": "crear_producto_borrador", "variables": {"titulo": "Rascador", "descripcion": "Sisal"}}
    assert client.post(f"/api/apps/{c['id']}/run", json=body).status_code == 502 and sent == []                    # nunca por la vía directa
    req = client.post(f"/api/apps/{c['id']}/request", json=body).json()
    assert req["preview"]["method"] == "POST" and req["preview"]["body"]["product"] == {"title": "Rascador", "body_html": "Sisal", "status": "draft"}
    run_all()
    assert jobs.get(req["job"]["id"])["status"] == "waiting_approval" and sent == []
    pend = client.get(f"/api/apps/pending/{req['job']['id']}").json()
    assert pend["preview"]["url"].endswith("/products.json")
    assert client.post(f"/api/apps/pending/{req['job']['id']}/approve", json={}).status_code == 200
    db.execute("UPDATE jobs SET params=? WHERE id=?", (json.dumps({**jobs.get(req["job"]["id"])["params"], "variables": {"titulo": "OTRO", "descripcion": "x"}}), req["job"]["id"]))
    run_all()
    assert jobs.get(req["job"]["id"])["status"] == "waiting_approval" and sent == []                               # la petición cambió: la aprobación no vale
    db.execute("UPDATE jobs SET params=? WHERE id=?", (json.dumps({"connection_id": c["id"], "action_id": "crear_producto_borrador", "variables": body["variables"]}), req["job"]["id"]))
    client.post(f"/api/apps/pending/{req['job']['id']}/approve", json={})
    run_all()
    assert jobs.get(req["job"]["id"])["status"] == "completed" and len(sent) == 1 and sent[0]["product"]["status"] == "draft"
    assert db.get_setting(f"action_approval:{req['job']['id']}") is None
    assert "accion_externa" in [a["action"] for a in db.query("SELECT action FROM audit")]


def test_oauth_authorization_code_and_refresh(fake, conn, client):
    tokens = []

    def google(req):
        form = dict(x.split("=") for x in req.content.decode().split("&"))
        tokens.append(form)
        return httpx.Response(200, json={"access_token": f"at{len(tokens)}", "refresh_token": "rt1", "expires_in": 3600})

    fake.custom["oauth2.googleapis.com"] = google
    fake.custom["www.googleapis.com"] = lambda req: httpx.Response(200, json={"user": {"emailAddress": "yo@test"}, "auth": req.headers["authorization"]})
    p = connectors.PRESETS["google_drive"]
    c = conn("api", name="Drive", base_url=p["base_url"], secret="GOCSPX-secreto", options={"preset": "google_drive", "auth": p["auth"], "actions": p["actions"], "client_id": "123.apps.googleusercontent.com"})
    assert client.post(f"/api/apps/{c['id']}/run", json={"action": "yo"}).status_code == 502                       # sin autorizar
    start = client.post("/api/oauth/start", json={"connection_id": c["id"]}).json()
    assert "client_id=123.apps.googleusercontent.com" in start["url"] and "drive.readonly" in start["url"] and start["redirect_uri"].endswith("/api/oauth/callback")
    state = start["url"].split("state=")[1].split("&")[0]
    assert client.get("/api/oauth/callback", params={"state": "falso", "code": "x"}).status_code == 502
    assert "autorizada" in client.get("/api/oauth/callback", params={"state": state, "code": "c0d1go"}).text
    assert tokens[0]["grant_type"] == "authorization_code" and tokens[0]["client_secret"] == "GOCSPX-secreto"
    assert client.post(f"/api/apps/{c['id']}/run", json={"action": "yo"}).json()["json"]["auth"] == "Bearer at1"
    sec = connectors._secret(connections.get(c["id"]))
    connectors._save_secret(connections.get(c["id"]), {**sec, "expires_at": 0})
    assert client.post(f"/api/apps/{c['id']}/run", json={"action": "yo"}).json()["json"]["auth"] == "Bearer at2" and tokens[-1]["grant_type"] == "refresh_token"
    assert "at2" not in json.dumps(client.get("/api/connections").json())


# ---------- Monitores proactivos

def test_monitors_alert_once_and_notify(fake, conn, space, client):
    sid = space()
    sent = []
    fake.custom["api.telegram.org"] = lambda req: sent.append(json.loads(req.content)["text"]) or httpx.Response(200, json={"ok": True, "result": []})
    conn("telegram", secret="1:A", options={"chat_id": "7"})
    records.create(sid, "task", "Pagar hosting", {"due_date": (date.today() - timedelta(days=2)).isoformat()})
    mon = records.create(sid, "monitor", "Tareas vencidas", {"type": "tareas_vencidas", "every_hours": 6, "notify": True})
    assert monitors.run_due()[0]["nuevos"] == 1 and len(sent) == 1 and "Pagar hosting" in sent[0]
    assert monitors.run_due() == []                                                         # aún no toca
    db.execute("UPDATE records SET data=json_set(data,'$.last_run','2000-01-01T00:00:00+00:00') WHERE id=?", (mon["id"],))
    assert monitors.run_due()[0]["nuevos"] == 0 and len(sent) == 1                           # mismo hallazgo: no repite
    assert len(records.list_records(sid, "alert")) == 1
    fake.pages["https://mitienda.test/"] = (503, "caída")
    web = records.create(sid, "monitor", "Web", {"type": "sitio_web", "url": "https://mitienda.test/"})
    out = client.post("/api/monitors/run", json={"space": sid, "id": web["id"]}).json()
    assert out["nuevos"] == 1 and "503" in records.list_records(sid, "alert")[0]["title"]
    db.set_setting("agents_paused", True)
    db.execute("UPDATE records SET data=json_set(data,'$.last_run','2000-01-01T00:00:00+00:00') WHERE kind='monitor'")
    assert monitors.run_due() == []                                                         # la pausa global también detiene los monitores


# ---------- Importadores

def test_apple_health_and_ofx_imports(space, client):
    sid = space("Personal", "personal", "solo_local")
    d = (date.today() - timedelta(days=1)).isoformat()
    xml = f"""<?xml version="1.0"?><HealthData>
<Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisAsleepCore" startDate="{d} 00:10:00 +0100" endDate="{d} 04:10:00 +0100"/>
<Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisAsleepDeep" startDate="{d} 04:10:00 +0100" endDate="{d} 07:40:00 +0100"/>
<Record type="HKCategoryTypeIdentifierSleepAnalysis" value="HKCategoryValueSleepAnalysisInBed" startDate="{d} 00:00:00 +0100" endDate="{d} 08:00:00 +0100"/>
<Record type="HKQuantityTypeIdentifierStepCount" value="4200" startDate="{d} 10:00:00 +0100" endDate="{d} 11:00:00 +0100"/>
<Record type="HKQuantityTypeIdentifierStepCount" value="800" startDate="{d} 15:00:00 +0100" endDate="{d} 15:30:00 +0100"/>
<Record type="HKQuantityTypeIdentifierStepCount" value="9999" startDate="2001-01-01 10:00:00 +0100" endDate="2001-01-01 11:00:00 +0100"/>
<Workout workoutActivityType="HKWorkoutActivityTypeRunning" duration="32.5" durationUnit="min" startDate="{d} 18:00:00 +0100" endDate="{d} 18:32:00 +0100"/>
</HealthData>""".encode()
    pre = client.post("/api/import/health", data={"space": sid}, files={"file": ("export.xml", xml, "text/xml")}).json()
    assert (pre["noches"], pre["entrenamientos"], pre["dias_de_pasos"], pre["aplicado"]) == (1, 1, 1, False) and records.list_records(sid, "sleep") == []
    client.post("/api/import/health", data={"space": sid, "commit": "si"}, files={"file": ("export.xml", xml, "text/xml")})
    night = records.list_records(sid, "sleep")[0]
    assert night["data"]["hours"] == 7.5 and records.list_records(sid, "workout")[0]["data"] == {"date": d, "type": "cardio", "minutes": 32, "notes": "Importado de Apple Health: Running"}
    assert "5000 pasos" in records.list_records(sid, "activity")[0]["data"]["notes"]
    again = client.post("/api/import/health", data={"space": sid, "commit": "si"}, files={"file": ("export.xml", xml, "text/xml")}).json()
    assert again["duplicados"] == 3 and len(records.list_records(sid, "sleep")) == 1
    assert client.post("/api/import/health", data={"space": sid}, files={"file": ("x.xml", b"<roto", "text/xml")}).status_code == 400
    ofx = """OFXHEADER:100\n<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS><CURDEF>EUR<BANKTRANLIST>
<STMTTRN><TRNTYPE>CREDIT<DTPOSTED>20261103120000<TRNAMT>1500.00<FITID>A1<NAME>Cliente Uno<MEMO>Factura 12</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20261104<TRNAMT>-49,90<FITID>A2<NAME>Hosting SL</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>roto<TRNAMT>x<FITID>A3</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>"""
    r = client.post("/api/import/ofx", data={"space": sid, "commit": "si"}, files={"file": ("banco.ofx", ofx.encode(), "application/x-ofx")}).json()
    assert (r["nuevos"], r["errores"], r["moneda"]) == (2, 1, "EUR")
    tx = {t["title"]: t["data"] for t in records.list_records(sid, "transaction")}
    assert tx["Cliente Uno"]["type"] == "ingreso" and tx["Cliente Uno"]["stage"] == "cobrado" and tx["Hosting SL"]["amount"] == 49.9 and tx["Hosting SL"]["date"] == "2026-11-04"
    assert client.post("/api/import/ofx", data={"space": sid, "commit": "si"}, files={"file": ("banco.ofx", ofx.encode(), "x")}).json()["duplicados"] == 2
    assert client.post("/api/import/ofx", data={"space": sid}, files={"file": ("x.ofx", b"hola", "x")}).status_code == 400


# ---------- Tutor, preguntas a las notas y texto bíblico

def test_study_plan_and_ask_notes(fake, conn, space, client):
    from jarvis import files
    sid = space()
    f = files.save_bytes(sid, "curso.txt", ("El recuerdo activo consiste en recuperar la información sin mirarla. " * 20).encode(), origin="upload")
    j, _ = jobs.enqueue(sid, "study_plan", "Ruta", {"file_id": f["id"]})
    run_all()
    assert jobs.get(j["id"])["status"] == "waiting_config"                                   # sin modelo: espera, no inventa
    conn()
    fake.llm = lambda s, u: json.dumps({"modules": [{"title": "Recuerdo activo", "objectives": ["Entenderlo"], "key_ideas": ["Recuperar sin mirar"], "exercise": "Explícalo"}],
                                        "flashcards": [{"front": "¿Qué es el recuerdo activo?", "back": "Recuperar sin mirar"}, {"front": "¿Qué es el recuerdo activo?", "back": "dup"}],
                                        "quiz": [{"question": "¿Sirve releer?", "answer": "Menos que recordar"}]})
    jobs.retry(j["id"])
    run_all()
    done = jobs.get(j["id"])
    assert done["status"] == "completed" and done["result"]["tarjetas"] == 1
    card = records.list_records(sid, "flashcard")[0]
    assert card["data"]["deck"] == "curso" and card["data"]["due"] == date.today().isoformat()
    assert "100 %" in json.dumps(review.detail(done["result"]["deliverable_ids"][0], sid)["version"]["content"], ensure_ascii=False)
    note = records.create(sid, "note", "Adquisición de clientes B2B", {"body": "Las referencias de clientes convierten mejor que los anuncios fríos."})
    records.create(sid, "note", "Receta de pan", {"body": "Harina y agua."})
    seen = {}

    def llm(system, user):
        seen["user"] = user
        return json.dumps({"answer": "Aprendiste que las referencias convierten mejor.", "cited": [note["id"], "not_inventada"]})

    fake.llm = llm
    out = client.post("/api/life/ask", json={"space": sid, "question": "¿Qué aprendí sobre adquisición de clientes?"}).json()
    assert [s["id"] for s in out["sources"]] == [note["id"]] and "Receta de pan" not in seen["user"]
    assert client.post("/api/life/ask", json={"space": sid, "question": "zzzz qqqq"}).json()["sources"] == []
    personal = space("Personal", "personal", "solo_local")
    records.create(personal, "note", "Clientes y dudas", {"body": "nota privada sobre clientes"})
    before = fake.count("llm.test")
    assert client.post("/api/life/ask", json={"space": personal, "question": "clientes"}).status_code == 409 and fake.count("llm.test") == before   # lo personal no sale a la nube


def test_scripture_is_user_loaded(client):
    assert client.get("/api/scripture").json() == []
    text = "\n".join(["Juan 3:16\tPorque de tal manera amó Dios al mundo", "Juan 3:17\tPorque no envió Dios a su Hijo para condenar", "Salmos 23:1\tJehová es mi pastor; nada me faltará"] + [f"Génesis 1:{i}\tverso {i}" for i in range(1, 12)])
    r = client.post("/api/scripture", data={"name": "rv1909", "title": "Reina-Valera 1909", "license": "Dominio público"}, files={"file": ("rv.txt", text.encode(), "text/plain")}).json()
    assert r == {"translation": "RV1909", "verses": 14, "books": 3}
    p = client.get("/api/scripture/RV1909/passage", params={"ref": "juan 3:16-17"}).json()
    assert p["reference"] == "Juan 3:16-17" and len(p["verses"]) == 2 and "amó Dios" in p["verses"][0]["text"]
    assert len(client.get("/api/scripture/RV1909/passage", params={"ref": "Gen 1"}).json()["verses"]) == 11
    s = client.get("/api/scripture/RV1909/search", params={"q": "Dios"}).json()
    assert s["total"] == 2 and s["results"][0]["book"] == "Juan"
    assert client.get("/api/scripture/RV1909/passage", params={"ref": "Apocalipsis 99"}).status_code == 404
    assert client.post("/api/scripture", data={"name": "x"}, files={"file": ("x.txt", b"nada util", "text/plain")}).status_code == 400
    client.delete("/api/scripture/RV1909")
    assert client.get("/api/scripture").json() == []


# ---------- Usuarios con rol

def test_roles_restrict_remote_users_to_their_spaces(monkeypatch, space, conn, fake, client):
    from fastapi.testclient import TestClient
    from jarvis.api import app
    monkeypatch.setenv("JARVIS_HOST", "0.0.0.0")
    monkeypatch.setenv("JARVIS_ACCESS_CODE", "codigo-largo-de-casa")
    access._failures.clear()
    a, b, personal = space("Cliente A"), space("Cliente B"), space("Personal", "personal", "solo_local")
    d = review.create(a, "documento", "Informe", {"sections": [{"key": "c", "title": "C", "type": "text", "body": "x"}]})
    conn()
    for bad in ({"username": "ana", "role": "equipo", "spaces": [personal], "password": "contrasena-larga"}, {"username": "ana", "role": "equipo", "spaces": [a], "password": "corta"},
                {"username": "ana", "role": "admin", "spaces": [a], "password": "contrasena-larga"}):
        assert client.post("/api/users", json=bad).status_code == 400
    ana = client.post("/api/users", json={"username": "Ana", "role": "equipo", "spaces": [a], "password": "contrasena-larga"}).json()
    client.post("/api/users", json={"username": "cli", "role": "cliente", "spaces": [a], "password": "otra-contrasena-1"})
    assert "pass_hash" not in ana and "contrasena" not in config.db_path().read_bytes().decode("latin-1")
    net = lambda ip: TestClient(app, client=(ip, 5000), base_url="http://192.168.1.20:8765")
    team = net("192.168.1.51")
    assert team.post("/api/login", json={"user": "ana", "password": "mala"}).status_code == 400
    assert team.post("/api/login", json={"user": "ana", "password": "contrasena-larga"}).status_code == 200
    boot = team.get("/api/bootstrap").json()
    assert boot["user"] == {"username": "ana", "role": "equipo"} and [s["id"] for s in boot["spaces"]] == [a]
    assert team.post("/api/records", json={"space": a, "kind": "task", "title": "De Ana"}).status_code == 200
    assert team.post("/api/records", json={"space": b, "kind": "task", "title": "Intrusa"}).status_code == 403
    assert team.get("/api/records", params={"space": b, "kind": "task"}).status_code == 403 and team.get("/api/jobs").status_code == 403
    for path in ("/api/connections", "/api/users", "/api/backups", "/api/diagnostics", "/api/usage", "/api/events", "/api/spaces"):
        assert team.get(path).status_code == 403, path
    assert team.patch("/api/settings", json={"allow_paid": True}).status_code == 403
    assert team.post(f"/api/deliverables/{d['id']}/approve", json={"space": a, "version": 1}).status_code == 403
    assert team.post("/api/jobs", json={"space": a, "type": "external_export", "params": {}}).status_code == 403
    assert team.post("/api/jobs", json={"space": a, "type": "lead_search", "params": {"sector": "x"}}).status_code == 200
    cli = net("192.168.1.52")
    cli.post("/api/login", json={"user": "cli", "password": "otra-contrasena-1"})
    assert cli.get(f"/api/deliverables/{d['id']}", params={"space": a}).status_code == 200
    assert cli.post(f"/api/deliverables/{d['id']}/comments", json={"space": a, "body": "Me gusta"}).status_code == 200
    assert cli.get("/api/records", params={"space": a, "kind": "task"}).status_code == 403
    assert cli.post(f"/api/deliverables/{d['id']}/versions", json={"space": a, "content": {}}).status_code == 403
    assert cli.get(f"/api/deliverables/{d['id']}", params={"space": b}).status_code == 403
    owner = net("192.168.1.53")
    owner.post("/api/login", json={"code": "codigo-largo-de-casa"})
    assert owner.get("/api/connections").status_code == 200 and owner.get("/api/bootstrap").json()["user"]["role"] == "propietario"
    client.patch(f"/api/users/{ana['id']}", json={"username": "ana", "role": "equipo", "spaces": [a], "active": False})
    assert team.get("/api/bootstrap").status_code == 401                                     # desactivar revoca la sesión al instante


# ---------- MCP y API para otros programas

def test_mcp_server_exposes_internal_tools(space):
    sid = space("Estudio")
    space("Personal", "personal", "solo_local")
    msgs = [{"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "t", "version": "0"}}},
            {"jsonrpc": "2.0", "method": "notifications/initialized"}, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "capturar", "arguments": {"text": "Llamar al gestor", "as_task": True}}},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {"name": "enviar_email", "arguments": {}}},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {"name": "buscar_leads", "arguments": {"sector": ""}}}]
    res = subprocess.run([sys.executable, "-m", "jarvis.mcp_server"], input="\n".join(json.dumps(m) for m in msgs) + "\n", capture_output=True, text=True,
                         cwd=str(config.REPO_ROOT / "backend"), env=os.environ.copy(), timeout=60)
    out = {m["id"]: m for m in map(json.loads, res.stdout.strip().splitlines())}
    assert len(out) == 5 and out[1]["result"]["serverInfo"]["name"] == "jarvis-os" and "Estudio" in out[1]["result"]["instructions"]
    names = {t["name"] for t in out[2]["result"]["tools"]}
    assert {"buscar_oportunidades", "resumen_pendientes", "pausar_agentes"} <= names and all(t["inputSchema"]["type"] == "object" for t in out[2]["result"]["tools"])
    assert "Tarea creada" in out[3]["result"]["content"][0]["text"] and records.list_records(sid, "task")[0]["title"] == "Llamar al gestor"
    assert out[4]["error"]["code"] == -32602 and out[5]["result"]["isError"] is True


def test_external_command_api_needs_token(space, client):
    sid = space("Estudio")
    assert client.post("/api/ext/command", json={"text": "tarea: x"}).status_code == 401
    token = client.post("/api/token").json()["token"]
    assert token.startswith("jrv_") and token not in json.dumps(db.query("SELECT * FROM settings"))
    r = client.post("/api/ext/command", json={"text": "tarea: revisar pedidos", "space": "estudio"}, headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200 and r.json()["tool"] == "capturar" and records.list_records(sid, "task")[0]["title"] == "revisar pedidos"
    new = client.post("/api/token").json()["token"]
    assert client.post("/api/ext/command", json={"text": "x"}, headers={"Authorization": f"Bearer {token}"}).status_code == 401   # rotar invalida el anterior
    assert client.post("/api/ext/command", json={"text": "resume lo pendiente"}, headers={"Authorization": f"Bearer {new}"}).status_code == 200
