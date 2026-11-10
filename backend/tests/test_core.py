import sqlite3
import time

import httpx
import pytest

from jarvis import config, connections, db, jobs, records, router, secrets_store, security, worker
from jarvis.jobs import Cancelled, JobError
from jarvis.providers import base
from jarvis.router import Ctx, RouterError
from conftest import run_all


# ---------- Persistencia y migraciones

def test_migrations_are_idempotent_and_data_persists(space):
    assert db.migrate() == []
    v = db.schema_version()
    assert v >= 1
    sid = space()
    rec = records.create(sid, "task", "Persistir", {"notes": "x"})
    raw = sqlite3.connect(config.db_path())  # conexión nueva = reinicio del proceso
    assert raw.execute("SELECT title FROM records WHERE id=?", (rec["id"],)).fetchone()[0] == "Persistir"
    assert db.migrate() == [] and db.schema_version() == v


def test_records_validation_and_space_isolation(space):
    a, b = space("A"), space("B")
    rec = records.create(a, "transaction", "Factura 1", {"type": "ingreso", "stage": "facturado", "amount": "1.200,5".replace(".", "")})
    assert rec["data"]["amount"] == 1200.5
    with pytest.raises(records.RecordError):
        records.create(a, "transaction", "Mala", {"type": "regalo", "stage": "cobrado", "amount": 1})
    with pytest.raises(records.RecordError):
        records.create(a, "transaction", "Sin importe", {"type": "ingreso", "stage": "cobrado"})
    assert records.get(rec["id"], b) is None
    assert records.list_records(b, "transaction") == []
    with pytest.raises(KeyError):
        records.update(rec["id"], b, {"title": "robo"})
    proj_b = records.create(b, "project", "Proyecto B")
    with pytest.raises(records.RecordError):  # no se puede enlazar con un proyecto de otro espacio
        records.create(a, "task", "Cruzada", project_id=proj_b["id"])


def test_personal_modules_crud_archive_export(space):
    sid = space("Personal", "personal", "solo_local")
    for kind in ("task", "capture", "focus_block", "habit", "activity", "journal", "reading", "reflection"):
        rec = records.create(sid, kind, f"Uno {kind}")
        rec = records.update(rec["id"], sid, {"title": f"Editado {kind}"})
        assert records.list_records(sid, kind)[0]["title"] == f"Editado {kind}"
        records.update(rec["id"], sid, {"archived": True})
        assert records.list_records(sid, kind) == [] and len(records.list_records(sid, kind, archived=True)) == 1
        assert f"Editado {kind}" in records.export_csv(sid, kind)


# ---------- Proveedores y conexiones

@pytest.mark.parametrize("code,status", [(401, "credencial_invalida"), (403, "sin_permiso"), (429, "cuota_agotada"), (404, "no_compatible"), (402, "cuota_agotada")])
def test_provider_errors_map_to_clear_states(fake, conn, code, status):
    c = conn()
    fake.status["llm.test"] = code
    res = connections.test(c["id"])
    assert res["ok"] is False and res["status"] == status
    assert connections.public(connections.get(c["id"]))["status_label"] == base.STATUS_LABELS[status]


def test_timeout_and_missing_credential(fake, conn):
    c = conn()
    fake.raise_timeout.add("llm.test")
    res = connections.test(c["id"])
    assert res["status"] == "error" and "tiempo" in res["detail"]
    c2 = conn(secret="")
    assert connections.public(connections.get(c2["id"]))["status"] == "no_configurada"
    assert connections.test(c2["id"])["status"] == "no_configurada"


def test_secrets_never_returned_nor_stored_in_db(fake, conn):
    c = conn(secret="sk-supersecreta-ABCDEFGH12345678")
    assert "secret" not in c and c["has_secret"] and c["secret_hint"].endswith("5678") and "supersecreta" not in str(c)
    assert "supersecreta" not in config.db_path().read_bytes().decode("latin-1")
    assert connections.test(c["id"])["ok"] is True
    assert fake.calls[-1].headers["authorization"] == "Bearer sk-supersecreta-ABCDEFGH12345678"
    assert "[REDACTADO]" in security.redact("Authorization: Bearer sk-supersecreta-ABCDEFGH12345678")
    assert "supersecreta" not in security.redact("fallo con api_key=sk-supersecreta-ABCDEFGH12345678 en url")


def test_cloud_provider_disabled_until_terms_accepted(fake, conn, space):
    sid = space()
    c = conn(terms_accepted=False)
    assert connections.public(connections.get(c["id"]))["status"] == "condiciones_pendientes"
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(sid), system="s", user="u")
    assert e.value.kind == "needs_config" and "Condiciones" in e.value.message and fake.count("llm.test") == 0


def test_provider_url_validation():
    with pytest.raises(ValueError):
        connections.create({"provider": "openai_compat", "base_url": "file:///etc/passwd"})
    with pytest.raises(ValueError):
        connections.create({"provider": "openai_compat", "base_url": "https://user:pass@host.test/v1"})


