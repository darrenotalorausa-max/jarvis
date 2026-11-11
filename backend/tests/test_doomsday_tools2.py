"""Doomsday: funcionalidad propia de cada módulo (sin IA) y planes de acciones externas con una sola aprobación."""
import io
import json
import zipfile
from datetime import date, timedelta

import httpx
import pytest

from jarvis import db, files, jobs, records, review
from conftest import run_all
from test_doomsday import dd  # noqa: F401
from test_doomsday_integrations import _api_conn


def _tool(c, module, tool, inputs=None, **kw):
    return c.post(f"/api/dd/tools/{tool}", json={"module": module, "inputs": inputs or {}, **kw})


def test_every_module_has_its_own_function_and_no_tool_crashes_empty(dd):
    from doomsday import catalog, tools
    c = dd["client"]
    sin = [m["id"] for m in catalog.MODULES.values() if not m["tools"] and not m["widget"]]
    assert sin == [], f"módulos que solo dependen de IA: {sin}"
    assert len(tools.TOOLS) >= 60
    for m in catalog.MODULES.values():
        for t in m["tools"]:
            r = _tool(c, m["id"], t)
            assert r.status_code in (200, 400), (m["id"], t, r.text[:300])  # 400 = pide una entrada obligatoria, nunca un error interno
            if r.status_code == 200:
                assert set(r.json()) >= {"resumen", "metricas", "tablas", "alertas"}


def test_search_voice_hooks_and_ideas(dd):
    c, sid = dd["client"], dd["spaces"]["interna"]
    txt = "¿Sabes por qué tu tienda no vende? Te lo digo de una. La verdad es que el problema no es el producto. La verdad es que es la oferta. " * 3
    records.create(sid, "dd_pieza", "Video ofertas", {"tipo": "transcripcion", "texto": txt, "vistas": 90000})
    records.create(sid, "dd_pieza", "Video logística", {"tipo": "transcripcion", "texto": "Hoy hablamos de transportadoras y de devoluciones en contra entrega. " * 6, "vistas": 500})
    r = _tool(c, "C10", "buscar", {"consulta": "oferta producto"}).json()
    assert r["tablas"][0]["filas"][0][0] == "Video ofertas" and "oferta" in r["tablas"][0]["filas"][0][2].lower()
    assert _tool(c, "C10", "buscar", {"consulta": "criptomonedas"}).json()["alertas"]
    v = _tool(c, "C02", "perfil_voz").json()
    assert v["metricas"][0]["valor"] == 2 and any("la verdad es" in f[0] for f in v["tablas"][0]["filas"])
    h = _tool(c, "C03", "hooks", {"hooks": "¿Sabes por qué tu tienda no vende 3 pedidos al día?\nEl mejor del mundo increíble producto que te va a volar la cabeza hoy mismo sin duda alguna de verdad"}).json()
    assert h["tablas"][0]["filas"][0][0].startswith("¿Sabes") and h["tablas"][0]["filas"][0][1] > h["tablas"][0]["filas"][1][1]
    records.create(sid, "dd_idea", "Idea completa", {"angulo": "contra la creencia X", "formato": "corto", "canal": "ig", "prioridad": "alta"})
    records.create(sid, "dd_idea", "Idea vaga", {"prioridad": "baja"})
    i = _tool(c, "C01", "ideas").json()
    assert i["tablas"][0]["filas"][0][0] == "Idea completa" and i["metricas"][1]["valor"] == 1


