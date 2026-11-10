import { useEffect, useState } from "react";
import { api, fmtNum, label, type Deliverable, type Rec } from "../api";
import { useApp, useData } from "../store";
import { DeliverableView } from "../components/DeliverableView";
import { RecordsPanel } from "../components/RecordsPanel";
import { FileTable, UploadButton, useFiles, useRecords } from "../components/shared";
import { Badge, Btn, Empty, ErrorBox, FieldRow, Modal, Panel, Select, Skeleton, Stat, Tabs, Text } from "../components/ui";
import { fmtDate } from "../api";

function Head({ title, sub }: { title: string; sub: string }) {
  return <div className="page__head"><div><h1 className="page__title">{title}</h1><p className="page__sub">{sub}</p></div></div>;
}

// ---------- Revisión, aprobación y experimentos

export function Review() {
  const { space, boot, route, nav, doneTick } = useApp();
  const [tab, setTab] = useState<"bandeja" | "experimentos" | "mediciones">("bandeja");
  const [status, setStatus] = useState("");
  const [kind, setKind] = useState("");
  const [tick, setTick] = useState(0);
  const list = useData<Deliverable[]>(() => api("/deliverables", { query: { space: space.id, status, kind } }), [space.id, status, kind, doneTick, tick]);
  const open = route[1];
  if (open) return (
    <div className="page">
      <div className="row"><Btn small kind="ghost" onClick={() => nav("revision")}>← Volver a la bandeja</Btn></div>
      <DeliverableView id={open} onChanged={() => setTick((n) => n + 1)} />
    </div>
  );
  return (
    <div className="page">
      <Head title="Revisión y aprobación" sub="Bandeja común de expedientes, propuestas, lotes, paquetes y videos. Las comprobaciones automáticas validan estructura, enlaces, fuentes y permisos registrados; la veracidad la decide una persona." />
      <Tabs value={tab} onChange={setTab} tabs={[["bandeja", "Bandeja"], ["experimentos", "Experimentos"], ["mediciones", "Mediciones"]]} />
      {tab === "bandeja" && (
        <Panel title="Entregables" actions={<>
          <div style={{ width: 180 }}><Select value={status} onChange={setStatus} empty="Todos los estados" options={boot.deliverable_statuses.map((s) => [s, label(s)])} /></div>
          <div style={{ width: 210 }}><Select value={kind} onChange={setKind} empty="Todos los tipos" options={Object.entries(boot.deliverable_kinds)} /></div>
        </>}>
          {list.error ? <ErrorBox message={list.error} retry={list.reload} /> : !list.data ? <Skeleton /> : !list.data.length ? (
            <Empty title="Nada que revisar">Los entregables aparecen aquí cuando un trabajo termina. También puedes crear un documento manual desde Leads → Propuestas.</Empty>
          ) : (
            <div className="tablewrap"><table><thead><tr><th>Título</th><th>Tipo</th><th>Estado</th><th>Versión</th><th>Actualizado</th></tr></thead>
              <tbody>{list.data.map((d) => (
                <tr key={d.id}><td className="wrap"><button className="linkbtn" onClick={() => nav(`revision/${d.id}`)}>{d.title}</button></td><td>{d.kind_label}</td><td><Badge value={d.status} /></td><td>v{d.current_version}</td><td className="small">{fmtDate(d.updated_at)}</td></tr>
              ))}</tbody></table></div>
          )}
        </Panel>
      )}
      {tab === "experimentos" && <RecordsPanel kind="experiment" columns={["variable", "metric", "window_end", "decision"]}
        note="Registrar un experimento no activa campañas ni cambia presupuestos: Jarvis solo documenta hipótesis, límite, ventana, resultado y decisión." />}
      {tab === "mediciones" && <RecordsPanel kind="metric_entry" columns={["experiment_id", "date", "variant", "metric", "value", "source"]} importable
        note="Carga los datos por CSV o a mano. No hay conectores de analítica en esta versión: indica siempre el origen de cada dato." />}
    </div>
  );
}

// ---------- Proyectos, marcas y biblioteca

