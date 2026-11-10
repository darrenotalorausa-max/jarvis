"""Tipos comunes de proveedores y traducción de errores HTTP a estados comprensibles."""
from __future__ import annotations
from dataclasses import dataclass, field

import httpx

from ..security import redact

# Las pruebas sustituyen este transporte por httpx.MockTransport. En operación real es None.
TRANSPORT: httpx.BaseTransport | None = None

KIND_STATUS = {
    "auth": "credencial_invalida",
    "permission": "sin_permiso",
    "quota": "cuota_agotada",
    "not_supported": "no_compatible",
    "timeout": "error",
    "network": "error",
    "bad_response": "error",
    "config": "no_configurada",
}

STATUS_LABELS = {
    "operativa": "Operativa",
    "sin_probar": "Sin probar",
    "no_configurada": "No configurada",
    "credencial_invalida": "Credencial inválida",
    "sin_permiso": "Sin permiso",
    "cuota_agotada": "Cuota agotada",
    "no_compatible": "No compatible",
    "condiciones_pendientes": "Condiciones sin aceptar",
    "deshabilitada": "Deshabilitada",
    "error": "Error",
}


class ProviderError(Exception):
    def __init__(self, kind: str, message: str, retry_after: float | None = None, http_status: int | None = None):
        super().__init__(message)
        self.kind = kind
        self.message = redact(message)
        self.retry_after = retry_after
        self.http_status = http_status

    @property
    def status(self) -> str:
        return KIND_STATUS.get(self.kind, "error")


@dataclass
class LLMResult:
    text: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    quota: dict = field(default_factory=dict)


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str = ""
    published_at: str | None = None


def client(timeout: float) -> httpx.Client:
    return httpx.Client(timeout=httpx.Timeout(timeout, connect=min(timeout, 10)), transport=TRANSPORT,
                        follow_redirects=False, headers={"User-Agent": "JarvisOS/0.1"})


def _retry_after(resp: httpx.Response) -> float | None:
    raw = resp.headers.get("retry-after")
    try:
        return float(raw) if raw else None
    except ValueError:
        return None


def _detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
        err = body.get("error", body) if isinstance(body, dict) else body
        if isinstance(err, dict):
            msg = err.get("message") or err.get("detail") or err.get("status") or str(err)
        else:
            msg = str(err)
    except ValueError:
        msg = resp.text
    return redact(str(msg))[:300]


def raise_for_status(resp: httpx.Response, what: str) -> None:
    code = resp.status_code
    if code < 400:
        return
    detail = _detail(resp)
    if code == 401:
        raise ProviderError("auth", f"{what}: el proveedor rechazó la credencial (401). {detail}", http_status=code)
    if code == 403:
        raise ProviderError("permission", f"{what}: la credencial no tiene permiso para esta operación o modelo (403). {detail}", http_status=code)
    if code == 402:
        raise ProviderError("quota", f"{what}: el proveedor exige saldo o plan de pago (402). {detail}", http_status=code)
    if code == 429:
        raise ProviderError("quota", f"{what}: límite de uso o cuota alcanzado (429). {detail}", retry_after=_retry_after(resp), http_status=code)
    if code in (404, 405, 501):
        raise ProviderError("not_supported", f"{what}: el modelo o endpoint no existe en este proveedor ({code}). {detail}", http_status=code)
    if code in (400, 422):
        low = detail.lower()
        if "api key" in low or "api_key" in low:
            raise ProviderError("auth", f"{what}: credencial inválida. {detail}", http_status=code)
        raise ProviderError("bad_response", f"{what}: el proveedor rechazó la solicitud ({code}). {detail}", http_status=code)
    raise ProviderError("network", f"{what}: error del proveedor ({code}). {detail}", retry_after=_retry_after(resp), http_status=code)


def send(cli: httpx.Client, method: str, url: str, what: str, **kw) -> httpx.Response:
    try:
        resp = cli.request(method, url, **kw)
    except httpx.TimeoutException:
        raise ProviderError("timeout", f"{what}: el proveedor no respondió dentro del tiempo límite.")
    except httpx.HTTPError as exc:
        raise ProviderError("network", f"{what}: no se pudo conectar ({type(exc).__name__}). Revisa la URL y que el servicio esté activo.")
    raise_for_status(resp, what)
    return resp


def json_body(resp: httpx.Response, what: str) -> dict:
    try:
        data = resp.json()
    except ValueError:
        raise ProviderError("bad_response", f"{what}: respuesta no válida (no es JSON).")
    if not isinstance(data, dict):
        raise ProviderError("bad_response", f"{what}: respuesta con formato inesperado.")
    return data


def quota_from_headers(resp: httpx.Response) -> dict:
    out = {}
    for k, v in resp.headers.items():
        lk = k.lower()
        if lk.startswith("x-ratelimit-") or lk.startswith("x-rate-limit-"):
            out[lk] = v
    return out