def test_documents_from_templates_are_saved_as_deliverables(dd):
    c, sid = dd["client"], dd["spaces"]["clientes"]
    assert "Registra tus planes" in _tool(c, "V02", "propuesta", {"empresa": "Acme"}).json()["detail"]
    records.create(sid, "dd_plan", "Growth Sprint", {"alcance": "Auditoría de cuenta\n20 creativos al mes", "exclusiones": "Presupuesto de pauta", "precio": 1500, "duracion": "3 meses"})
    records.create(sid, "dd_caso", "Caso sin permiso", {"cliente": "Zeta", "resultado": "ROAS 5", "autorizado": False})
    records.create(sid, "dd_caso", "Caso ok", {"cliente": "Beta", "resultado": "CPA de 12 a 7 en 60 días", "autorizado": True, "evidencia_url": "https://ev.test/1"}, status="autorizado")
    r = _tool(c, "V02", "propuesta", {"empresa": "Acme", "plan": "growth sprint", "problema": "No sabe qué anuncio gana"}, guardar=True).json()
    d = review.detail(r["deliverable_id"], sid)
    body = json.dumps(d["version"]["content"], ensure_ascii=False)
    assert d["title"] == "V02 · Propuesta para Acme" and "20 creativos al mes" in body and "Beta" in body and "Zeta" not in body and "1,500" in body
    assert d["version"]["content"]["meta"]["sin_ia"] is True
    rep = _tool(c, "V03", "reporte", {"cliente": "Acme", "periodo": "Noviembre", "cifras": "Ventas; 120; 100\nCPA; 9; 6"}).json()
    assert rep["tablas"][0]["filas"] == [["Ventas", 120, 100, 20.0], ["CPA", 9, 6, 50.0]]
    assert _tool(c, "V10", "casos").json()["metricas"][1]["valor"] == 1


def test_contract_billing_and_client_acceptance(dd):
    from doomsday import app as dd_app
    from jarvis import access
    c = dd["client"]
    acme = c.post("/api/dd/clients", json={"nombre": "Acme"}).json()["id"]
    records.create(acme, "dd_plan", "Growth Partner", {"alcance": "Gestión de pauta", "exclusiones": "Producción de video", "precio": 2000})
    r = _tool(c, "V08", "contrato", {"cliente": "Acme SAS", "plan": "Growth Partner", "ciudad": "Bogotá, Colombia"}, guardar=True, space=acme).json()
    did = r["deliverable_id"]
    assert records.list_records(acme, "dd_contrato")[0]["status"] == "borrador"
    sign = {"space": acme, "deliverable_id": did, "nombre": "Ana Pérez", "acepto": True}
    assert "aún no está listo" in c.post("/api/dd/sign", json=sign).json()["detail"]
    v = review.detail(did, acme)["version"]["version"]
    review.set_status(did, acme, "en_revision")
    review.approve(did, acme, version=v, user="yo")
    assert c.post("/api/dd/sign", json={**sign, "acepto": False}).status_code == 400
    ok = c.post("/api/dd/sign", json=sign).json()
    firma = records.list_records(acme, "dd_firma")[0]["data"]
    assert ok["ok"] and firma["nombre"] == "Ana Pérez" and firma["huella"] == ok["huella"] and firma["version"] == v
    assert records.list_records(acme, "dd_contrato")[0]["status"] == "firmado"
    assert "ya fue aceptada" in c.post("/api/dd/sign", json=sign).json()["detail"]
    # El rol cliente alcanza solo esta ruta de Doomsday, y solo dentro de su espacio (lo impone el guardián del motor).
    assert access.allowed({"role": "cliente"}, "POST", "/api/dd/sign") and not access.allowed({"role": "cliente"}, "POST", "/api/dd/run")
    assert c.post("/api/dd/sign", json={**sign, "space": dd["spaces"]["clientes"]}).status_code == 404
    cob = _tool(c, "V08", "cobros", space=acme).json()
    assert cob["metricas"][0]["valor"] == 2000 and cob["tablas"][0]["filas"][0][5] == "por cobrar este mes"
    records.update(records.list_records(acme, "dd_contrato")[0]["id"], acme, {"data": {"ultimo_pago": date.today().isoformat()}})
    assert _tool(c, "V08", "cobros", space=acme).json()["tablas"][0]["filas"][0][5] == "al día"