# ---------- Router: pago desactivado, caché, políticas, cuota, reintentos

def test_paid_spend_disabled_by_default(fake, conn, space):
    sid = space()
    conn(is_paid=True, monthly_budget_usd=5, price_in=1, price_out=2)
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(sid), system="s", user="u")
    assert "gasto está desactivado" in e.value.message and fake.count("llm.test") == 0
    db.set_setting("allow_paid", True)
    fake.llm = lambda s, u: "hola"
    text, meta = router.llm(Ctx(sid), system="s", user="u")
    assert text == "hola"
    row = db.one("SELECT * FROM usage WHERE state='ok'")
    assert row["est_cost_usd"] == pytest.approx((100 * 1 + 50 * 2) / 1_000_000) and "estimado" in row["cost_basis"]


def test_paid_budget_exhausted_blocks(fake, conn, space):
    sid = space()
    db.set_setting("allow_paid", True)
    c = conn(is_paid=True, monthly_budget_usd=0.0001, price_in=1000, price_out=1000)
    fake.llm = lambda s, u: "x"
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(sid), system="s", user="u")
    assert "presupuesto" in e.value.message and fake.count("llm.test") == 0


def test_local_first_ordering(fake, conn, space):
    sid = space()
    conn(name="Nube")
    conn(name="Local", base_url="http://127.0.0.1:9999/v1", secret="")
    usable, _, _ = router.candidates(sid, "texto")
    assert [c["name"] for c in usable] == ["Local", "Nube"]


def test_cache_by_content_and_space_with_ttl(fake, conn, space):
    a, b = space("A"), space("B")
    conn()
    fake.llm = lambda s, u: "respuesta"
    router.llm(Ctx(a), system="s", user="u", ttl_s=3600)
    _, meta = router.llm(Ctx(a), system="s", user="u", ttl_s=3600)
    assert meta["cached"] is True and fake.count("llm.test") == 1
    router.llm(Ctx(a), system="s", user="u", ttl_s=3600, prompt_version="v2")   # otra versión de instrucciones
    assert fake.count("llm.test") == 2
    _, meta_b = router.llm(Ctx(b), system="s", user="u", ttl_s=3600)            # otro espacio: no comparte caché
    assert meta_b["cached"] is False and fake.count("llm.test") == 3
    db.execute("UPDATE cache SET expires_at='2000-01-01T00:00:00+00:00'")       # caducada: no se reutiliza como actual
    _, meta = router.llm(Ctx(a), system="s", user="u", ttl_s=3600)
    assert meta["cached"] is False
    router.llm(Ctx(a), system="s", user="sin ttl")
    router.llm(Ctx(a), system="s", user="sin ttl")
    assert fake.count("llm.test") == 6  # sin TTL no hay caché


def test_space_policies(fake, conn, space):
    conn()
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(space("L", "negocio", "solo_local")), system="s", user="u")
    assert "solo permite proveedores locales" in e.value.message
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(space("P", "personal", "nube_permitida")), system="s", user="diario")
    assert "datos personales" in e.value.message
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(space("N", "negocio", "sin_ia")), system="s", user="u")
    assert e.value.kind == "policy" and fake.count("llm.test") == 0


def test_quota_pauses_and_does_not_loop(fake, conn, space):
    sid = space()
    c = conn()
    fake.status["llm.test"] = 429
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(sid), system="s", user="u")
    assert e.value.kind == "quota" and e.value.resume_at and fake.count("llm.test") == 1  # 429 no se reintenta en bucle
    assert connections.public(connections.get(c["id"]))["status"] == "cuota_agotada"
    with pytest.raises(RouterError):
        router.llm(Ctx(sid), system="s", user="u")
    assert fake.count("llm.test") == 1  # bloqueada hasta retry-after: ni siquiera se llama


def test_timeouts_retry_with_limit(fake, conn, space):
    sid = space()
    conn()
    fake.raise_timeout.add("llm.test")
    with pytest.raises(RouterError):
        router.llm(Ctx(sid), system="s", user="u")
    assert fake.count("llm.test") == 3  # 1 intento + 2 reintentos con backoff


def test_configured_rate_limit_and_job_limits(fake, conn, space):
    sid = space()
    conn(rpm_limit=1)
    fake.llm = lambda s, u: "x"
    router.llm(Ctx(sid), system="s", user="1")
    with pytest.raises(RouterError) as e:
        router.llm(Ctx(sid), system="s", user="2")
    assert e.value.kind == "quota" and "límite por minuto" in e.value.message
    ctx = Ctx(sid, limits={"max_calls": 0, "max_tokens": 10, "max_cost_usd": 1})
    with pytest.raises(RouterError) as e:
        router.llm(ctx, system="s", user="3")
    assert e.value.kind == "limit"


# ---------- Cola de trabajos

def _handler(name, fn):
    worker.HANDLERS[name] = fn


