"""Doomsday: integraciones con plataformas externas (transporte simulado), recorte real con FFmpeg y espacios por cliente."""
import json
import subprocess
from datetime import date

import httpx
import pytest

from jarvis import connections, connectors, db, files, jobs, records, review
from conftest import run_all
from test_doomsday import _entrega, dd  # noqa: F401


def _api_conn(preset, base_url=None, name="App"):
    from doomsday import integrations
    integrations.register()
    p = connectors.PRESETS[preset]
    return connections.create({"provider": "api", "name": name, "base_url": base_url or p["base_url"], "enabled": True, "terms_accepted": True,
                               "secret": "token-de-prueba-1234567890", "options": {"auth": p["auth"], "actions": p["actions"]}})


def _approve_and_run(c, job_id):
    run_all()
    assert jobs.get(job_id)["status"] == "waiting_approval"
    assert c.post(f"/api/apps/pending/{job_id}/approve", json={}).status_code == 200
    run_all()
    return jobs.get(job_id)


def test_meta_and_tiktok_spend_sync_upserts_and_links_product(dd, fake):
    c, sid = dd["client"], dd["spaces"]["interna"]
    records.create(sid, "dd_producto", "Faja", {})
    hoy = date.today().isoformat()
    meta_rows = [{"campaign_id": "111111", "campaign_name": "CO_Faja_dolor", "ad_id": "999001", "ad_name": "faja_dolor_v01", "spend": "50.5", "impressions": "1000", "clicks": "40",
                  "actions": [{"action_type": "link_click", "value": "40"}, {"action_type": "purchase", "value": "5"}], "date_start": hoy}]
    fake.custom["graph.facebook.com"] = lambda req: httpx.Response(200, json={"data": meta_rows})
    cn = _api_conn("meta", name="Meta vieja")  # conexión creada con la plantilla antigua: la acción de gasto se añade sola
    r = c.post("/api/dd/sync/ads", json={"connection_id": cn["id"], "plataforma": "meta", "cuenta": "123456"}).json()
    assert r["filas"] == 1 and r["nuevos"] == 1 and r["actualizados"] == 0
    req = fake.calls[-1]
    assert req.method == "GET" and req.url.path.endswith("/act_123456/insights") and req.url.params["level"] == "ad" and req.headers["authorization"].startswith("Bearer ")
    g = records.list_records(sid, "dd_gasto_pauta")[0]["data"]
    assert g["gasto"] == 50.5 and g["compras"] == 5 and g["producto"] == "Faja" and g["ref_campana"] == "111111" and g["ref_anuncio"] == "999001"
    meta_rows[0]["spend"] = "80"
    r = c.post("/api/dd/sync/ads", json={"connection_id": cn["id"], "plataforma": "meta", "cuenta": "act_123456"}).json()
    assert r["nuevos"] == 0 and r["actualizados"] == 1 and records.list_records(sid, "dd_gasto_pauta")[0]["data"]["gasto"] == 80
    tk = _api_conn("tiktok_ads", name="TikTok")
    fake.custom["business-api.tiktok.com"] = lambda req: httpx.Response(200, json={"code": 0, "data": {"list": [
        {"dimensions": {"ad_id": "777", "stat_time_day": f"{hoy} 00:00:00"}, "metrics": {"campaign_id": "55", "campaign_name": "Otra", "ad_name": "a1", "spend": "10", "impressions": "5", "clicks": "1", "conversion": "2"}}]}})
    r = c.post("/api/dd/sync/ads", json={"connection_id": tk["id"], "plataforma": "tiktok", "cuenta": "7001"}).json()
    assert r["nuevos"] == 1 and "sin producto" in r["nota"] and fake.calls[-1].headers["access-token"] == "token-de-prueba-1234567890"
    assert len(records.list_records(sid, "dd_gasto_pauta")) == 2
    fake.custom["business-api.tiktok.com"] = lambda req: httpx.Response(200, json={"code": 40001, "message": "Access token is invalid"})
    assert "invalid" in c.post("/api/dd/sync/ads", json={"connection_id": tk["id"], "plataforma": "tiktok", "cuenta": "7001"}).json()["detail"]
    assert c.post("/api/dd/sync/ads", json={"connection_id": cn["id"], "plataforma": "x", "cuenta": "1"}).status_code == 400


