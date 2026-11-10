"""Importadores de archivos estándar: exportación de Apple Health (XML) y extractos bancarios OFX/QFX."""
from __future__ import annotations
import io
import re
import zipfile
from collections import defaultdict
from datetime import datetime, timedelta
from xml.etree import ElementTree

from . import records
from .security import SecurityError

MAX_XML = 1_500_000_000
ASLEEP = ("HKCategoryValueSleepAnalysisAsleep", "AsleepCore", "AsleepDeep", "AsleepREM", "AsleepUnspecified")
WORKOUT = {"Running": "cardio", "Walking": "cardio", "Cycling": "cardio", "Swimming": "cardio", "Hiking": "cardio", "TraditionalStrengthTraining": "fuerza",
           "FunctionalStrengthTraining": "fuerza", "Yoga": "movilidad", "Pilates": "movilidad", "Flexibility": "movilidad"}


def _dt(s: str) -> datetime:
    return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")


def apple_health(raw: bytes, space_id: str, *, days: int = 90, commit: bool = True) -> dict:
    """Lee export.xml (o el export.zip de la app Salud). Suma el sueño por noche, y registra entrenamientos y pasos diarios."""
    if raw[:2] == b"PK":
        with zipfile.ZipFile(io.BytesIO(raw)) as z:
            name = next((n for n in z.namelist() if n.endswith("export.xml") and ".." not in n), None)
            if not name or z.getinfo(name).file_size > MAX_XML:
                raise SecurityError("El ZIP no contiene export.xml o es demasiado grande.")
            stream = z.open(name)
    else:
        stream = io.BytesIO(raw)
    cutoff = datetime.now() - timedelta(days=days)
    sleep: dict[str, float] = defaultdict(float)
    steps: dict[str, float] = defaultdict(float)
    workouts = []
    try:
        for _, el in ElementTree.iterparse(stream, events=("end",)):
            if el.tag == "Record":
                t, start = el.get("type"), el.get("startDate") or ""
                if t in ("HKCategoryTypeIdentifierSleepAnalysis", "HKQuantityTypeIdentifierStepCount") and start and _dt(start) >= cutoff:
                    if t.endswith("SleepAnalysis"):
                        if any((el.get("value") or "").endswith(v) for v in ASLEEP):
                            end = _dt(el.get("endDate"))
                            sleep[end.date().isoformat()] += (end - _dt(start)).total_seconds() / 3600
                    else:
                        steps[start[:10]] += float(el.get("value") or 0)
                el.clear()
            elif el.tag == "Workout":
                start = el.get("startDate") or ""
                if start and _dt(start) >= cutoff:
                    kind = (el.get("workoutActivityType") or "").replace("HKWorkoutActivityType", "")
                    minutes = float(el.get("duration") or 0) * (60 if (el.get("durationUnit") or "min") == "h" else 1)
                    workouts.append((start[:10], kind, round(minutes)))
                el.clear()
    except ElementTree.ParseError:
        raise SecurityError("El archivo no es una exportación válida de Apple Health.")
    have = lambda kind, key: {(r["data"].get("date"), r["title"]) for r in records.list_records(space_id, kind, limit=50000)} | \
                              {(r["data"].get("date"), r["title"]) for r in records.list_records(space_id, kind, archived=True, limit=50000)}
    out = {"noches": 0, "entrenamientos": 0, "dias_de_pasos": 0, "duplicados": 0, "desde": cutoff.date().isoformat(), "aplicado": commit}
    plan = [("sleep", d, f"Noche del {d} (Apple Health)", {"date": d, "hours": round(h, 2), "notes": "Importado de Apple Health"}, "noches") for d, h in sorted(sleep.items()) if 0.5 <= h <= 20]
    plan += [("workout", d, f"{k or 'Entrenamiento'} {d} (Apple Health)", {"date": d, "type": WORKOUT.get(k, "otro"), "minutes": m, "notes": f"Importado de Apple Health: {k}"}, "entrenamientos") for d, k, m in workouts]
    plan += [("activity", d, f"Pasos {d} (Apple Health)", {"date": d, "type": "pasos", "notes": f"{int(n)} pasos"}, "dias_de_pasos") for d, n in sorted(steps.items())]
    seen: dict[str, set] = {}
    for kind, d, title, data, counter in plan:
        seen.setdefault(kind, have(kind, d))
        if (d, title) in seen[kind]:
            out["duplicados"] += 1
            continue
        seen[kind].add((d, title))
        if commit:
            records.create(space_id, kind, title, data)
        out[counter] += 1
    return out


_TAG = re.compile(r"<([A-Z0-9.]+)>([^<\r\n]*)")


def ofx(text: str, space_id: str, *, commit: bool = True, project_id: str | None = None) -> dict:
    """Extracto bancario OFX/QFX (formato estándar de exportación de bancos). Deduplica por el identificador único del banco (FITID)."""
    if "<OFX" not in text.upper() or "<STMTTRN" not in text.upper():
        raise SecurityError("El archivo no parece un extracto OFX/QFX con movimientos.")
    currency = (re.search(r"<CURDEF>([A-Z]{3})", text) or [None, ""])[1]
    existing = {r["data"].get("external_id") for r in records.list_records(space_id, "transaction", limit=100000)} | \
               {r["data"].get("external_id") for r in records.list_records(space_id, "transaction", archived=True, limit=100000)}
    out = {"nuevos": 0, "duplicados": 0, "errores": 0, "moneda": currency, "aplicado": commit, "detalle": []}
    for block in re.split(r"<STMTTRN>", text, flags=re.I)[1:]:
        f = {k.upper(): v.strip() for k, v in _TAG.findall(block.split("</STMTTRN>")[0])}
        try:
            amount = float(f["TRNAMT"].replace(",", "."))
            day = f"{f['DTPOSTED'][:4]}-{f['DTPOSTED'][4:6]}-{f['DTPOSTED'][6:8]}"
            fitid = f"ofx:{f.get('FITID') or day + f['TRNAMT'] + f.get('NAME', '')}"
        except (KeyError, ValueError):
            out["errores"] += 1
            continue
        title = (f.get("NAME") or f.get("MEMO") or "Movimiento bancario")[:200]
        item = {"fecha": day, "concepto": title, "importe": amount, "estado": "duplicado" if fitid in existing else "nuevo"}
        out["detalle"].append(item)
        if fitid in existing:
            out["duplicados"] += 1
            continue
        existing.add(fitid)
        if commit:
            records.create(space_id, "transaction", title, {"type": "ingreso" if amount > 0 else "gasto", "stage": "cobrado" if amount > 0 else "pagado", "amount": abs(amount),
                                                             "currency": currency, "date": day, "external_id": fitid, "notes": f.get("MEMO") or "", "counterparty": f.get("NAME") or ""}, project_id=project_id)
        out["nuevos"] += 1
    out["detalle"] = out["detalle"][:200]
    return out