export function Projects() {
  const { boot, space, run, reload, setSpace } = useApp();
  const [tab, setTab] = useState<"proyectos" | "marcas" | "biblioteca" | "archivos" | "espacios">("proyectos");
  const brands = useRecords("brand");
  const [brand, setBrand] = useState("");
  const files = useFiles();
  const [ns, setNs] = useState({ name: "", kind: "negocio", ai_policy: "solo_local" });
  useEffect(() => { if (!brand && brands.data?.length) setBrand(brands.data[0].id); }, [brands.data]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <div className="page">
      <Head title="Proyectos, marcas y biblioteca" sub="Cada espacio mantiene separados sus proyectos, marcas, archivos y conocimiento. Nada de un espacio se usa en otro." />
      <Tabs value={tab} onChange={setTab} tabs={[["proyectos", "Proyectos"], ["marcas", "Marcas"], ["biblioteca", "Biblioteca de marca"], ["archivos", "Archivos"], ["espacios", "Espacios"]]} />
      {tab === "proyectos" && <RecordsPanel kind="project" columns={["type", "owner", "due_date"]} />}
      {tab === "marcas" && <RecordsPanel kind="brand" columns={["market", "language", "voice"]} onChanged={brands.reload} />}
      {tab === "biblioteca" && (!brands.data?.length ? <Empty title="Primero registra una marca">La biblioteca (voz, pilares, ejemplos, historias reales, fuentes y permisos) pertenece a una marca concreta.</Empty> : <>
        <div className="row"><span className="muted small">Marca</span><div style={{ width: 260 }}><Select value={brand} onChange={setBrand} options={brands.data.map((b) => [b.id, b.title])} /></div></div>
        {brand && <RecordsPanel key={brand} kind="brand_asset" brandId={brand} columns={["type", "body", "permission"]} defaults={{ permission: "sin_confirmar", type: "ejemplo" }}
          note="Solo los elementos vigentes de esta marca se usan al generar contenido. Los marcados «sin confirmar» no se citan literalmente y generan un aviso en revisión." />}
      </>)}
      {tab === "archivos" && <Panel title="Archivos del espacio" actions={<UploadButton multiple onDone={files.reload} />}
        note="Tipos admitidos: video, audio, imagen, subtítulos, texto, CSV, JSON, PDF, HTML y ZIP. Archivar un archivo lo oculta, no lo borra del disco.">
        <FileTable files={files.data || []} onArchive={async (f) => { await run(api(`/files/${f.id}`, { method: "DELETE", query: { space: space.id } }), "Archivo archivado"); files.reload(); }} />
      </Panel>}
      {tab === "espacios" && <>
        <Panel title="Espacios" note="La política de IA decide qué proveedores pueden recibir datos de cada espacio. Los espacios personales exigen además que la conexión esté autorizada para datos personales.">
          <div className="tablewrap"><table><thead><tr><th>Espacio</th><th>Tipo</th><th>Política de IA</th><th /></tr></thead>
            <tbody>{boot.spaces.filter((s) => !s.archived).map((s) => (
              <tr key={s.id}><td>{s.name} {s.id === space.id && <Badge value="ok" text="actual" />}</td><td>{boot.space_kinds[s.kind]}</td>
                <td><select className="input" aria-label={`Política de IA de ${s.name}`} value={s.ai_policy} onChange={async (e) => { await run(api(`/spaces/${s.id}`, { method: "PATCH", body: { ai_policy: e.target.value } }), "Política actualizada"); reload(); }}>
                  {Object.entries(boot.ai_policies).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></td>
                <td>{s.id !== space.id && <Btn small onClick={() => setSpace(s.id)}>Cambiar a este</Btn>}</td></tr>
            ))}</tbody></table></div>
        </Panel>
        <Panel title="Nuevo espacio">
          <form className="form" onSubmit={async (e) => { e.preventDefault(); const s: any = await run(api("/spaces", { body: ns }), "Espacio creado"); if (s) { setNs({ ...ns, name: "" }); await reload(); } }}>
            <FieldRow label="Nombre"><Text value={ns.name} onChange={(v) => setNs({ ...ns, name: v })} /></FieldRow>
            <FieldRow label="Tipo"><Select value={ns.kind} onChange={(v) => setNs({ ...ns, kind: v })} options={Object.entries(boot.space_kinds)} /></FieldRow>
            <FieldRow label="Política de IA"><Select value={ns.ai_policy} onChange={(v) => setNs({ ...ns, ai_policy: v })} options={Object.entries(boot.ai_policies)} /></FieldRow>
            <div className="row row--end"><Btn kind="primary" type="submit" disabled={!ns.name.trim()}>Crear espacio</Btn></div>
          </form>
        </Panel>
      </>}
    </div>
  );
}

// ---------- Operaciones y economía

export function Operations() {
  const { space, doneTick } = useApp();
  const [tab, setTab] = useState<"economia" | "movimientos" | "tiempo" | "hitos" | "entregas" | "capacidad">("economia");
  const [tick, setTick] = useState(0);
  const eco = useData<any>(() => api("/economy/summary", { query: { space: space.id } }), [space.id, doneTick, tick]);
  const bump = () => setTick((n) => n + 1);
  return (
    <div className="page">
      <Head title="Operaciones y economía" sub="Proyectos, hitos, entregas, capacidad y control económico administrativo a partir de lo que registras o importas por CSV. No hay integraciones bancarias y esto no sustituye a tu contabilidad." />
      <Tabs value={tab} onChange={setTab} tabs={[["economia", "Resumen económico"], ["movimientos", "Movimientos"], ["tiempo", "Tiempo"], ["hitos", "Hitos"], ["entregas", "Entregas"], ["capacidad", "Capacidad"]]} />
      {tab === "economia" && <>
        {eco.data?.totales.map((t: any) => (
          <Panel key={t.moneda} title={`Totales en ${t.moneda}`}>
            <div className="stats">
              <Stat label="Acordado" value={fmtNum(t.ingreso_acordado)} hint="Pendiente de facturar" />
              <Stat label="Facturado" value={fmtNum(t.ingreso_facturado)} hint="Pendiente de cobrar" tone={t.ingreso_facturado ? "amber" : undefined} />
              <Stat label="Cobrado" value={fmtNum(t.ingreso_cobrado)} tone="ok" />
              <Stat label="Gastos pagados" value={fmtNum(t.gasto_pagado)} hint={t.gasto_comprometido ? `${fmtNum(t.gasto_comprometido)} comprometidos` : undefined} />
              <Stat label="Contribución" value={fmtNum(t.contribucion)} hint="Cobrado − gastos pagados" />
              <Stat label="Por hora" value={t.contribucion_por_hora === null ? "—" : fmtNum(t.contribucion_por_hora)} hint={`${fmtNum(t.horas)} h registradas`} />
            </div>
          </Panel>
        ))}
        <Panel title="Por proyecto" note={eco.data?.nota}>
          {!eco.data?.por_proyecto.length ? <Empty title="Sin movimientos registrados">Añade movimientos a mano o impórtalos desde un CSV de tu sistema de pagos o CRM en la pestaña Movimientos.</Empty> : (
            <div className="tablewrap"><table>
              <thead><tr><th>Proyecto</th><th>Moneda</th><th className="num">Acordado</th><th className="num">Facturado</th><th className="num">Cobrado</th><th className="num">Gastos pagados</th><th className="num">Créditos</th><th className="num">Horas</th><th className="num">Contribución</th><th className="num">Por hora</th></tr></thead>
              <tbody>{eco.data.por_proyecto.map((r: any, i: number) => (
                <tr key={i}><td>{r.proyecto}</td><td>{r.moneda}</td><td className="num">{fmtNum(r.ingreso_acordado)}</td><td className="num">{fmtNum(r.ingreso_facturado)}</td><td className="num">{fmtNum(r.ingreso_cobrado)}</td>
                  <td className="num">{fmtNum(r.gasto_pagado)}</td><td className="num">{fmtNum(r.creditos)}</td><td className="num">{fmtNum(r.horas)}</td><td className="num">{fmtNum(r.contribucion)}</td><td className="num">{r.contribucion_por_hora === null ? "—" : fmtNum(r.contribucion_por_hora)}</td></tr>
              ))}</tbody></table></div>
          )}
        </Panel>
        {eco.data?.suscripciones.length > 0 && <Panel title="Suscripciones registradas">
          <ul className="list">{eco.data.suscripciones.map((s: any) => <li key={s.id}>{s.titulo} — {fmtNum(s.importe)} {s.moneda || ""} {s.contraparte ? `· ${s.contraparte}` : ""} {s.fecha ? `· ${s.fecha}` : ""}</li>)}</ul>
        </Panel>}
      </>}
      {tab === "movimientos" && <RecordsPanel kind="transaction" columns={["type", "stage", "amount", "currency", "date", "counterparty"]} importable onChanged={bump} defaults={{ type: "ingreso", stage: "acordado" }}
        note="Cada movimiento cuenta una sola vez en su estado actual (acordado → facturado → cobrado). Cambia el estado económico al avanzar; no dupliques el movimiento. Los duplicados de un CSV se detectan por referencia externa o por fecha + importe + contraparte + concepto." />}
      {tab === "tiempo" && <RecordsPanel kind="time_entry" columns={["date", "hours", "owner"]} importable onChanged={bump} />}
      {tab === "hitos" && <RecordsPanel kind="milestone" columns={["due_date", "owner"]} />}
      {tab === "entregas" && <RecordsPanel kind="delivery" columns={["client", "due_date", "owner"]} />}
      {tab === "capacidad" && <RecordsPanel kind="capacity" columns={["owner", "week", "hours_available"]} />}
    </div>
  );
}

// ---------- Espacio personal

function Habits() {
  const { space, run } = useApp();
  const habits = useRecords("habit");
  const [tick, setTick] = useState(0);
  const logs = useRecords("habit_log", [tick]);
  const days = Array.from({ length: 7 }, (_, i) => { const d = new Date(); d.setDate(d.getDate() - (6 - i)); return d.toISOString().slice(0, 10); });
  const find = (h: string, day: string) => (logs.data || []).find((l) => l.data.habit_id === h && l.data.date === day);
  const toggle = async (h: Rec, day: string) => {
    const log = find(h.id, day);
    await run(log ? api(`/records/${log.id}`, { method: "PATCH", body: { space: space.id, data: { done: !log.data.done } } })
      : api("/records", { body: { space: space.id, kind: "habit_log", title: `${h.title} ${day}`, data: { habit_id: h.id, date: day, done: true } } }));
    setTick((n) => n + 1);
  };
  const active = (habits.data || []).filter((h) => h.status === "activo");
  return (
    <>
      <Panel title="Últimos 7 días" note="Marca lo que tú decides registrar. Jarvis no evalúa tu salud ni hace diagnósticos.">
        {!active.length ? <p className="muted small">Crea un hábito abajo para empezar a registrarlo.</p> : (
          <div className="tablewrap"><table><thead><tr><th>Hábito</th>{days.map((d) => <th key={d}>{d.slice(5)}</th>)}</tr></thead>
            <tbody>{active.map((h) => (
              <tr key={h.id}><td>{h.title}</td>{days.map((d) => { const done = !!find(h.id, d)?.data.done; return <td key={d}><input type="checkbox" aria-label={`${h.title} el ${d}`} checked={done} onChange={() => toggle(h, d)} /></td>; })}</tr>
            ))}</tbody></table></div>
        )}
      </Panel>
      <RecordsPanel kind="habit" columns={["frequency", "target"]} onChanged={habits.reload} />
    </>
  );
}

function FocusTimer() {
  const { space, run } = useApp();
  const [goal, setGoal] = useState("");
  const [minutes, setMinutes] = useState("25");
  const [end, setEnd] = useState<number | null>(null);
  const [left, setLeft] = useState(0);
  const [done, setDone] = useState<{ minutes: number } | null>(null);
  const [outcome, setOutcome] = useState("");
  useEffect(() => {
    if (!end) return;
    const t = setInterval(() => {
      const l = Math.max(0, Math.round((end - Date.now()) / 1000));
      setLeft(l);
      if (!l) { setEnd(null); setDone({ minutes: Number(minutes) }); }
    }, 500);
    return () => clearInterval(t);
  }, [end, minutes]);
  const saveBlock = async (status: string, mins: number) => {
    await run(api("/records", { body: { space: space.id, kind: "focus_block", title: goal || "Bloque de enfoque", status, data: { date: new Date().toISOString().slice(0, 10), start_time: new Date().toTimeString().slice(0, 5), minutes: mins, goal, outcome } } }), "Bloque registrado");
    setDone(null); setOutcome(""); setGoal("");
  };
  return (
    <Panel title="Bloque de enfoque ahora">
      {end ? (
        <div className="row"><span className="stat__value mono" role="timer">{String(Math.floor(left / 60)).padStart(2, "0")}:{String(left % 60).padStart(2, "0")}</span><span className="muted wrap">{goal || "Enfoque"}</span>
          <Btn onClick={() => { const spent = Math.round((Number(minutes) * 60 - left) / 60); setEnd(null); setDone({ minutes: spent }); }}>Terminar ahora</Btn></div>
      ) : (
        <form className="row" onSubmit={(e) => { e.preventDefault(); const m = Math.max(1, Math.min(240, Number(minutes) || 25)); setMinutes(String(m)); setLeft(m * 60); setEnd(Date.now() + m * 60000); }}>
          <div style={{ flex: 1, minWidth: 200 }}><Text value={goal} onChange={setGoal} placeholder="¿En qué vas a enfocarte?" /></div>
          <div style={{ width: 90 }}><Text type="number" value={minutes} onChange={setMinutes} /></div><span className="muted small">min</span><Btn kind="primary" type="submit">Empezar</Btn>
        </form>
      )}
      {done && (
        <Modal title="Bloque terminado" onClose={() => setDone(null)}>
          <FieldRow label={`Resultado (${done.minutes} min)`}><Text area rows={2} value={outcome} onChange={setOutcome} /></FieldRow>
          <div className="row row--end"><Btn onClick={() => saveBlock("omitido", done.minutes)}>Registrar como omitido</Btn><Btn kind="primary" onClick={() => saveBlock("completado", done.minutes)}>Registrar completado</Btn></div>
        </Modal>
      )}
    </Panel>
  );
}

export function Personal() {
  const { space, boot, setSpace, nav } = useApp();
  const [tab, setTab] = useState<"tareas" | "capturas" | "enfoque" | "habitos" | "actividad" | "diario" | "lecturas" | "reflexion">("tareas");
  const personal = boot.spaces.find((s) => s.kind === "personal" && !s.archived);
  if (space.kind !== "personal") return (
    <div className="page">
      <Head title="Espacio personal" sub="Tareas, capturas, enfoque, hábitos, actividad, diario, lecturas y reflexión viven en un espacio personal separado de tus negocios." />
      <Empty title={`«${space.name}» es un espacio de ${boot.space_kinds[space.kind].toLowerCase()}`}
        action={personal ? <Btn kind="primary" onClick={() => setSpace(personal.id)}>Cambiar a «{personal.name}»</Btn> : <Btn kind="primary" onClick={() => nav("proyectos")}>Crear un espacio personal</Btn>}>
        Para mantener separados los datos personales, abre tu espacio personal. Las tareas de negocio se gestionan en este mismo espacio desde Operaciones.
      </Empty>
      <RecordsPanel kind="task" columns={["due_date", "priority"]} quickAdd="Añadir tarea de este espacio…" title={`Tareas de «${space.name}»`} />
    </div>
  );
  return (
    <div className="page">
      <Head title="Espacio personal" sub="Tus datos personales no se envían a ningún proveedor salvo que cambies la política de este espacio y autorices expresamente una conexión para datos personales." />
      <Tabs value={tab} onChange={setTab} tabs={[["tareas", "Tareas"], ["capturas", "Capturas"], ["enfoque", "Enfoque"], ["habitos", "Hábitos"], ["actividad", "Actividad y descanso"], ["diario", "Diario"], ["lecturas", "Lecturas"], ["reflexion", "Reflexión"]]} />
      {tab === "tareas" && <RecordsPanel kind="task" columns={["due_date", "priority"]} quickAdd="Añadir tarea…" />}
      {tab === "capturas" && <RecordsPanel kind="capture" columns={["body", "origin"]} quickAdd="Captura rápida: escribe y pulsa Intro…" defaults={{ origin: "texto" }} note="También puedes capturar por voz desde Comando: «anota …» o «tarea: …»." />}
      {tab === "enfoque" && <><FocusTimer /><RecordsPanel kind="focus_block" columns={["date", "minutes", "goal", "outcome"]} /></>}
      {tab === "habitos" && <Habits />}
      {tab === "actividad" && <RecordsPanel kind="activity" columns={["date", "type", "minutes", "sleep_hours"]} defaults={{ date: new Date().toISOString().slice(0, 10) }} note="Registro personal de lo que tú anotas. No es consejo médico ni sustituye a un profesional." />}
      {tab === "diario" && <RecordsPanel kind="journal" columns={["date", "body"]} defaults={{ date: new Date().toISOString().slice(0, 10) }} note="Privado: el diario nunca forma parte de ningún prompt ni se envía a proveedores." />}
      {tab === "lecturas" && <RecordsPanel kind="reading" columns={["author", "type", "progress"]} />}
      {tab === "reflexion" && <RecordsPanel kind="reflection" columns={["date", "practice", "minutes"]} defaults={{ date: new Date().toISOString().slice(0, 10) }} note="Un lugar para tu práctica según tus propias preferencias. Jarvis no interpreta ni valora su contenido." />}
    </div>
  );
}
