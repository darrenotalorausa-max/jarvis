"""Entorno aislado por prueba. Los proveedores simulados existen SOLO aquí (httpx.MockTransport): nunca en operación real."""
import json
import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("JARVIS_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("JARVIS_SECRETS_BACKEND", "file")
    monkeypatch.setenv("JARVIS_SECRETS_FILE", str(tmp_path / "secrets" / "secrets.json"))
    from jarvis import db, router, security, webfetch, worker
    from jarvis.providers import base
    db.migrate()
    worker.load_handlers()
    monkeypatch.setattr(router, "SLEEP", lambda s: None)
    monkeypatch.setattr(security, "resolve_host", lambda host: ["93.184.216.34"])
    router._semaphores.clear()
    webfetch._robots_cache.clear()
    base.TRANSPORT = httpx.MockTransport(lambda req: httpx.Response(599, text="sin simulador"))
    yield
    base.TRANSPORT = None


class Fake:
    """Simulador de proveedores y sitios web para pruebas. Registra cada petición."""

    def __init__(self):
        self.calls = []
        self.pages = {}          # url -> html | (status, body)
        self.search_results = []  # lista de dicts {title,url,content}
        self.llm = lambda system, user: "{}"
        self.status = {}         # host -> código forzado
        self.raise_timeout = set()

    def __call__(self, req: httpx.Request) -> httpx.Response:
        self.calls.append(req)
        host, path = req.url.host, req.url.path
        if host in self.raise_timeout:
            raise httpx.ReadTimeout("simulado", request=req)
        if host in self.status:
            return httpx.Response(self.status[host], json={"error": {"message": "simulado"}}, headers={"retry-after": "30"})
        if host == "api.tavily.com":
            return httpx.Response(200, json={"results": self.search_results})
        if host == "llm.test" and path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "modelo-prueba"}]})
        if host == "llm.test" and path.endswith("/chat/completions"):
            body = json.loads(req.content)
            text = self.llm(body["messages"][0]["content"], body["messages"][1]["content"])
            return httpx.Response(200, json={"choices": [{"message": {"content": text}}], "usage": {"prompt_tokens": 100, "completion_tokens": 50}, "model": "modelo-prueba"},
                                  headers={"x-ratelimit-remaining-requests": "99"})
        if path == "/robots.txt" and str(req.url) not in self.pages:
            return httpx.Response(404)
        url = str(req.url)
        if url in self.pages:
            page = self.pages[url]
            if isinstance(page, tuple):
                return httpx.Response(page[0], text=page[1], headers=page[2] if len(page) > 2 else {})
            return httpx.Response(200, text=page, headers={"content-type": "text/html; charset=utf-8"})
        return httpx.Response(404, text="no encontrada")

    def count(self, host):
        return sum(1 for c in self.calls if c.url.host == host and c.url.path != "/robots.txt")


@pytest.fixture
def fake():
    from jarvis.providers import base
    f = Fake()
    base.TRANSPORT = httpx.MockTransport(f)
    return f


@pytest.fixture
def space():
    from jarvis import db
    from jarvis.util import new_id, now_iso
    def make(name="Negocio", kind="negocio", policy="nube_permitida"):
        sid = new_id("esp")
        db.execute("INSERT INTO spaces(id,name,kind,ai_policy,created_at,updated_at) VALUES(?,?,?,?,?,?)", (sid, name, kind, policy, now_iso(), now_iso()))
        return sid
    return make


@pytest.fixture
def conn():
    from jarvis import connections
    def make(provider="openai_compat", **kw):
        data = {"provider": provider, "enabled": True, "terms_accepted": True, "secret": "sk-prueba-1234567890abcdef"}
        if provider == "openai_compat":
            data.update(base_url="https://llm.test/v1", model="modelo-prueba", capabilities=["texto", "extraccion"])
        data.update(kw)
        return connections.create(data)
    return make


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from jarvis.api import app
    return TestClient(app)


def run_all(max_jobs=20):
    from jarvis import worker
    done = []
    while len(done) < max_jobs:
        jid = worker.run_once()
        if not jid:
            break
        done.append(jid)
    return done
