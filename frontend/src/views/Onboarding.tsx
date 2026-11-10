import { useEffect, useState } from "react";
import { api, ApiError, type Job, type Space } from "../api";
import type { Boot } from "../store";
import { Badge, Btn, Check, FieldRow, Panel, Select, Text } from "../components/ui";
import { ConnectionForm } from "./Connections";

const BUSINESS = [["ecommerce", "E-commerce físico o digital"], ["infoproducto", "Infoproductos"], ["servicio_b2b", "Servicios B2B"], ["clipping", "Clipping remunerado"], ["marca_personal", "Marca personal"], ["otro", "Otro negocio digital"]];
const STEPS = ["Tu espacio", "Marca o proyecto", "Proveedor", "Costo y datos", "Primer recorrido"];

export function Onboarding({ boot, reload }: { boot: Boot; reload: () => Promise<void> }) {
  const [step, setStep] = useState(0);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [name, setName] = useState(boot.settings.user_name || "");
  const [types, setTypes] = useState<string[]>(boot.settings.business_types || []);
  const [bizName, setBizName] = useState("Mi negocio");
  const [spaces, setSpaces] = useState<Space[]>(boot.spaces);
  const biz = spaces.find((s) => s.kind !== "personal");
  const [itemKind, setItemKind] = useState("brand");
  const [itemName, setItemName] = useState("");
  const [created, setCreated] = useState<string[]>([]);
  const [conns, setConns] = useState<any[]>([]);
  const [adding, setAdding] = useState(false);
  const [policy, setPolicy] = useState("solo_local");
  const [question, setQuestion] = useState("");
  const [job, setJob] = useState<Job | null>(null);
  const [tour, setTour] = useState<string[]>([]);
  const [avail, setAvail] = useState<Record<string, any>>({});

  const guard = async <T,>(p: Promise<T>): Promise<T | undefined> => {
    setBusy(true); setError("");
    try { return await p; } catch (e) { setError(e instanceof ApiError ? e.message : "Error inesperado"); return undefined; } finally { setBusy(false); }
  };
  const loadConns = () => api<any[]>("/connections").then(setConns).catch(() => undefined);
  useEffect(() => { loadConns(); }, []);
  useEffect(() => { if (biz && step >= 3) api("/availability", { query: { space: biz.id } }).then(setAvail).catch(() => undefined); }, [step, biz?.id, policy]);
  useEffect(() => {
    if (!job || ["completed", "failed", "cancelled", "waiting_config", "waiting_quota"].includes(job.status)) return;
    const t = setInterval(() => api<Job>(`/jobs/${job.id}`).then(setJob).catch(() => undefined), 1500);
    return () => clearInterval(t);
  }, [job?.id, job?.status]);

  const step1 = async () => {
    const ok = await guard((async () => {
      await api("/settings", { method: "PATCH", body: { user_name: name.trim() || "usuario", business_types: types } });
      let list = await api<Space[]>("/spaces");
      if (!list.some((s) => s.kind === "personal")) await api("/spaces", { body: { name: "Personal", kind: "personal", ai_policy: "solo_local" } });
      if (!list.some((s) => s.kind !== "personal")) await api("/spaces", { body: { name: bizName.trim() || "Mi negocio", kind: "negocio", ai_policy: "solo_local" } });
      list = await api<Space[]>("/spaces");
      setSpaces(list);
      return true;
    })());
    if (ok) setStep(1);
  };
  const step2 = async () => {
    if (!itemName.trim()) { setStep(2); return; }
    const rec = await guard(api<any>("/records", { body: { space: biz!.id, kind: itemKind, title: itemName.trim(), data: itemKind === "project" && types[0] ? { type: types[0] } : {} } }));
    if (rec) { setCreated((c) => [...c, `${itemKind === "brand" ? "Marca" : "Proyecto"} «${rec.title}»`]); setItemName(""); setStep(2); }
  };
  const step4 = async () => { if (await guard(api(`/spaces/${biz!.id}`, { method: "PATCH", body: { ai_policy: policy } }))) setStep(4); };
  const canResearch = avail.busqueda?.disponible;
  const runTour = async () => {
    const lines: string[] = [];
    const ok = await guard((async () => {
      const task = await api<any>("/records", { body: { space: biz!.id, kind: "task", title: "Revisar mi primer entregable en Jarvis" } });
      lines.push(`Tarea creada en «${biz!.name}»: ${task.title}`);
      if (canResearch && question.trim()) {
        const res = await api<{ job: Job }>("/jobs", { body: { space: biz!.id, type: "opportunity_research", title: `Oportunidades: ${question.slice(0, 80)}`, params: { question, max_queries: 2, max_pages: 4 } } });
        setJob(res.job);
        lines.push(`Investigación real lanzada: ${res.job.id}. La verás avanzar aquí y en Trabajos.`);
      } else {
        const d = await api<any>("/deliverables", { body: { space: biz!.id, kind: "documento", title: "Mi primer documento", content: { summary: "", sections: [{ key: "contenido", title: "Contenido", type: "text", body: "Documento de prueba creado durante la configuración inicial. Edítalo en Revisión para crear una versión nueva." }] } } });
        const ex = await api<any>(`/deliverables/${d.id}/export`, { body: { space: biz!.id, format: "md" } });
        lines.push(`Documento ${d.id} creado y exportado a ${ex.carpeta}`);
        lines.push("Recorrido sin IA completado: registro, entregable versionado y exportación local funcionan sin ninguna conexión.");
      }
      return true;
    })());
    if (ok) setTour(lines);
  };
  const finish = async () => { if (await guard(api("/settings", { method: "PATCH", body: { onboarded: true } }))) await reload(); };

  return (
    <div className="wizard">
      <div className="brand" style={{ fontSize: 18 }}>JARVIS OS</div>
      <div className="steps">{STEPS.map((s, i) => <span key={s} aria-current={i === step ? "step" : undefined}>{i + 1}. {s}</span>)}</div>
      {error && <div className="errorbox" role="alert">{error}</div>}

      {step === 0 && <Panel title="Crea tu espacio" note="Se crearán dos espacios separados: uno personal (solo proveedores locales) y uno de negocio. Podrás añadir más para cada marca o cliente.">
        <div className="form">
          <FieldRow label="¿Cómo te llamas? (se usa para firmar aprobaciones)"><Text value={name} onChange={setName} /></FieldRow>
          <FieldRow label="Nombre de tu primer espacio de negocio"><Text value={bizName} onChange={setBizName} /></FieldRow>
          <FieldRow group label="¿Qué negocios vas a operar?" wide><div className="stack">{BUSINESS.map(([k, t]) => <Check key={k} checked={types.includes(k)} onChange={(v) => setTypes((x) => (v ? [...x, k] : x.filter((y) => y !== k)))}>{t}</Check>)}</div></FieldRow>
        </div>
        <div className="row row--end"><Btn kind="primary" busy={busy} disabled={!name.trim()} onClick={step1}>Continuar</Btn></div>
      </Panel>}

      {step === 1 && <Panel title="Registra una marca o un proyecto" note={`Se guardará en el espacio «${biz?.name}». Puedes omitirlo y hacerlo después.`}>
        <div className="form">
          <FieldRow label="Tipo"><Select value={itemKind} onChange={setItemKind} options={[["brand", "Marca"], ["project", "Proyecto"]]} /></FieldRow>
          <FieldRow label="Nombre"><Text value={itemName} onChange={setItemName} /></FieldRow>
        </div>
        {created.map((c) => <p key={c} className="small"><Badge value="ok" text="Creado" /> {c}</p>)}
        <div className="row row--end"><Btn onClick={() => setStep(0)}>Atrás</Btn><Btn kind="primary" busy={busy} onClick={step2}>{itemName.trim() ? "Guardar y continuar" : "Omitir"}</Btn></div>
      </Panel>}

      {step === 2 && <Panel title="Configura un proveedor (opcional)" note="Sin proveedores funcionan proyectos, archivos, tareas, revisión, importación/exportación y video. Para investigar necesitas búsqueda (Tavily o Brave); para redactar y analizar, un modelo de texto (Ollama local, Gemini, Groq u otro compatible).">
        {conns.length === 0 ? <p className="muted">Aún no hay conexiones.</p> : conns.map((c) => <p key={c.id} className="small"><Badge value={c.status} text={c.status_label} /> {c.name} — {c.provider_label}{c.last_error && c.status !== "operativa" ? ` · ${c.last_error}` : ""}</p>)}
        <div className="row row--end"><Btn onClick={() => setStep(1)}>Atrás</Btn><Btn onClick={() => setAdding(true)}>Añadir y probar una conexión</Btn><Btn kind="primary" onClick={() => setStep(3)}>{conns.length ? "Continuar" : "Omitir por ahora"}</Btn></div>
        {adding && <ConnectionForm meta={boot} notify={(t, k) => { if (k === "error") setError(t); }} onClose={() => { setAdding(false); loadConns(); }} onSaved={() => { setAdding(false); loadConns(); }} />}
      </Panel>}

      {step === 3 && <Panel title="Política de costo y datos">
        <div className="stack">
          <p><Badge value="ok" text="Gasto de pago: desactivado" /> Las conexiones de pago no se usan hasta que lo actives en Conexiones y definas un presupuesto mensual.</p>
          <FieldRow label={`¿Qué proveedores pueden recibir datos de «${biz?.name}»?`} hint="El espacio Personal queda en «solo proveedores locales». Puedes cambiar ambas políticas después en Proyectos → Espacios.">
            <Select value={policy} onChange={setPolicy} options={[["solo_local", "Solo proveedores locales (Ollama, transcripción local)"], ["nube_permitida", "También proveedores en la nube que yo haya configurado y aceptado"], ["sin_ia", "Ninguno: sin IA en este espacio"]]} />
          </FieldRow>
          {conns.some((c) => !c.is_local) && policy === "solo_local" && <p className="note note--amber">Has configurado un proveedor en la nube: con «solo locales» no se usará en este espacio.</p>}
        </div>
        <div className="row row--end"><Btn onClick={() => setStep(2)}>Atrás</Btn><Btn kind="primary" busy={busy} onClick={step4}>Continuar</Btn></div>
      </Panel>}

      {step === 4 && <Panel title="Primer recorrido real">
        <div className="stack">
          {canResearch ? <>
            <p>Hay búsqueda disponible en «{biz?.name}»{avail.extraccion?.disponible ? " y un modelo de texto para analizar" : " (sin modelo de texto: obtendrás la evidencia recopilada, sin análisis)"}. Lanza una investigación pequeña (2 consultas, 4 páginas).</p>
            <FieldRow label="¿Qué quieres investigar?"><Text value={question} onChange={setQuestion} placeholder="Ej.: accesorios para gatos de interior en España" /></FieldRow>
          </> : <p>No hay búsqueda disponible en «{biz?.name}»{conns.length ? ` (${(avail.busqueda?.motivos || []).join("; ") || "ninguna conexión con esa capacidad"})` : ""}. El recorrido creará una tarea y un documento versionado, y lo exportará: todo real y sin IA.</p>}
          {tour.map((l) => <p key={l} className="small wrap"><Badge value="ok" text="Hecho" /> {l}</p>)}
          {job && <p className="small wrap"><Badge value={job.status} text={job.status_label} /> {job.message || job.stage || "En cola"}{job.error ? ` — ${job.error}` : ""}</p>}
        </div>
        <div className="row row--end">
          <Btn onClick={() => setStep(3)}>Atrás</Btn>
          {!tour.length && <Btn busy={busy} disabled={!!canResearch && !question.trim()} onClick={runTour}>Ejecutar recorrido</Btn>}
          <Btn kind="primary" busy={busy} onClick={finish}>{tour.length ? "Entrar en Jarvis" : "Omitir y entrar"}</Btn>
        </div>
      </Panel>}
    </div>
  );
}