def test_idempotent_enqueue_and_completion(space):
    sid = space()
    _handler("t_ok", lambda ctx: {"mensaje": "listo", "x": 1})
    j1, created1 = jobs.enqueue(sid, "t_ok", "A", {"p": 1})
    j2, created2 = jobs.enqueue(sid, "t_ok", "A", {"p": 1})
    assert created1 and not created2 and j1["id"] == j2["id"]
    run_all()
    done = jobs.get(j1["id"])
    assert done["status"] == "completed" and done["result"]["x"] == 1 and done["progress"] == 1
    _, created3 = jobs.enqueue(sid, "t_ok", "A", {"p": 1})  # el anterior ya terminó: se permite uno nuevo
    assert created3


def test_cancel_pending_and_running(space):
    sid = space()
    seen = []

    def slow(ctx):
        seen.append("inicio")
        jobs.request_cancel(ctx.id)            # el usuario cancela mientras se ejecuta
        ctx._cancel.set()                      # (el hilo de latido lo detectaría en ≤5 s)
        ctx.stage("paso", 0.5, "no debería continuar")
        seen.append("no")

    _handler("t_slow", slow)
    j, _ = jobs.enqueue(sid, "t_slow", "S", {})
    assert jobs.request_cancel(j["id"])["status"] == "cancelled"   # pendiente: cancelación inmediata
    j2, _ = jobs.enqueue(sid, "t_slow", "S", {"n": 2})
    run_all()
    assert jobs.get(j2["id"])["status"] == "cancelled" and seen == ["inicio"]


def test_heartbeat_detects_cancel_request(space):
    sid = space()
    j, _ = jobs.enqueue(sid, "x", "X", {})
    jobs.claim("w1")
    jobs.request_cancel(j["id"])
    assert jobs.heartbeat(j["id"]) is True


def test_recovery_after_crash_and_limited_retries(space):
    sid = space()
    _handler("t_ok", lambda ctx: {"mensaje": "ok"})
    j, _ = jobs.enqueue(sid, "t_ok", "R", {})
    jobs.claim("muerto")                                  # un worker lo toma y "muere"
    db.execute("UPDATE jobs SET heartbeat_at='2000-01-01T00:00:00+00:00'")
    assert jobs.recover_stale() == [j["id"]] and jobs.get(j["id"])["status"] == "pending"
    jobs.claim("muerto2")
    db.execute("UPDATE jobs SET heartbeat_at='2000-01-01T00:00:00+00:00'")
    jobs.recover_stale()
    assert jobs.get(j["id"])["status"] == "failed"         # agotó max_attempts: no reintenta sin fin
    calls = []

    def boom(ctx):
        calls.append(1)
        raise RuntimeError("inesperado")

    _handler("t_boom", boom)
    b, _ = jobs.enqueue(sid, "t_boom", "B", {})
    run_all()
    db.execute("UPDATE jobs SET resume_at=NULL WHERE id=?", (b["id"],))
    run_all()
    assert jobs.get(b["id"])["status"] == "failed" and len(calls) == 2


def test_waiting_states_and_wake_on_config(fake, conn, space):
    sid = space()
    _handler("t_llm", lambda ctx: {"mensaje": router.llm(ctx.router, system="s", user="u")[0]})
    j, _ = jobs.enqueue(sid, "t_llm", "L", {})
    run_all()
    got = jobs.get(j["id"])
    assert got["status"] == "waiting_config" and "Conexiones" in got["message"]
    fake.llm = lambda s, u: "ya"
    conn()                                   # crear no despierta; probar/editar sí
    connections.test(connections.list_all()[0]["id"])
    assert jobs.get(j["id"])["status"] == "pending"
    run_all()
    assert jobs.get(j["id"])["status"] == "completed"
    fake.status["llm.test"] = 429
    q, _ = jobs.enqueue(sid, "t_llm", "Q", {"n": 2})
    run_all()
    got = jobs.get(q["id"])
    assert got["status"] == "waiting_quota" and got["resume_at"]
    assert worker.run_once() is None          # no entra en bucle: espera a resume_at


def test_unknown_type_and_non_retryable_error(space):
    sid = space()
    j, _ = jobs.enqueue(sid, "no_existe", "N", {})
    run_all()
    assert jobs.get(j["id"])["status"] == "failed"
    _handler("t_err", lambda ctx: (_ for _ in ()).throw(JobError("dato inválido")))
    e, _ = jobs.enqueue(sid, "t_err", "E", {})
    run_all()
    got = jobs.get(e["id"])
    assert got["status"] == "failed" and got["error"] == "dato inválido" and got["attempts"] == 1


def test_run_proc_no_shell_and_cancel(space):
    sid = space()
    j, _ = jobs.enqueue(sid, "x", "X", {})
    ctx = worker.JobCtx(jobs.claim("w"))
    code, _ = ctx.run_proc(["python3", "-c", "import sys; sys.exit(3)"])
    assert code == 3
    ctx._cancel.set()
    t0 = time.monotonic()
    with pytest.raises(Cancelled):
        ctx.run_proc(["python3", "-c", "import time; time.sleep(30)"])
    assert time.monotonic() - t0 < 10
