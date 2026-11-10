"""Adaptadores de búsqueda web: Brave Search API y Tavily."""
from __future__ import annotations

from . import base
from .base import ProviderError, SearchHit

FRESHNESS_TAVILY = {"pd": "day", "pw": "week", "pm": "month", "py": "year"}


def web_search(conn: dict, secret: str | None, query: str, *, count: int = 8, country: str | None = None,
               lang: str | None = None, freshness: str | None = None) -> list[SearchHit]:
    provider, url = conn["provider"], conn["base_url"]
    what = f"Búsqueda ({conn.get('name') or provider})"
    count = max(1, min(int(count), 20))
    with base.client(conn.get("timeout_s") or 30) as cli:
        if provider == "brave":
            params = {"q": query[:400], "count": count}
            if country:
                params["country"] = country.upper()
            if lang:
                params["search_lang"] = lang.lower()
            if freshness in ("pd", "pw", "pm", "py"):
                params["freshness"] = freshness
            data = base.json_body(base.send(cli, "GET", f"{url}/res/v1/web/search", what, params=params,
                                            headers={"X-Subscription-Token": secret or "", "Accept": "application/json"}), what)
            results = (data.get("web") or {}).get("results") or []
            return [SearchHit(r.get("title") or "", r["url"], r.get("description") or "", r.get("page_age") or r.get("age"))
                    for r in results if r.get("url")]
        if provider == "tavily":
            body = {"query": query[:400], "max_results": count, "search_depth": "basic"}
            if freshness in FRESHNESS_TAVILY:
                body["time_range"] = FRESHNESS_TAVILY[freshness]
            data = base.json_body(base.send(cli, "POST", f"{url}/search", what, json=body,
                                            headers={"Authorization": f"Bearer {secret or ''}"}), what)
            return [SearchHit(r.get("title") or "", r["url"], r.get("content") or "", r.get("published_date"))
                    for r in data.get("results") or [] if r.get("url")]
    raise ProviderError("not_supported", f"El proveedor {provider} no ofrece búsqueda web.")