def test_pause_and_whatsapp_need_exact_approval_before_touching_the_platform(dd, fake):
    c = dd["client"]
    cn = _api_conn("meta_ads")
    fake.custom["graph.facebook.com"] = lambda req: httpx.Response(200, json={"success": True})
    r = c.post("/api/dd/ads/pause", json={"connection_id": cn["id"], "plataforma": "meta", "objeto_id": "111111", "nombre": "CO_Faja"}).json()
    assert r["preview"]["method"] == "POST" and r["preview"]["url"].endswith("/111111") and r["preview"]["body"] == {"status": "PAUSED"}
    run_all()
    assert jobs.get(r["job"]["id"])["status"] == "waiting_approval" and not fake.calls  # nada sale sin aprobación
    job = _approve_and_run(c, r["job"]["id"])
    assert job["status"] == "completed" and fake.calls[-1].method == "POST" and json.loads(fake.calls[-1].content) == {"status": "PAUSED"}
    assert c.post("/api/dd/ads/pause", json={"connection_id": cn["id"], "plataforma": "meta", "objeto_id": "../me"}).status_code == 400
    wa = _api_conn("whatsapp", name="WhatsApp")
    msg = records.create(dd["spaces"]["clientes"], "dd_mensaje", "Ana", {"canal": "whatsapp", "texto": "¿Cuándo llega?"})
    n = len(fake.calls)
    r = c.post("/api/dd/whatsapp/send", json={"connection_id": wa["id"], "numero_id": "1055", "telefono": "+57 300 123 4567", "mensaje": "Hola Ana, llega mañana.", "record_id": msg["id"]}).json()
    assert r["preview"]["body"]["to"] == "573001234567" and r["job"]["space_id"] == dd["spaces"]["clientes"]
    job = _approve_and_run(c, r["job"]["id"])
    assert job["status"] == "completed" and len(fake.calls) == n + 1 and json.loads(fake.calls[-1].content)["text"]["body"] == "Hola Ana, llega mañana."
    assert records.get(msg["id"])["data"]["borrador"] == "Hola Ana, llega mañana."
    assert c.post("/api/dd/whatsapp/send", json={"connection_id": wa["id"], "numero_id": "1", "telefono": "12", "mensaje": "x"}).status_code == 400


def test_logistics_export_updates_orders_and_creates_settlements(dd):
    c, sid = dd["client"], dd["spaces"]["interna"]
    records.create(sid, "dd_pedido", "#1001", {"ref": "#1001", "producto": "Faja", "precio": 89900}, status="confirmado")
    csv_text = ("ID;ESTADO;CIUDAD DESTINO;TOTAL DE LA ORDEN;PRECIO FLETE;COSTO DEVOLUCION FLETE;PRECIO PROVEEDOR;TRANSPORTADORA;VALOR LIQUIDADO;NOTAS\n"
                "1001;ENTREGADO;Cali;$ 89.900;12.500;;30.000;Envia;47.400;ok\n"
                "1002;DEVOLUCION;Bogotá;89.900;12.500;9.000;30.000;Coordinadora;;\n"
                "1003;GUIA GENERADA;Medellín;59.900;11.000;;20.000;Envia;;\n"
                "1004;RARO;Pasto;10.000;;;;;;\n")
    pre = c.post("/api/dd/import/logistica", files={"file": ("dropi.csv", csv_text.encode("latin-1"), "text/csv")}).json()
    assert pre["guardado"] is False and pre["filas"] == 4 and pre["actualizados"] == 1 and pre["nuevos"] == 3 and pre["sin_estado"] == 1 and "NOTAS" in pre["ignoradas"]
    assert len(records.list_records(sid, "dd_pedido")) == 1
    res = c.post("/api/dd/import/logistica", files={"file": ("dropi.csv", csv_text.encode("latin-1"), "text/csv")}, data={"commit": "1"}).json()
    assert res["guardado"] and res["liquidaciones"] == 1
    by = {r["data"]["ref"].lstrip("#"): r for r in records.list_records(sid, "dd_pedido")}
    assert by["1001"]["status"] == "entregado" and by["1001"]["data"]["flete"] == 12500 and by["1001"]["data"]["costo_producto"] == 30000 and by["1001"]["data"]["producto"] == "Faja"
    assert by["1002"]["status"] == "devuelto" and by["1002"]["data"]["flete_devolucion"] == 9000 and by["1003"]["status"] == "en_transito" and by["1004"]["status"] == "pendiente"
    assert records.list_records(sid, "dd_liquidacion")[0]["data"]["valor_liquidado"] == 47400
    # Repetir la importación no duplica nada; la utilidad ya usa los costos reales.
    again = c.post("/api/dd/import/logistica", files={"file": ("dropi.csv", csv_text.encode("latin-1"), "text/csv")}, data={"commit": "1"}).json()
    assert again["nuevos"] == 0 and again["liquidaciones"] == 0 and len(records.list_records(sid, "dd_pedido")) == 4
    util = c.post("/api/dd/tools/utilidad_cod", json={"module": "G02"}).json()
    assert util["metricas"][0]["valor"] == 89900 - 30000 - 12500 - (12500 + 9000)
    assert c.post("/api/dd/import/logistica", files={"file": ("x.csv", b"a,b\n1,2\n", "text/csv")}).status_code == 400
    assert c.post("/api/dd/import/logistica", files={"file": ("x.xlsx", b"PK", "application/octet-stream")}).status_code == 400