def test_checklists_messages_meeting_call_and_code(dd):
    c, interna, cli, per = dd["client"], dd["spaces"]["interna"], dd["spaces"]["clientes"], dd["spaces"]["personal"]
    p = _tool(c, "G03", "pasos", {"plantilla": "tienda_shopify_cod", "nombre": "Tienda Faja"}).json()
    pasos = records.list_records(interna, "dd_paso", limit=100)
    assert len(pasos) == 20 and p["tablas"][0]["filas"][0][:3] == ["Tienda Faja", 0, 20]
    assert _tool(c, "G03", "pasos", {"plantilla": "tienda_shopify_cod", "nombre": "Tienda Faja"}).status_code == 400
    records.update(sorted(pasos, key=lambda x: x["title"])[0]["id"], interna, {"status": "hecho"})
    assert _tool(c, "G03", "pasos").json()["tablas"][0]["filas"][0][3] == "5.0 %"
    # Bandeja: estado real del pedido, base de respuestas y escalado.
    records.create(interna, "dd_pedido", "#5001", {"ref": "#5001", "producto": "Faja"}, status="en_transito")
    records.create(interna, "dd_conocimiento", "Tallas", {"tema": "tallas", "contenido": "La faja viene en tallas S a XL; mide tu cintura."})
    for t, txt in (("Ana", "Hola, ¿dónde está mi pedido 5001?"), ("Luis", "¿Qué tallas tiene la faja y cuánto cuesta?"), ("Eva", "Esto es una estafa, quiero mi reembolso"), ("X", "ok")):
        records.create(interna, "dd_mensaje", t, {"canal": "whatsapp", "remitente": t, "texto": txt})
    m = _tool(c, "A02", "mensajes").json()
    by = {r["title"]: r for r in records.list_records(interna, "dd_mensaje")}
    assert by["Ana"]["status"] == "borrador_listo" and "#5001 está: en camino" in by["Ana"]["data"]["borrador"]
    assert by["Luis"]["status"] == "borrador_listo" and "S a XL" in by["Luis"]["data"]["borrador"]
    assert by["Eva"]["status"] == "escalado" and "borrador" not in by["Eva"]["data"] and by["X"]["status"] == "nuevo" and m["metricas"][2]["valor"] == 1
    r = _tool(c, "R05", "reunion", {"titulo": "Semanal", "transcripcion": "Ana: me encargo de enviar la propuesta para el viernes.\nAcordamos subir el presupuesto a 50.\nLuis: hay que revisar el píxel de la tienda nueva.\nHizo buen clima."}).json()
    assert r["metricas"][2]["valor"] == 1 and {t["data"].get("responsable") for t in records.list_records(per, "dd_tarea")} == {"Ana", "Luis"}
    ll = _tool(c, "R10", "llamada", {"transcripcion": "Yo: Hola, te cuento todo lo que hacemos. " + "Somos los mejores en pauta y hacemos de todo. " * 6 + "\nCliente: Me parece caro, déjame pensarlo.\nYo: ¿Qué es lo que más te preocupa?\nCliente: El precio, y lo hablo con mi socio.\nYo: Vale."}).json()
    assert ll["metricas"][0]["tono"] == "bad" and {o[0] for o in ll["tablas"][0]["filas"]} >= {"precio", "pensarlo", "socio"} and len(ll["alertas"]) >= 2
    diff = "diff --git a/app.py b/app.py\n+++ b/app.py\n@@ -1 +1,3 @@\n+API_KEY = \"sk-abcdefghijklmnopqrstuvwxyz123\"\n+print(x)\n+    except Exception: pass\n-old\n"
    rc = _tool(c, "A07", "revision_codigo", {"diff": diff}).json()
    assert rc["metricas"][3]["valor"] >= 1 and rc["alertas"] and {h[1] for h in rc["tablas"][0]["filas"]} >= {"depuración olvidada", "excepción silenciada"}
    assert _tool(c, "A07", "revision_codigo", {"diff": "hola"}).status_code == 400


