import io
import json
import zipfile

import pytest

from jarvis import backup, config, connections, db, files, jobs, records, review, security, webfetch
from conftest import run_all


# ---------- SSRF, rutas y archivos

@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.10", "169.254.169.254", "::1", "172.16.0.1", "0.0.0.0", "100.64.0.1"])
def test_ssrf_blocks_private_and_metadata(monkeypatch, fake, ip):
    monkeypatch.setattr(security, "resolve_host", lambda host: [ip])
    res = webfetch.fetch_page("http://interno.ejemplo.test/admin")
    assert res["status"] == "bloqueada" and fake.calls == []


def test_ssrf_blocks_schemes_literals_and_redirects(monkeypatch, fake):
    for url in ("file:///etc/passwd", "ftp://x.test/a", "http://localhost:8765/api/connections", "http://metadata.google.internal/x", "http://user:pw@sitio.test/"):
        assert webfetch.fetch_page(url)["status"] == "bloqueada"
    assert fake.calls == []
    monkeypatch.setattr(security, "resolve_host", lambda host: ["10.0.0.1"] if host == "interno.test" else ["93.184.216.34"])
    fake.pages["https://publico.test/"] = (302, "", {"location": "http://interno.test/secreto"})
    res = webfetch.fetch_page("https://publico.test/")
    assert res["status"] == "bloqueada" and "Redirección rechazada" in res["note"]
    assert all(c.url.host != "interno.test" for c in fake.calls)


def test_fetch_respects_blocks_and_robots(fake):
    fake.pages["https://sitio.test/privado"] = (403, "no")
    res = webfetch.fetch_page("https://sitio.test/privado")
    assert res["status"] == "bloqueada" and "no se intentó evadir" in res["note"]
    fake.pages["https://cerrado.test/robots.txt"] = (200, "User-agent: *\nDisallow: /", {"content-type": "text/plain"})
    fake.pages["https://cerrado.test/pagina"] = "<html><body>hola</body></html>"
    res = webfetch.fetch_page("https://cerrado.test/pagina")
    assert res["status"] == "bloqueada" and "robots.txt" in res["note"]
    assert all(c.url.path != "/pagina" for c in fake.calls)


def test_html_extraction_ignores_scripts():
    info = webfetch.html_to_text("<html><head><title>T</title><script>alert('x')</script><meta property='article:published_time' content='2026-01-02T00:00:00Z'></head>"
                                 "<body><p>Hola <b>mundo</b></p><style>.a{}</style><a href='mailto:ventas@x.test'>Escríbenos</a></body></html>")
    assert info["title"] == "T" and "alert" not in info["text"] and "Hola mundo" in info["text"]
    assert info["published_at"].startswith("2026-01-02") and ("mailto:ventas@x.test", "Escríbenos") in info["links"]


def test_path_traversal_and_file_types(space, client):
    with pytest.raises(security.SecurityError):
        security.safe_join(config.files_dir(), "../../etc/passwd")
    assert security.sanitize_filename("../../../etc/passwd") == "passwd"
    assert security.sanitize_filename("C:\\Windows\\evil.exe") == "evil.exe"
    sid = space()
    r = client.post("/api/files", data={"space": sid}, files={"file": ("malware.exe", b"MZ", "application/octet-stream")})
    assert r.status_code == 400 and "no permitido" in r.json()["detail"]
    r = client.post("/api/files", data={"space": sid}, files={"file": ("../../nota.txt", b"hola", "text/plain")})
    assert r.status_code == 200 and r.json()["name"] == "nota.txt" and ".." not in r.json()["rel_path"]
    other = space("Otro")
    assert client.get(f"/api/files/{r.json()['id']}/download", params={"space": other}).status_code == 404
    assert client.get("/api/exports/file", params={"path": "../data/jarvis.db"}).status_code == 400


def test_upload_size_limit(space):
    with pytest.raises(security.SecurityError):
        files.save_stream(space(), "grande.txt", io.BytesIO(b"x" * 2000), max_bytes=1000)
    assert list(config.files_dir().rglob("*.txt")) == []


