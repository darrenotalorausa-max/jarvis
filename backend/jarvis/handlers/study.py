"""Tutor: convierte un PDF o texto en una ruta de estudio con módulos, ejercicios, cuestionario y tarjetas de repaso."""
from __future__ import annotations
from datetime import date

from pydantic import BaseModel, Field

from .. import files, records, review, router, webfetch
from ..jobs import JobError
from ..worker import handler
from .common import ask_json, available, norm

CHUNK, MAX_CHUNKS = 9000, 4


class Module(BaseModel):
    title: str
    objectives: list[str] = Field(default_factory=list)
    key_ideas: list[str] = Field(default_factory=list)
    exercise: str = ""


class Card(BaseModel):
    front: str
    back: str


class Quiz(BaseModel):
    question: str
    answer: str


class Plan(BaseModel):
    modules: list[Module] = Field(default_factory=list)
    flashcards: list[Card] = Field(default_factory=list)
    quiz: list[Quiz] = Field(default_factory=list)


@handler("study_plan")
def study_plan(ctx) -> dict:
    p = ctx.params
    f = files.get(p.get("file_id") or "", ctx.space_id)
    if not f:
        raise JobError("El archivo no existe en este espacio.")
    text = webfetch.file_to_text(files.path_of(f), f["name"]).strip()
    if len(text) < 400:
        raise JobError("No se pudo extraer texto suficiente del archivo (¿es un PDF escaneado sin texto?).")
    if not available(ctx, "extraccion"):
        raise router.RouterError("needs_config", "El tutor necesita un modelo de texto permitido para este espacio. En un espacio personal, un modelo local (Ollama) "
                                 "o una conexión autorizada para datos personales.")
    chunks = [text[i:i + CHUNK] for i in range(0, len(text), CHUNK)][:MAX_CHUNKS]
    covered = min(len(text), CHUNK * MAX_CHUNKS)
    system = ("Eres un tutor. A partir exclusivamente del material entre <fuente>, prepara en español una ruta de estudio: módulos con objetivos, ideas clave y un ejercicio práctico; "
              "tarjetas de repaso (pregunta concreta, respuesta breve) y preguntas de autoevaluación con su respuesta. No añadas datos que no estén en el material.")
    modules, cards, quiz = [], [], []
    for i, ch in enumerate(chunks):
        ctx.stage("lectura", 0.1 + 0.8 * i / len(chunks), f"Estudiando la parte {i + 1} de {len(chunks)}")
        plan, meta = ask_json(ctx, Plan, system=system, user=f"Parte {i + 1} de {len(chunks)} de «{f['name']}».\n<fuente>\n{ch.replace('</fuente>', '')}\n</fuente>",
                              max_tokens=3000, ttl_s=30 * 24 * 3600, prompt_version="tutor-v1")
        modules += plan.modules[:4]
        cards += plan.flashcards[:10]
        quiz += plan.quiz[:6]
    deck = (p.get("deck") or f["name"].rsplit(".", 1)[0])[:60]
    existing = {norm(c["title"]) for c in records.list_records(ctx.space_id, "flashcard", limit=20000)}
    created = 0
    for c in cards:
        if c.front.strip() and c.back.strip() and norm(c.front) not in existing:
            existing.add(norm(c.front))
            records.create(ctx.space_id, "flashcard", c.front[:280], {"deck": deck, "back": c.back, "due": date.today().isoformat()})
            created += 1
    sections = [{"key": f"modulo_{i:02d}", "title": f"Módulo {i}: {m.title}", "type": "text",
                 "body": "**Objetivos**\n" + "\n".join(f"- {o}" for o in m.objectives) + "\n\n**Ideas clave**\n" + "\n".join(f"- {k}" for k in m.key_ideas) + f"\n\n**Ejercicio:** {m.exercise}"}
                for i, m in enumerate(modules, start=1)]
    sections.append({"key": "autoevaluacion", "title": "Autoevaluación", "type": "table", "columns": ["Pregunta", "Respuesta"], "rows": [[q.question, q.answer] for q in quiz]})
    sections.append({"key": "cobertura", "title": "Cobertura", "type": "list", "items": [
        f"Material: {f['name']} ({len(text):,} caracteres de texto).", f"Analizado: {covered:,} caracteres ({round(100 * covered / len(text))} %)." + ("" if covered == len(text) else " El resto no se leyó: divide el documento para cubrirlo."),
        f"Tarjetas de repaso creadas en el mazo «{deck}»: {created}.", f"Generado con {meta['connection']}; contrástalo con el material original."]})
    d = review.create(ctx.space_id, "documento", f"Ruta de estudio: {deck}", {"summary": f"{len(modules)} módulos, {len(quiz)} preguntas y {created} tarjetas nuevas.", "sections": sections}, author="jarvis", job_id=ctx.id)
    return {"mensaje": f"Ruta de estudio lista: {len(modules)} módulos y {created} tarjetas en «{deck}».", "deliverable_ids": [d["id"]], "tarjetas": created}


class Answer(BaseModel):
    answer: str
    cited: list[str] = Field(default_factory=list, description="IDs de las notas usadas, tal como aparecen en el atributo id")


def ask_notes(space_id: str, question: str) -> dict:
    """Responde con las notas del propio usuario. Recuperación por coincidencia de palabras (sin enviar nada) y redacción con un modelo permitido para el espacio."""
    words = {w for w in norm(question).split() if len(w) > 3}
    scored = []
    for kind in ("note", "reading", "journal", "choice", "study_note"):
        for r in records.list_records(space_id, kind, limit=5000):
            text = " ".join(str(v) for v in [r["title"], *r["data"].values()] if v)
            hits = sum(norm(text).count(w) for w in words)
            if hits:
                scored.append((hits, r, text))
    scored.sort(key=lambda x: -x[0])
    top = scored[:8]
    if not top:
        return {"answer": "No encontré nada en tus notas, lecturas, diario o decisiones que coincida con esa pregunta.", "sources": [], "model": None}
    block = "\n".join(f"<nota id=\"{r['id']}\" tipo=\"{r['kind']}\" fecha=\"{r['created_at'][:10]}\" titulo=\"{r['title']}\">\n{t[:1800]}\n</nota>" for _, r, t in top)

    class _Ctx:  # contexto mínimo para ask_json fuera de un trabajo
        def __init__(self):
            self.router, self.space_id, self.id = router.Ctx(space_id=space_id, limits={"max_calls": 3, "max_tokens": 30000, "max_cost_usd": 0.2}), space_id, None
        def log(self, *_a, **_k):
            pass

    out, meta = ask_json(_Ctx(), Answer, max_tokens=900, user=f"Pregunta: {question}\n\n{block}",
                         system="Respondes en español usando solo las notas del usuario que se te dan entre <nota>. Si no bastan, dilo. Cita los id de las notas que uses. No inventes.")
    valid = {r["id"]: r for _, r, _ in top}
    return {"answer": out.answer, "model": meta["connection"],
            "sources": [{"id": i, "title": valid[i]["title"], "kind": valid[i]["kind"], "date": valid[i]["created_at"][:10]} for i in dict.fromkeys(out.cited) if i in valid]}