def test_design_packages_theme_and_personal_tools(dd):
    c, interna, com, per = dd["client"], dd["spaces"]["interna"], dd["spaces"]["comercial"], dd["spaces"]["personal"]
    for t, tipo, val in (("Fondo", "color", "#ffffff"), ("Tinta", "color", "#111111"), ("Acento", "color", "#ffee88"), ("Cuerpo", "tipografia", "Georgia, serif")):
        records.create(interna, "dd_token", t, {"marca": "Acme", "tipo": tipo, "valor": val})
    tk = _tool(c, "X04", "tokens_css", {"marca": "acme"}).json()
    assert "--tinta: #111111;" in tk["texto"] and {f[0]: f[3] for f in tk["tablas"][0]["filas"]} == {"Tinta": "AA texto", "Acento": "NO cumple"}
    pk = _tool(c, "S06", "paquete_skills", {"skills": "g04, M06 zz9", "nombre": "Pack ecommerce"}).json()
    z = zipfile.ZipFile(files.path_of(files.get(pk["archivo"]["id"], com)))
    assert sorted(z.namelist()) == ["LEEME.md", "LICENCIA.md", "skills/G04.md", "skills/M06.md"] and "Estratega de conversión" in z.read("skills/G04.md").decode()
    th = _tool(c, "S01", "tema", {"_descargar": True}).json()
    z = zipfile.ZipFile(files.path_of(files.get(th["archivo"]["id"], com)))
    from doomsday import content
    assert len(content.SECTIONS) == 6 and all(f"sections/{k}.liquid" in z.namelist() for k in content.SECTIONS)
    for k, s in content.SECTIONS.items():
        schema = json.loads(s["liquid"].split("{% schema %}")[1].split("{% endschema %}")[0])  # el esquema de cada sección es JSON válido
        assert schema["name"].startswith("DD · ") and schema["presets"] and s["liquid"].count("{%- if") + s["liquid"].count("{% if") == s["liquid"].count("endif")
    pe = _tool(c, "H10", "plan_estudio", {"materia": "Cálculo", "fecha": (date.today() + timedelta(days=20)).isoformat(), "temas": "Límites\nDerivadas\nIntegrales"}).json()
    assert pe["metricas"][1]["valor"] == 3 and any("Simulacro" in f[1] for f in pe["tablas"][0]["filas"]) and any("Repasar: Límites" in f[1] for f in pe["tablas"][0]["filas"])
    en = _tool(c, "H04", "ingles", {"tema": "objeciones"}).json()
    assert len(records.list_records(per, "flashcard", limit=100)) == 6 and "tarjetas nuevas" in en["resumen"]
    assert "0 tarjetas nuevas" in _tool(c, "H04", "ingles", {"tema": "objeciones"}).json()["resumen"]
    records.create(per, "sleep", "Noche importada", {"date": "2026-11-01", "hours": 6}) if "sleep" in records.KINDS else None
    for d, h in (("2026-11-02", 7), ("2026-11-03", 8)):
        records.create(per, "dd_sueno", d, {"fecha": d, "horas": h})
    assert _tool(c, "H02", "sueno").json()["metricas"][0]["valor"] == "7.0 h"


def test_web_tools_read_public_pages_only(dd, fake):
    c, sid = dd["client"], dd["spaces"]["interna"]
    fake.pages["https://rival.test/"] = "<html><head><title>Rival</title><meta name='description' content='Fajas'></head><body><p>Faja premium por $ 89.900 con envío gratis a todo el país desde hoy mismo.</p><a href='https://instagram.com/rival'>IG</a></body></html>"
    f = _tool(c, "A05", "ficha_web", {"enlace": "https://rival.test/"}).json()
    assert f["metricas"][2]["valor"] == 1 and "instagram" in json.dumps(f["tablas"])
    records.create(sid, "dd_competidor", "Rival", {"url": "https://rival.test/"})
    assert _tool(c, "M05", "vigia").json()["tablas"][0]["filas"][0][1] == "primera lectura"
    assert _tool(c, "M05", "vigia").json()["tablas"][0]["filas"][0][1] == "sin cambios"
    fake.pages["https://rival.test/"] = fake.pages["https://rival.test/"].replace("89.900", "69.900")
    v = _tool(c, "M05", "vigia").json()
    assert v["tablas"][0]["filas"][0][1] == "CAMBIÓ" and "69.900" in v["alertas"][0] and len(records.list_records(sid, "dd_alerta")) == 1
    largo = " ".join(f"La utilidad neta en contra entrega depende de la tasa de entrega número {i} y del flete de cada ciudad." for i in range(12))
    e = _tool(c, "H07", "extracto", {"texto": largo, "frases": 3}).json()
    assert e["metricas"][1]["valor"] == 3 and records.list_records(dd["spaces"]["personal"], "dd_fuente")[0]["status"] == "resumido"
    assert _tool(c, "A05", "ficha_web", {"enlace": "http://localhost/x"}).status_code == 400