def test_host_and_origin_guard(client, space):
    assert client.get("/api/health", headers={"host": "evil.example"}).status_code == 403
    r = client.post("/api/spaces", json={"name": "X", "kind": "negocio"}, headers={"origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.post("/api/spaces", json={"name": "X", "kind": "negocio"}, headers={"origin": "http://127.0.0.1:8765"}).status_code == 200


# ---------- Revisión y aprobaciones ligadas a versión

def _doc(space_id, body="Texto inicial"):
    return review.create(space_id, "documento", "Doc", {"sections": [{"key": "contenido", "title": "Contenido", "type": "text", "body": body}]})


def test_approval_bound_to_version_destination_and_expiry(space):
    sid = space()
    d = _doc(sid)
    review.approve(d["id"], sid, version=1, user="ana", action="envio_externo", destination="https://crm.test/hook", scope="lead X")
    assert review.find_valid_approval(d["id"], "envio_externo", "https://crm.test/hook")
    assert review.find_valid_approval(d["id"], "envio_externo", "https://otro.test/hook") is None      # otro destino
    assert review.find_valid_approval(d["id"], "version", "") is None                                  # otra acción
    review.add_version(d["id"], sid, {"sections": [{"key": "contenido", "title": "Contenido", "type": "text", "body": "Texto cambiado"}]})
    assert review.find_valid_approval(d["id"], "envio_externo", "https://crm.test/hook") is None       # cambió la pieza
    assert review.get(d["id"])["status"] == "borrador" and review.get(d["id"])["current_version"] == 2
    with pytest.raises(review.ReviewError):
        review.approve(d["id"], sid, version=1, user="ana")                                            # versión antigua
    a = review.approve(d["id"], sid, version=2, user="ana", action="envio_externo", destination="https://crm.test/hook", expires_hours=1)
    db.execute("UPDATE approvals SET expires_at='2000-01-01T00:00:00+00:00' WHERE id=?", (a["id"],))
    assert review.find_valid_approval(d["id"], "envio_externo", "https://crm.test/hook") is None       # caducada
    with pytest.raises(review.ReviewError):
        review.approve(d["id"], sid, version=2, user="ana", action="envio_externo")                    # sin destino


def test_identical_edit_does_not_create_version_and_diff(space):
    sid = space()
    d = _doc(sid)
    same = review.get_version(d["id"])["content"]
    assert review.add_version(d["id"], sid, same)["current_version"] == 1
    review.add_version(d["id"], sid, {"sections": [{"key": "contenido", "title": "Contenido", "type": "text", "body": "Otro texto"}]})
    diff = review.diff(d["id"], sid, 1, 2)
    assert any(l.startswith("-Texto inicial") for l in diff["diff"]) and any(l.startswith("+Otro texto") for l in diff["diff"])


def test_checks_flag_unsourced_facts_and_placeholders(space):
    sid = space()
    content = {"sections": [
        {"key": "comprador", "title": "c", "type": "text", "body": "x"},
        {"key": "hechos", "title": "h", "type": "facts", "items": [
            {"claim": "El 80% compra online", "kind": "hecho", "source_ids": [], "evidence": ""},
            {"claim": "Con fuente falsa", "kind": "hecho", "source_ids": ["src_inexistente"], "evidence": "cita"}]},
        {"key": "oportunidad", "title": "o", "type": "text", "body": "[pendiente] ver http://localhost"},
        {"key": "riesgos", "title": "r", "type": "list", "items": []},
        {"key": "validacion", "title": "v", "type": "table", "columns": ["a"], "rows": []}]}
    d = review.create(sid, "dossier", "Exp", content)
    checks = {c["id"]: c for c in review.get_version(d["id"])["checks"]["automaticas"]}
    assert checks["campos"]["result"] == "fail" and "riesgos" in checks["campos"]["detail"]
    assert checks["fuentes"]["result"] == "fail" and "src_inexistente" in checks["fuentes"]["detail"]
    assert checks["pendientes"]["result"] == "warn" and checks["enlaces"]["result"] == "fail" and checks["cifras"]["result"] == "warn"
    assert "No certifican la veracidad" in review.get_version(d["id"])["checks"]["nota"]


def test_external_send_requires_specific_approval(fake, space, client):
    sid = space()
    d = _doc(sid)
    hook = connections.create({"provider": "webhook", "base_url": "https://crm.test/hook", "enabled": True, "terms_accepted": True})
    fake.pages["https://crm.test/hook"] = (200, "ok")
    job = client.post(f"/api/deliverables/{d['id']}/send", json={"space": sid, "connection_id": hook["id"]}).json()["job"]
    run_all()
    assert jobs.get(job["id"])["status"] == "waiting_approval" and fake.count("crm.test") == 0     # sin aprobación no sale nada
    review.approve(d["id"], sid, version=1, user="ana", action="version")                          # aprobar la versión no autoriza el envío
    jobs.retry(job["id"]); run_all()
    assert jobs.get(job["id"])["status"] == "waiting_approval" and fake.count("crm.test") == 0
    client.post(f"/api/deliverables/{d['id']}/approve", json={"space": sid, "version": 1, "action": "envio_externo", "destination": "https://crm.test/hook"})
    run_all()
    assert jobs.get(job["id"])["status"] == "completed" and fake.count("crm.test") == 1
    sent = json.loads(fake.calls[-1].content)
    assert sent["entregable"]["version"] == 1 and sent["aprobacion"]["usuario"]
    job2 = client.post(f"/api/deliverables/{d['id']}/send", json={"space": sid, "connection_id": hook["id"]}).json()["job"]
    run_all()
    assert jobs.get(job2["id"])["status"] == "waiting_approval" and fake.count("crm.test") == 1    # la aprobación es de un solo uso


def test_export_writes_into_exports_only(space):
    sid = space()
    d = _doc(sid)
    out = review.export(d["id"], sid, "md")
    path = config.exports_dir() / out["archivos"][0]
    assert path.is_file() and "Texto inicial" in path.read_text(encoding="utf-8")
    assert review.export(d["id"], sid, "json")["archivos"]
    with pytest.raises(review.ReviewError):
        review.export(d["id"], sid, "exe")


# ---------- Respaldo y restauración

def test_backup_restore_roundtrip_without_secrets(space, conn):
    sid = space()
    conn(secret="sk-NO-DEBE-SALIR-0123456789")
    rec = records.create(sid, "task", "Antes del respaldo")
    f = files.save_bytes(sid, "nota.txt", b"contenido original", origin="upload")
    info = backup.create()
    zpath = backup.backups_dir() / info["archivo"]
    with zipfile.ZipFile(zpath) as z:
        blob = b"".join(z.read(n) for n in z.namelist())
    assert b"NO-DEBE-SALIR" not in blob and info["manifiesto"]["incluye_secretos"] is False
    records.update(rec["id"], sid, {"title": "Cambiado después"})
    records.create(sid, "task", "Creada después")
    files.path_of(f).write_bytes(b"alterado")
    with pytest.raises(security.SecurityError):
        backup.restore(zpath, confirm=False)                      # exige confirmación
    assert records.get(rec["id"])["title"] == "Cambiado después"
    res = backup.restore(zpath, confirm=True)
    assert records.get(rec["id"])["title"] == "Antes del respaldo" and len(records.list_records(sid, "task")) == 1
    assert files.path_of(files.get(f["id"])).read_bytes() == b"contenido original"
    safety = backup.backups_dir() / res["copia_de_seguridad_previa"]
    assert safety.is_file() and "antes-de-restaurar" in safety.name   # el estado previo no se pierde


def test_backup_rejects_tampered_or_unsafe(space, tmp_path):
    space()
    info = backup.create()
    src = backup.backups_dir() / info["archivo"]
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(bad, "w") as zout:
        for n in zin.namelist():
            zout.writestr(n, zin.read(n) + (b"x" if n == "db/jarvis.db" else b""))
    with pytest.raises(security.SecurityError, match="huella"):
        backup.inspect(bad)
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as z:
        z.writestr("../../fuera.txt", "x")
        z.writestr("manifest.json", "{}")
    with pytest.raises(security.SecurityError, match="rutas"):
        backup.inspect(evil)
    notzip = tmp_path / "no.zip"
    notzip.write_text("hola")
    with pytest.raises(security.SecurityError):
        backup.inspect(notzip)