def test_shopify_full_draft_only_from_approved_sheet(dd, fake, conn):
    c, sid = dd["client"], dd["spaces"]["interna"]
    conn()
    fake.llm = lambda s, u: _entrega(titulo="Faja postural", resumen="Página de la faja.", secciones=[
        {"titulo": "Beneficios", "contenido": "Acompaña tu postura.\n- **Cómoda** todo el día\n- Transpirable <b>"}, {"titulo": "Preguntas frecuentes", "contenido": "### ¿Qué tallas hay?\nS a XL."}])
    run = c.post("/api/dd/run", json={"module": "G04", "action": "ficha", "inputs": {"producto": "Faja postural"}}).json()
    run_all()
    did = jobs.get(run["job"]["id"])["result"]["deliverable_ids"][0]
    shop = _api_conn("shopify", "https://tienda1.myshopify.com/admin/api/2026-10", "Tienda")
    body = {"connection_id": shop["id"], "deliverable_id": did, "precio": "89900", "imagen": "https://cdn.test/faja.jpg"}
    assert "Aprueba primero" in c.post("/api/dd/publish/shopify", json=body).json()["detail"]
    d = review.detail(did, sid)
    review.set_status(did, sid, "en_revision")
    review.approve(did, sid, version=d["version"]["version"], user="yo")
    fake.custom["tienda1.myshopify.com"] = lambda req: httpx.Response(201, json={"product": {"id": 1}})
    r = c.post("/api/dd/publish/shopify", json=body).json()
    prod = r["preview"]["body"]["product"]
    assert prod["status"] == "draft" and prod["title"] == "Faja postural" and prod["variants"] == [{"price": "89900.00"}] and prod["images"] == [{"src": "https://cdn.test/faja.jpg"}]
    assert "<h2>Beneficios</h2>" in prod["body_html"] and "<li><strong>Cómoda</strong> todo el día</li>" in prod["body_html"] and "<h3>¿Qué tallas hay?</h3>" in prod["body_html"]
    assert "&lt;b&gt;" in prod["body_html"] and "Autoevaluación" not in prod["body_html"] and r["secciones"] == 2
    job = _approve_and_run(c, r["job"]["id"])
    assert job["status"] == "completed" and json.loads(fake.calls[-1].content)["product"]["status"] == "draft"
    assert c.post("/api/dd/publish/shopify", json={**body, "imagen": "http://inseguro/x.jpg"}).status_code == 400
    assert c.post("/api/dd/publish/shopify", json={**body, "precio": ""}).status_code == 400


def test_creative_media_requires_approved_creative(dd):
    c, sid = dd["client"], dd["spaces"]["interna"]
    rec = records.create(sid, "dd_creativo", "faja_dolor_v01", {"producto": "Faja", "hook": "¿Te duele la espalda al final del día?", "formato": "ugc", "guion": "Mujer en su casa muestra la faja."})
    assert "Aprueba primero" in c.post(f"/api/dd/creativos/{rec['id']}/generar", json={}).json()["detail"]
    records.update(rec["id"], sid, {"status": "aprobado"})
    r = c.post(f"/api/dd/creativos/{rec['id']}/generar", json={"seconds": 6}).json()
    assert r["created"] and r["job"]["type"] == "media_generate" and r["job"]["params"]["kind"] == "video" and r["job"]["params"]["aspect"] == "9:16" and "¿Te duele" in r["job"]["params"]["prompt"]
    run_all()
    assert jobs.get(r["job"]["id"])["status"] == "waiting_config"  # sin proveedor de video conectado no se inventa nada ni se gasta