# ---------- Planes con una sola aprobación

def _approve(c, job_id, **body):
    run_all()
    assert jobs.get(job_id)["status"] == "waiting_approval"
    assert c.post(f"/api/dd/plans/{job_id}/approve", json=body).status_code == 200


def test_instagram_publication_plan_schedule_and_single_use(dd, fake):
    c, sid = dd["client"], dd["spaces"]["interna"]
    cn = _api_conn("redes_meta")
    pieza = records.create(sid, "dd_pieza", "Reel faja", {"tipo": "post", "texto": "Tu espalda te lo agradece."}, status="aprobado")
    seq = iter([{"id": "c1"}, {"status_code": "IN_PROGRESS"}, {"status_code": "FINISHED"}, {"id": "p9"}])
    fake.custom["graph.facebook.com"] = lambda req: httpx.Response(200, json=next(seq))
    r = c.post("/api/dd/social/publish", json={"connection_id": cn["id"], "red": "instagram", "record_id": pieza["id"], "cuenta": "17841400000", "media_url": "https://cdn.test/reel.mp4"}).json()
    assert [p["paso"] for p in r["pasos"]] == ["Crear el contenedor", "Esperar a que Instagram procese el video", "Publicar"] and r["pasos"][0]["cuerpo"]["media_type"] == "REELS"
    jid = r["job"]["id"]
    run_all()
    assert not fake.calls and c.get("/api/dd/plans", params={"module": "C05"}).json()[0]["id"] == jid
    # Programado: aprobado ahora, no se ejecuta hasta su hora.
    when = (date.today() + timedelta(days=2)).isoformat() + "T09:00:00"
    assert c.post(f"/api/dd/plans/{jid}/approve", json={"at": when}).json()["resume_at"].startswith((date.today() + timedelta(days=2)).isoformat()[:8])
    run_all()
    assert not fake.calls and jobs.get(jid)["status"] == "pending"
    db.execute("UPDATE jobs SET resume_at=NULL WHERE id=?", (jid,))  # llega la hora
    run_all()
    job = jobs.get(jid)
    assert job["status"] == "completed" and job["result"]["ids"] == {"creacion": "c1", "publicacion": "p9"} and len(fake.calls) == 4
    assert json.loads(fake.calls[0].content)["caption"] == "Tu espalda te lo agradece." and fake.calls[-1].url.path.endswith("/17841400000/media_publish")
    assert records.get(pieza["id"])["status"] == "publicado"
    assert c.post(f"/api/dd/plans/{jid}/approve", json={}).status_code == 400  # la aprobación ya se consumió
    assert c.post("/api/dd/social/publish", json={"connection_id": cn["id"], "red": "tiktok", "texto": "x"}).status_code == 400
    assert c.post("/api/dd/social/publish", json={"connection_id": cn["id"], "red": "instagram", "texto": "x", "cuenta": "1", "media_url": "http://x/a.jpg"}).status_code == 400


