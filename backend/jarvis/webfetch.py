"""Importador web seguro: valida destino (SSRF), sigue redirecciones validando cada salto, respeta robots.txt
y bloqueos, limita tamaño y trata el contenido como datos no confiables."""
from __future__ import annotations
import re
import urllib.robotparser
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import httpx

from . import security
from .providers import base

USER_AGENT = "JarvisOS/0.1 (local research assistant; respects robots.txt)"
MAX_BYTES = 1_500_000
MAX_REDIRECTS = 4
_robots_cache: dict[str, urllib.robotparser.RobotFileParser | None] = {}


class FetchResult(dict):
    pass


class _Extractor(HTMLParser):
    SKIP = {"script", "style", "noscript", "svg", "template", "iframe"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "tr", "section", "article", "header", "footer"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self.description = ""
        self.published = None
        self.links: list[tuple[str, str]] = []
        self._skip = 0
        self._in_title = False
        self._href = None
        self._link_text: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in self.SKIP:
            self._skip += 1
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            content = a.get("content") or ""
            if name in ("description", "og:description") and not self.description:
                self.description = content.strip()
            if name in ("article:published_time", "date", "og:published_time", "datepublished") and not self.published:
                self.published = content.strip()[:25]
        elif tag == "time" and a.get("datetime") and not self.published:
            self.published = a["datetime"][:25]
        elif tag == "a" and a.get("href"):
            self._href, self._link_text = a["href"], []
        if tag in self.BLOCK:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self._skip:
            self._skip -= 1
        elif tag == "title":
            self._in_title = False
        elif tag == "a" and self._href:
            self.links.append((self._href, " ".join(self._link_text).strip()))
            self._href = None

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._skip:
            self.parts.append(data)
            if self._href is not None:
                self._link_text.append(data.strip())


def html_to_text(html: str) -> dict:
    ex = _Extractor()
    try:
        ex.feed(html)
    except Exception:
        pass
    text = re.sub(r"[ \t\r\f\v]+", " ", "".join(ex.parts))
    text = re.sub(r"\n\s*\n+", "\n", text).strip()
    return {"title": ex.title.strip()[:300], "description": ex.description[:500], "published_at": ex.published, "text": text, "links": ex.links}


def _client() -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(15, connect=8), transport=base.TRANSPORT, follow_redirects=False,
                        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml,text/plain,application/pdf;q=0.8"})


def _peer_is_public(resp: httpx.Response) -> bool:
    stream = resp.extensions.get("network_stream")
    if not stream:
        return True  # transporte de pruebas
    try:
        addr = stream.get_extra_info("server_addr")
        return security._ip_is_public(addr[0]) if addr else True
    except Exception:
        return True


def _robots_allows(cli: httpx.Client, url: str) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    if origin not in _robots_cache:
        rp = urllib.robotparser.RobotFileParser()
        try:
            r = cli.get(origin + "/robots.txt")
            if r.status_code == 200 and _peer_is_public(r):
                rp.parse(r.text.splitlines())
                _robots_cache[origin] = rp
            else:
                _robots_cache[origin] = None
        except httpx.HTTPError:
            _robots_cache[origin] = None
    rp = _robots_cache[origin]
    return True if rp is None else rp.can_fetch("JarvisOS", url)


def fetch_page(url: str, *, respect_robots: bool = True) -> FetchResult:
    """Devuelve status: ok | no_disponible | bloqueada, con nota explicativa. Nunca lanza por errores de red."""
    try:
        current = security.check_public_url(url)
    except security.SecurityError as exc:
        return FetchResult(url=url, status="bloqueada", note=str(exc), text="", title="")
    with _client() as cli:
        try:
            for _ in range(MAX_REDIRECTS + 1):
                if respect_robots and not _robots_allows(cli, current):
                    return FetchResult(url=current, status="bloqueada", note="El sitio no permite el acceso automatizado (robots.txt).", text="", title="")
                with cli.stream("GET", current) as resp:
                    if not _peer_is_public(resp):
                        return FetchResult(url=current, status="bloqueada", note="La conexión terminó en una dirección privada; descartada.", text="", title="")
                    if resp.status_code in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                        nxt = urljoin(current, resp.headers["location"])
                        try:
                            current = security.check_public_url(nxt)
                        except security.SecurityError as exc:
                            return FetchResult(url=nxt, status="bloqueada", note=f"Redirección rechazada: {exc}", text="", title="")
                        continue
                    if resp.status_code in (401, 403, 429, 451):
                        return FetchResult(url=current, status="bloqueada", note=f"El sitio denegó el acceso ({resp.status_code}); no se intentó evadir.", text="", title="")
                    if resp.status_code >= 400:
                        return FetchResult(url=current, status="no_disponible", note=f"El sitio respondió {resp.status_code}.", text="", title="")
                    ctype = resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    raw = b""
                    for chunk in resp.iter_bytes():
                        raw += chunk
                        if len(raw) > MAX_BYTES:
                            break
                    truncated = len(raw) > MAX_BYTES
                    if ctype == "application/pdf" or current.lower().endswith(".pdf"):
                        text = pdf_to_text(raw)
                        return FetchResult(url=current, status="ok" if text else "no_disponible", title=current.rsplit("/", 1)[-1], text=text,
                                           note="PDF" + ("; truncado" if truncated else "") + ("" if text else "; no se pudo extraer texto"), published_at=None, links=[])
                    if ctype and not (ctype.startswith("text/") or "html" in ctype or "xml" in ctype):
                        return FetchResult(url=current, status="no_disponible", note=f"Tipo de contenido no soportado ({ctype}).", text="", title="")
                    html = raw.decode(resp.encoding or "utf-8", "replace")
                    info = html_to_text(html) if "html" in ctype or "<html" in html[:2000].lower() else {"title": "", "description": "", "published_at": None, "text": html, "links": []}
                    return FetchResult(url=current, status="ok", note="Contenido truncado por tamaño" if truncated else "", **info)
            return FetchResult(url=current, status="no_disponible", note="Demasiadas redirecciones.", text="", title="")
        except httpx.TimeoutException:
            return FetchResult(url=current, status="no_disponible", note="El sitio no respondió a tiempo.", text="", title="")
        except httpx.HTTPError as exc:
            return FetchResult(url=current, status="no_disponible", note=f"Error de red ({type(exc).__name__}).", text="", title="")


def pdf_to_text(raw: bytes, max_pages: int = 30) -> str:
    try:
        import io
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((page.extract_text() or "") for page in reader.pages[:max_pages]).strip()
    except Exception:
        return ""


def file_to_text(path, name: str) -> str:
    """Texto de un archivo importado por el usuario (txt, md, csv, json, html, pdf)."""
    ext = name.lower().rsplit(".", 1)[-1]
    raw = path.read_bytes()[: MAX_BYTES * 4]
    if ext == "pdf":
        return pdf_to_text(raw)
    text = raw.decode("utf-8", "replace")
    if ext in ("html", "htm"):
        return html_to_text(text)["text"]
    return text


def domain_of(url: str) -> str:
    host = (urlsplit(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host