def test_clip_is_really_cut_with_ffmpeg(dd, tmp_path):
    c, sid = dd["client"], dd["spaces"]["interna"]
    src = tmp_path / "largo.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=duration=6:size=640x360:rate=25", "-f", "lavfi", "-i", "sine=frequency=440:duration=6",
                    "-c:v", "libx264", "-preset", "ultrafast", "-c:a", "aac", "-shortest", str(src)], check=True)
    with open(src, "rb") as fh:
        f = files.save_stream(sid, "largo.mp4", fh)
    r = c.post("/api/dd/clip", json={"file_id": f["id"], "inicio": "0:01", "fin": "3.5", "vertical": True, "titulo": "Momento clave"}).json()
    run_all()
    job = jobs.get(r["job"]["id"])
    assert job["status"] == "completed", job
    out = files.get(job["result"]["file_ids"][0], sid)
    from jarvis.handlers import video
    info = video.probe(files.path_of(out))
    assert out["name"] == "Momento clave.mp4" and 2.3 <= float(info["duration"]) <= 2.7 and (info["width"], info["height"]) == (1080, 1920)
    assert review.detail(job["result"]["deliverable_ids"][0], sid)["ref_id"] == "C04"
    bad = c.post("/api/dd/clip", json={"file_id": f["id"], "inicio": "5", "fin": "2"}).json()
    run_all()
    assert jobs.get(bad["job"]["id"])["status"] == "failed"
    assert c.post("/api/dd/clip", json={"file_id": "nada", "inicio": 0, "fin": 1}).status_code == 400


def test_store_health_checks_shopify_product_and_cart(dd, fake):
    c = dd["client"]
    fake.pages["https://shop.test/products/faja"] = "<html><script src='https://cdn.shopify.com/x.js'></script><script>fbq('init')</script><form action='/cart/add'></form></html>"
    fake.pages["https://shop.test/products/faja.js"] = json.dumps({"available": False})
    fake.pages["https://shop.test/cart.js"] = "{}"
    r = c.post("/api/dd/tools/salud_tienda", json={"module": "G07", "inputs": {"enlace": "https://shop.test/products/faja"}}).json()
    assert any("Producto disponible" in a for a in r["alertas"]) and not any("carrito" in a.lower() for a in r["alertas"])
    fake.pages["https://shop.test/products/faja.js"] = json.dumps({"available": True})
    assert c.post("/api/dd/tools/salud_tienda", json={"module": "G07", "inputs": {"enlace": "https://shop.test/products/faja"}}).json()["metricas"][0]["valor"] == "sana"
    assert all(req.method == "GET" for req in fake.calls)


def test_client_spaces_keep_layers_apart(dd):
    c = dd["client"]
    acme = c.post("/api/dd/clients", json={"nombre": "Acme"}).json()
    assert c.post("/api/dd/clients", json={"nombre": "Acme"}).status_code == 400
    assert [x["name"] for x in c.get("/api/dd/clients").json()] == ["Clientes B2B", "Acme"]
    records.create(acme["id"], "dd_cliente", "Acme", {"mensualidad": 500, "resultado": "baja", "pagos_al_dia": False})
    assert c.post("/api/dd/tools/churn", json={"module": "V09", "space": acme["id"]}).json()["metricas"][0]["valor"] == 1
    assert "no hay datos" in c.post("/api/dd/tools/churn", json={"module": "V09"}).json()["resumen"].lower()  # el espacio general de clientes no ve los de Acme
    # Un módulo de otra capa no puede ejecutarse en el espacio de un cliente.
    assert c.post("/api/dd/tools/utilidad_cod", json={"module": "G02", "space": acme["id"]}).status_code == 400
    assert c.post("/api/dd/run", json={"module": "G02", "space": acme["id"], "inputs": {"orden": "x y z"}}).status_code == 400
    assert c.post("/api/dd/run", json={"module": "V03", "space": acme["id"], "inputs": {"orden": "Reporte de noviembre"}}).json()["job"]["space_id"] == acme["id"]
    from jarvis import access
    assert not access.allowed({"role": "cliente"}, "GET", "/api/dd/clients") and access.allowed({"role": "cliente"}, "GET", "/api/deliverables")