def test_meta_launch_creates_everything_paused_and_stops_on_failure(dd, fake):
    c, sid = dd["client"], dd["spaces"]["interna"]
    cn = _api_conn("meta_ads")
    ok = records.create(sid, "dd_creativo", "faja_dolor_v01", {"producto": "Faja", "hook": "¿Te duele la espalda?", "guion": "Acompaña tu postura.", "imagen_url": "https://cdn.test/1.jpg"}, status="aprobado")
    malo = records.create(sid, "dd_creativo", "faja_cura_v02", {"hook": "Cura la escoliosis", "guion": "Esta faja cura el dolor de espalda para siempre", "imagen_url": "https://cdn.test/2.jpg"}, status="aprobado")
    base = {"connection_id": cn["id"], "cuenta": "123", "pagina_id": "555", "pixel_id": "777", "destino": "https://tienda.test/p", "presupuesto_diario": 20, "pais": "co"}
    assert "Cumplimiento" in c.post("/api/dd/ads/launch", json={**base, "creativos": [ok["id"], malo["id"]]}).json()["detail"]
    r = c.post("/api/dd/ads/launch", json={**base, "creativos": [ok["id"]]}).json()
    cuerpos = [p["cuerpo"] for p in r["pasos"]]
    assert len(r["pasos"]) == 4 and all(b.get("status", "PAUSED") == "PAUSED" for b in cuerpos) and cuerpos[1]["daily_budget"] == "2000" and cuerpos[1]["targeting"] == {"geo_locations": {"countries": ["CO"]}}
    assert "utm_content=faja_dolor_v01" in cuerpos[2]["object_story_spec"]["link_data"]["link"]
    ids = iter(["cam1", "set1"])
    fake.custom["graph.facebook.com"] = lambda req: httpx.Response(400, json={"error": {"message": "Invalid picture"}}) if req.url.path.endswith("/adcreatives") else httpx.Response(200, json={"id": next(ids)})
    _approve(c, r["job"]["id"])
    run_all()
    job = jobs.get(r["job"]["id"])
    assert job["status"] == "failed" and "paso 3" in job["error"] and "Crear campaña (en pausa), Crear conjunto de anuncios (en pausa)" in job["error"]
    assert json.loads(fake.calls[1].content)["campaign_id"] == "cam1" and records.get(ok["id"])["status"] == "aprobado"


def test_capi_discord_theme_gmail_and_oura(dd, fake):
    from doomsday import plans
    c, sid, per = dd["client"], dd["spaces"]["interna"], dd["spaces"]["personal"]
    # Compras entregadas → API de conversiones, con el teléfono solo como huella.
    csv_text = "ID;ESTADO;TOTAL;TELEFONO;FECHA\nK1;ENTREGADO;89900;300 123 4567;%s\nK2;ENTREGADO;50000;;%s\n" % (date.today().isoformat(), date.today().isoformat())
    c.post("/api/dd/import/logistica", files={"file": ("d.csv", csv_text.encode(), "text/csv")}, data={"commit": "1"})
    k1 = next(o for o in records.list_records(sid, "dd_pedido") if o["title"] == "K1")
    assert k1["data"]["tel_hash"] == plans.phone_hash("+57 3001234567") and "3001234567" not in json.dumps(db.query("SELECT data FROM records"))
    meta = _api_conn("meta_ads")
    fake.custom["graph.facebook.com"] = lambda req: httpx.Response(200, json={"events_received": 1})
    r = c.post("/api/dd/capi/send", json={"connection_id": meta["id"], "pixel_id": "777"}).json()
    ev = r["pasos"][0]["cuerpo"]["data"]
    assert r["eventos"] == 1 and ev[0]["event_id"] == "K1" and ev[0]["user_data"] == {"ph": [k1["data"]["tel_hash"]]} and ev[0]["custom_data"]["value"] == 89900
    _approve(c, r["job"]["id"])
    run_all()
    assert jobs.get(r["job"]["id"])["status"] == "completed" and records.get(k1["id"])["data"]["capi_enviado"] is True
    assert c.post("/api/dd/capi/send", json={"connection_id": meta["id"], "pixel_id": "777"}).status_code == 400  # no se reenvía
    # Discord: estructura y bienvenida.
    dc = _api_conn("discord")
    for t, tipo, cont in (("general", "canal", "Charla"), ("Alumno", "rol", ""), ("Reglas", "regla", "Respeto ante todo.")):
        records.create(per, "dd_comunidad", t, {"tipo": tipo, "contenido": cont})
    fake.custom["discord.com"] = lambda req: httpx.Response(200, json=[{"user": {"id": "1", "username": "ana"}}, {"user": {"id": "2", "username": "bot", "bot": True}}] if req.method == "GET" else {"id": "x"})
    r = c.post("/api/dd/discord/apply", json={"connection_id": dc["id"], "servidor": "900", "canal_mensajes": "901"}).json()
    assert [p["metodo"] + " " + p["url"].split("/api/v10")[1] for p in r["pasos"]] == ["POST /guilds/900/channels", "POST /guilds/900/roles", "POST /channels/901/messages"]
    _approve(c, r["job"]["id"])
    run_all()
    assert jobs.get(r["job"]["id"])["status"] == "completed" and {x["status"] for x in records.list_records(per, "dd_comunidad")} == {"activo"}
    assert fake.calls[-1].headers["authorization"] == "token-de-prueba-1234567890"
    assert "Primera lectura" in c.post("/api/dd/discord/welcome", json={"connection_id": dc["id"], "servidor": "900", "canal_mensajes": "901"}).json()["nota"]
    fake.custom["discord.com"] = lambda req: httpx.Response(200, json=[{"user": {"id": "1", "username": "ana"}}, {"user": {"id": "3", "username": "luis"}}])
    w = c.post("/api/dd/discord/welcome", json={"connection_id": dc["id"], "servidor": "900", "canal_mensajes": "901"}).json()
    assert w["nuevos"] == 1 and w["pasos"][0]["cuerpo"]["content"].startswith("<@3> ")
    # Tema: las secciones se suben tal cual (el Liquid no se toca).
    shop = _api_conn("shopify", "https://t.myshopify.com/admin/api/2026-10", "Tienda")
    th = c.post("/api/dd/theme/upload", json={"connection_id": shop["id"], "tema_id": "123", "secciones": ["dd-packs"]}).json()
    assert th["pasos"][0]["metodo"] == "PUT" and "{%- form 'product', p" in th["pasos"][0]["cuerpo"]["asset"]["value"]
    fake.custom["t.myshopify.com"] = lambda req: httpx.Response(200, json={"asset": {}})
    _approve(c, th["job"]["id"])
    run_all()
    assert jobs.get(th["job"]["id"])["status"] == "completed" and "{{ section.settings.heading | escape }}" in json.loads(fake.calls[-1].content)["asset"]["value"]
    # Gmail y Oura: solo lectura.
    gm = _api_conn("gmail", name="Gmail")
    from jarvis import secrets_store, connections
    secrets_store.set_secret(connections.secret_name(gm["id"]), json.dumps({"access_token": "tok", "expires_at": 9999999999}))
    fake.custom["gmail.googleapis.com"] = lambda req: httpx.Response(200, json={"messages": [{"id": "m1"}]} if req.url.path.endswith("/messages") else
                                                                    {"id": "m1", "snippet": "Hola, quiero una cotización", "internalDate": "1762000000000", "payload": {"headers": [{"name": "From", "value": "Ana <ana@x.co>"}, {"name": "Subject", "value": "Cotización"}]}})
    g = c.post("/api/dd/sync/gmail", json={"connection_id": gm["id"]}).json()
    assert g["nuevos"] == 1 and c.post("/api/dd/sync/gmail", json={"connection_id": gm["id"]}).json()["nuevos"] == 0
    assert records.list_records(per, "dd_mensaje")[0]["title"] == "Cotización"
    c.post("/api/dd/tools/mensajes", json={"module": "P03"})
    assert records.list_records(per, "dd_mensaje")[0]["data"]["clasificacion"] == "oportunidad"
    ou = _api_conn("oura", name="Oura")
    fake.custom["api.ouraring.com"] = lambda req: httpx.Response(200, json={"data": [{"day": "2026-11-09", "type": "long_sleep", "total_sleep_duration": 27000, "efficiency": 91}]})
    assert c.post("/api/dd/sync/oura", json={"connection_id": ou["id"]}).json()["nuevos"] == 1
    assert records.list_records(per, "dd_sueno")[0]["data"]["horas"] == 7.5


# ---------- Vision: Jarvis maneja Doomsday y los datos antiguos se fusionan

def test_jarvis_assistant_drives_doomsday_modules(dd):
    from jarvis import assistant
    c, interna, per = dd["client"], dd["spaces"]["interna"], dd["spaces"]["personal"]
    records.create(interna, "dd_pedido", "E1", {"ref": "E1", "fecha": date.today().isoformat(), "producto": "Faja", "precio": 100, "costo_producto": 30, "flete": 10}, status="entregado")
    # Desde el espacio personal: la herramienta corre en la capa del módulo (interna), no en la actual.
    r = c.post("/api/assistant", json={"space": per, "text": "G02 calcula"}).json()
    assert r["tool"] == "doomsday_herramienta" and "Utilidad neta: 60" in r["reply"] and r["mode"] == "comando"
    o = c.post("/api/assistant", json={"space": per, "text": "G04: ficha para la faja postural"}).json()
    job = jobs.get(o["job"]["id"])
    assert o["tool"] == "doomsday_orden" and job["type"] == "dd_run" and job["space_id"] == interna and job["params"]["inputs"]["orden"] == "ficha para la faja postural"
    m = c.post("/api/assistant", json={"space": per, "text": "módulos de pauta"}).json()
    assert m["tool"] == "doomsday_modulos" and "M01" in m["data"]["modulos"]
    assert c.post("/api/assistant", json={"space": per, "text": "brief"}).json()["data"]["modulo"] == "P07"
    assert "100 módulos de Doomsday" in c.post("/api/assistant", json={"space": per, "text": "ayuda"}).json()["reply"]
    # Los comandos de Jarvis de siempre siguen intactos.
    assert assistant.parse_command("anota comprar dominios")[0] == "capturar" and assistant.parse_command("busca leads de dentistas en Cali")[0] == "buscar_leads"
    assert assistant.parse_command("pausa los agentes")[0] == "pausar_agentes" and assistant.parse_command("A10")[0] == "doomsday_herramienta"
    assert {"doomsday_orden", "doomsday_herramienta", "doomsday_modulos", "buscar_oportunidades", "generar_contenido"} <= set(assistant.TOOLS)


def test_old_doomsday_home_is_merged_without_overwriting(dd, tmp_path, monkeypatch):
    import sqlite3
    from jarvis import config
    from doomsday import fusion
    mine = records.create(dd["spaces"]["interna"], "dd_pedido", "Mío", {"ref": "M1"})
    # Una carpeta antigua de Doomsday con su propia base: se construye con el mismo esquema.
    old = tmp_path / "doomsday_home"
    main_home = config.home()
    monkeypatch.setenv("JARVIS_HOME", str(old))
    db.migrate()
    db.execute("INSERT INTO spaces(id,name,kind,ai_policy,created_at,updated_at) VALUES('esp_viejo','Interna antigua','negocio','nube_permitida','2026-11-01','2026-11-01')")
    db.set_setting("dd_spaces", {"interna": "esp_viejo"})
    records.create("esp_viejo", "dd_pedido", "Antiguo", {"ref": "A1"})
    (old / "skills").mkdir()
    (old / "skills" / "G04.md").write_text("**Rol.** Mi skill antigua de fichas, con su método y su estándar.", encoding="utf-8")
    monkeypatch.setenv("JARVIS_HOME", str(main_home))
    out = fusion.import_old_home(old)
    assert "1 registros" in out[0] and "intacta" in out[0]
    assert records.list_records("esp_viejo", "dd_pedido")[0]["title"] == "Antiguo" and records.get(mine["id"])["title"] == "Mío"
    assert db.get_setting("dd_spaces") == dd["spaces"]  # las capas actuales no se pisan; la antigua queda como un espacio más
    from doomsday import skills
    assert skills.get("G04")["origen"] == "propia"
    assert fusion.import_old_home(old) == [] and (old / "data" / "jarvis.db").is_file()  # una sola vez; la carpeta antigua no se toca
