import { useEffect, useState } from "react";
import { api, fmtNum, label, type Deliverable, type Rec } from "../api";
import { useApp, useData } from "../store";
import { DeliverableView } from "../components/DeliverableView";
import { RecordsPanel } from "../components/RecordsPanel";
import { FileTable, UploadButton, useFiles, useRecords } from "../components/shared";
import { Badge, Btn, Empty, ErrorBox, FieldRow, Modal, Panel, Rich, Select, Skeleton, Stat, Tabs, Text } from "../components/ui";
import { fmtDate } from "../api";
import { AskNotes, HealthImport, OfxImport, Scripture, StudyRoute } from "../components/LifeTools";

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
              <Stat label="Proyectado" value={fmtNum(t.ingreso_proyectado)} hint="Aún sin compromiso" />
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
      {tab === "movimientos" && <OfxImport onDone={bump} />}
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

function Guides({ items, more }: { items: [string, string][]; more?: string }) {
  const { nav } = useApp();
  return (
    <div className="row guides">
      <span className="small muted">Guías</span>
      {items.map(([col, title]) => <Btn small key={title} onClick={() => nav(`biblioteca/${col}/${encodeURIComponent(title + ".md")}`)}>{title.split(" - ")[0].split(" (")[0]}</Btn>)}
      {more && <Btn small kind="ghost" onClick={() => nav("biblioteca")}>Ver las 18 en la biblioteca</Btn>}
    </div>
  );
}

function CardReview() {
  const { space, run } = useApp();
  const [tick, setTick] = useState(0);
  const [shown, setShown] = useState(false);
  const cards = useData<Rec[]>(() => api("/life/cards", { query: { space: space.id } }), [space.id, tick]);
  const card = cards.data?.[0];
  const grade = async (g: number) => { await run(api("/life/review", { body: { space: space.id, id: card!.id, grade: g } })); setShown(false); setTick((n) => n + 1); };
  return (
    <Panel title={`Repaso de hoy${cards.data ? ` · ${cards.data.length} tarjeta(s)` : ""}`} note="Repetición espaciada: cada acierto aleja el siguiente repaso; cada fallo lo trae a mañana. Diez minutos al día rinden más que una tarde entera al mes.">
      {!cards.data ? <Skeleton /> : !card ? <p className="muted">Nada que repasar hoy. Crea tarjetas abajo: una pregunta por tarjeta, con tus palabras.</p> : (
        <div className="stack">
          <p className="small muted">{card.data.deck || "Sin mazo"}</p>
          <p className="flash">{card.title}</p>
          {shown ? <><div className="flash flash--back"><Rich text={card.data.back || ""} /></div>
            <div className="row">{[[0, "Otra vez"], [1, "Difícil"], [2, "Bien"], [3, "Fácil"]].map(([g, t]) => <Btn key={g} kind={g === 2 ? "primary" : "default"} onClick={() => grade(g as number)}>{t}</Btn>)}</div></>
            : <div><Btn kind="primary" onClick={() => setShown(true)}>Mostrar respuesta</Btn></div>}
        </div>
      )}
    </Panel>
  );
}

function LifeSummary({ go }: { go: (area: Area) => void }) {
  const { space, doneTick } = useApp();
  const s = useData<any>(() => api("/life/summary", { query: { space: space.id } }), [space.id, doneTick]);
  if (s.error) return <ErrorBox message={s.error} retry={s.reload} />;
  if (!s.data) return <Skeleton />;
  const d = s.data, none = "sin datos";
  const v = (x: any, unit = "") => (x === null || x === undefined ? none : `${fmtNum(x, 1)}${unit}`);
  return (
    <>
      <div className="grid grid--2">
        <Panel title="Cuerpo" actions={<Btn small kind="ghost" onClick={() => go("cuerpo")}>Abrir</Btn>}>
          <div className="stats">
            <Stat label="Sueño, 7 días" value={v(d.cuerpo.sueno_7d, " h")} hint={`${d.cuerpo.noches_registradas_7d} noche(s) registradas · 30 días: ${v(d.cuerpo.sueno_30d, " h")}`} />
            <Stat label="Entrenos, 7 días" value={v(d.cuerpo.entrenos_7d)} hint={d.cuerpo.minutos_entreno_7d !== null ? `${d.cuerpo.minutos_entreno_7d} min` : undefined} />
            <Stat label="Lista de mercado" value={d.cuerpo.por_comprar} />
          </div>
        </Panel>
        <Panel title="Mente" actions={<Btn small kind="ghost" onClick={() => go("mente")}>Abrir</Btn>}>
          <div className="stats">
            <Stat label="Tarjetas para hoy" value={d.mente.tarjetas_para_hoy} tone={d.mente.tarjetas_para_hoy ? "amber" : undefined} />
            <Stat label="Enfoque, 7 días" value={`${d.mente.minutos_enfoque_7d} min`} hint={`${d.mente.bloques_enfoque_7d} bloque(s) · ${d.mente.interrupciones_7d} interrupciones`} />
            <Stat label="Ánimo, 7 días" value={v(d.mente.animo_7d, " / 5")} hint={d.mente.animo_7d_previos !== null ? `semana anterior: ${fmtNum(d.mente.animo_7d_previos, 1)}` : undefined} />
          </div>
        </Panel>
        <Panel title="Espíritu" actions={<Btn small kind="ghost" onClick={() => go("espiritu")}>Abrir</Btn>}>
          <div className="stats">
            <Stat label="Devocionales, 7 días" value={d.espiritu.devocionales_7d} hint={`${d.espiritu.minutos_7d} min`} />
            <Stat label="Oraciones abiertas" value={d.espiritu.oraciones_abiertas} hint={`${d.espiritu.respondidas} respondidas`} />
          </div>
        </Panel>
        <Panel title="Patrimonio" actions={<Btn small kind="ghost" onClick={() => go("patrimonio")}>Abrir</Btn>}>
          <div className="stats">
            {d.economia.patrimonio ? d.economia.patrimonio.map((p: any) => <Stat key={p.moneda} label={`Patrimonio neto ${p.moneda}`} value={fmtNum(p.neto, 0)} hint={`activos ${fmtNum(p.activos, 0)} · deudas ${fmtNum(p.deudas, 0)}`} />) : <Stat label="Patrimonio neto" value={none} hint="Registra tus cuentas" />}
            <Stat label="Suscripciones al mes" value={d.economia.suscripciones_mes ? d.economia.suscripciones_mes.map((x: any) => `${fmtNum(x.importe)} ${x.moneda === "SIN MONEDA" ? "" : x.moneda}`).join(" · ") : none} />
          </div>
        </Panel>
      </div>
      {(d.economia.alertas.length > 0 || d.vencimientos.length > 0 || d.economia.presupuesto.some((b: any) => b.excedido) || d.economia.saldos_sin_actualizar.length > 0) && (
        <Panel title="Requiere tu atención">
          {d.vencimientos.map((x: any, i: number) => <div key={`v${i}`} className="check-row" style={{ gridTemplateColumns: "150px 1fr" }}><Badge value={x.dias < 0 ? "fail" : "warn"} text={x.dias < 0 ? `Vencido hace ${-x.dias} d` : `En ${x.dias} día(s)`} /><div>{x.tipo}: {x.titulo} <span className="muted">· {x.fecha}</span></div></div>)}
          {d.economia.presupuesto.filter((b: any) => b.excedido).map((b: any) => <div key={b.categoria} className="check-row" style={{ gridTemplateColumns: "150px 1fr" }}><Badge value="warn" text="Presupuesto" /><div>{b.categoria}: gastado {fmtNum(b.gastado)} de {fmtNum(b.limite)} este mes.</div></div>)}
          {d.economia.alertas.map((a: any, i: number) => <div key={`a${i}`} className="check-row" style={{ gridTemplateColumns: "150px 1fr" }}><Badge value="warn" text={label(a.tipo)} /><div className="wrap">{a.texto}</div></div>)}
          {d.economia.saldos_sin_actualizar.length > 0 && <div className="check-row" style={{ gridTemplateColumns: "150px 1fr" }}><Badge value="mute" text="Saldos antiguos" /><div>Sin actualizar hace más de 45 días: {d.economia.saldos_sin_actualizar.join(", ")}.</div></div>}
        </Panel>
      )}
      <p className="note">{d.nota}</p>
    </>
  );
}

type Area = "resumen" | "organizacion" | "cuerpo" | "mente" | "espiritu" | "patrimonio";
const SUBS: Record<Exclude<Area, "resumen">, [string, string][]> = {
  organizacion: [["tareas", "Tareas"], ["capturas", "Capturas"], ["enfoque", "Enfoque"], ["habitos", "Hábitos"]],
  cuerpo: [["entrenos", "Entrenamientos"], ["sueno", "Sueño"], ["nutricion", "Nutrición"], ["imagen", "Imagen personal"], ["salud", "Historial de salud"], ["actividad", "Actividad diaria"]],
  mente: [["cerebro", "Segundo cerebro"], ["aprendizaje", "Aprendizaje"], ["habilidades", "Habilidades"], ["lecturas", "Lecturas"], ["diario", "Diario"], ["decisiones", "Decisiones"]],
  espiritu: [["devocional", "Lectura y devocional"], ["oracion", "Diario de oración"], ["estudio", "Estudio bíblico"], ["comunidad", "Comunidad"], ["reflexion", "Reflexión"]],
  patrimonio: [["cuentas", "Cuentas y patrimonio"], ["presupuesto", "Presupuesto"], ["suscripciones", "Suscripciones"], ["inversiones", "Inversiones"], ["documentos", "Contratos y administración"]],
};
const today = () => new Date().toISOString().slice(0, 10);

export function Personal() {
  const { space, boot, setSpace, nav } = useApp();
  const [area, setArea] = useState<Area>("organizacion");
  const [cardTick, setCardTick] = useState(0);
  const [sub, setSub] = useState<Record<string, string>>({ organizacion: "tareas", cuerpo: "entrenos", mente: "cerebro", espiritu: "devocional", patrimonio: "cuentas" });
  const personal = boot.spaces.find((s) => s.kind === "personal" && !s.archived);
  if (space.kind !== "personal") return (
    <div className="page">
      <Head title="Espacio personal" sub="Cuerpo, mente, espíritu y patrimonio viven en un espacio personal separado de tus negocios, y sus datos no salen de tu equipo." />
      <Empty title={`«${space.name}» es un espacio de ${boot.space_kinds[space.kind].toLowerCase()}`}
        action={personal ? <Btn kind="primary" onClick={() => setSpace(personal.id)}>Cambiar a «{personal.name}»</Btn> : <Btn kind="primary" onClick={() => nav("proyectos")}>Crear un espacio personal</Btn>}>
        Para mantener separados los datos personales, abre tu espacio personal. Las tareas de negocio se gestionan aquí mismo.
      </Empty>
      <RecordsPanel kind="task" columns={["due_date", "priority"]} quickAdd="Añadir tarea de este espacio…" title={`Tareas de «${space.name}»`} />
    </div>
  );
  const cur = area === "resumen" ? "" : sub[area];
  return (
    <div className="page">
      <Head title="Espacio personal" sub="Health OS, Mind OS, Faith OS y Wealth OS en un mismo lugar. Privado por diseño: nada de esto se envía a proveedores salvo que tú cambies la política del espacio y autorices una conexión para datos personales." />
      <Tabs value={area} onChange={setArea} tabs={[["organizacion", "Organización"], ["resumen", "Tablero"], ["cuerpo", "Cuerpo"], ["mente", "Mente"], ["espiritu", "Espíritu"], ["patrimonio", "Patrimonio"]]} />
      {area === "resumen" && <LifeSummary go={setArea} />}
      {area !== "resumen" && <div className="subtabs"><Tabs value={cur} onChange={(v) => setSub({ ...sub, [area]: v })} tabs={SUBS[area]} /></div>}

      {cur === "tareas" && <RecordsPanel kind="task" columns={["due_date", "priority"]} quickAdd="Añadir tarea…" />}
      {cur === "capturas" && <RecordsPanel kind="capture" columns={["body", "origin"]} quickAdd="Captura rápida: escribe y pulsa Intro…" defaults={{ origin: "texto" }} note="También puedes capturar por voz o por Telegram: «anota …» o «tarea: …»." />}
      {cur === "enfoque" && <><Guides items={[["mente", "Enfoque y productividad sin agotarte"]]} /><FocusTimer /><RecordsPanel kind="focus_block" columns={["date", "minutes", "interruptions", "goal", "outcome"]} /></>}
      {cur === "habitos" && <Habits />}

      {cur === "entrenos" && <><Guides items={[["cuerpo", "Energía, movimiento y vitalidad"]]} />
        <RecordsPanel kind="workout" columns={["date", "type", "minutes", "effort", "recovery"]} defaults={{ date: today(), type: "fuerza" }} importable
          note="Registra series, repeticiones y cargas en «Ejercicios», una línea por ejercicio. Jarvis no prescribe entrenamientos: compara tus registros y decide con tu entrenador si tienes una lesión o condición." /></>}
      {cur === "sueno" && <><Guides items={[["cuerpo", "Dormir mejor"], ["cuerpo", "Evitar el agotamiento (burnout)"]]} />
        <RecordsPanel kind="sleep" columns={["date", "hours", "quality", "bedtime", "wake_time"]} defaults={{ date: today() }} importable note="Los promedios de 7 y 30 días aparecen en el Tablero. Puedes importar un CSV exportado de tu reloj o app de salud." /></>}
      {cur === "nutricion" && <>
        <RecordsPanel kind="meal" title="Plan de comidas" columns={["date", "meal", "protein_g", "cost"]} defaults={{ date: today(), meal: "comida" }} />
        <RecordsPanel kind="pantry" title="Despensa y lista de mercado" columns={["quantity", "unit", "expiry", "est_cost"]} quickAdd="Añadir producto…" note="Cambia el estado a «por comprar» para armar la lista de mercado; expórtala a CSV para llevarla en el celular. No hay conexión con supermercados." /></>}
      {cur === "imagen" && <>
        <RecordsPanel kind="care_routine" columns={["frequency", "next_date"]} />
        <RecordsPanel kind="wardrobe" columns={["category", "color", "season", "combos"]} note="Sube las fotos en Proyectos → Archivos y pega aquí el ID de cada una para tener tu armario digital." /></>}
      {cur === "salud" && <RecordsPanel kind="health_record" columns={["type", "date", "professional", "next_date"]} defaults={{ type: "cita" }}
        note="Tu archivo personal de citas, resultados, medicamentos y preguntas para el profesional. Jarvis no interpreta resultados ni sustituye un diagnóstico." />}
      {cur === "actividad" && <HealthImport onDone={() => setCardTick((n) => n + 1)} />}
      {cur === "actividad" && <RecordsPanel key={"act" + cardTick} kind="activity" columns={["date", "type", "minutes", "sleep_hours"]} defaults={{ date: today() }} />}

      {cur === "cerebro" && <><Guides items={[["mente", "Segundo cerebro - cómo usarlo"]]} /><AskNotes />
        <RecordsPanel kind="note" columns={["area", "tags", "body"]} quickAdd="Título de la nota (una idea, afirmada)…" defaults={{ area: "mente" }} note="Busca por palabra en el cuadro de arriba. Las notas son privadas: solo se usan en «Pregunta a tus notas», y solo con un modelo que la política de este espacio permita." /></>}
      {cur === "aprendizaje" && <><Guides items={[["mente", "Aprender más rápido - método práctico"], ["habilidades", "Aprender a Aprender (Meta-Learning)"]]} /><CardReview key={cardTick} /><StudyRoute />
        <RecordsPanel kind="flashcard" title="Tarjetas" onChanged={() => setCardTick((n) => n + 1)} columns={["deck", "back", "due", "interval_days"]} importable hideFields={["due", "interval_days", "ease", "reps"]} note="El título es la pregunta. Importa un CSV con columnas pregunta, respuesta y mazo para cargar muchas de una vez." /></>}
      {cur === "habilidades" && <><Guides items={[["habilidades", "Inteligencia Emocional y Autogestión"], ["habilidades", "Negociación de Alto Nivel"]]} more="habilidades" />
        <RecordsPanel kind="skill" columns={["why", "weekly_hours", "next_review"]} note="Pocas a la vez: una en curso y una en práctica rinden más que diez pendientes." /></>}
      {cur === "lecturas" && <RecordsPanel kind="reading" columns={["author", "type", "progress"]} />}
      {cur === "diario" && <RecordsPanel kind="journal" columns={["date", "mood", "body"]} defaults={{ date: today() }} note="Privado. El ánimo (1–5) alimenta la tendencia del Tablero; es un simple promedio de lo que anotas, no una evaluación." />}
      {cur === "decisiones" && <RecordsPanel kind="choice" columns={["chosen", "review_date", "outcome"]} note="Escribe por qué decidiste con lo que sabías entonces y ponle fecha de evaluación: así aprendes de tus decisiones y no solo de sus resultados." />}

      {cur === "devocional" && <><Guides items={[["espiritu", "Acercarte más a Dios - prácticas diarias"]]} />
        <RecordsPanel kind="devotional" columns={["date", "passage", "type", "minutes"]} defaults={{ date: today(), type: "lectura" }} note="Anota la referencia del pasaje y tus propias notas. Para leer el pasaje, carga tu traducción en «Estudio bíblico». Jarvis no genera interpretaciones." /></>}
      {cur === "oracion" && <RecordsPanel kind="prayer" columns={["type", "date", "body", "follow_up"]} defaults={{ date: today(), type: "peticion" }} note="Peticiones, agradecimientos y su seguimiento. Totalmente privado." />}
      {cur === "estudio" && <Scripture />}
      {cur === "estudio" && <RecordsPanel kind="study_note" columns={["passage", "topic", "source"]} note="Cita siempre la traducción o el comentario que consultas y separa el texto citado de tu interpretación." />}
      {cur === "comunidad" && <RecordsPanel kind="ministry_event" columns={["date", "place", "team", "consent"]} note="Si guardas nombres o contactos de participantes, hazlo solo con su consentimiento." />}
      {cur === "reflexion" && <RecordsPanel kind="reflection" columns={["date", "practice", "minutes"]} defaults={{ date: today() }} />}

      {cur === "cuentas" && <><Guides items={[["economia", "Orden financiero personal"]]} />
        <RecordsPanel kind="account" columns={["type", "balance", "currency", "updated"]} note="Actualiza los saldos a mano o por CSV; el patrimonio neto del Tablero suma activos e inversiones y resta deudas, por moneda. Para traer movimientos del banco, importa su extracto OFX en Presupuesto." importable /></>}
      {cur === "presupuesto" && <><RecordsPanel kind="budget" columns={["category", "monthly_limit", "currency"]} note="El gasto real sale de tus movimientos pagados del mes con la misma categoría." />
        <OfxImport onDone={() => setCardTick((n) => n + 1)} />
        <RecordsPanel key={"tx" + cardTick} kind="transaction" title="Movimientos personales" columns={["type", "stage", "amount", "category", "date"]} importable defaults={{ type: "gasto", stage: "pagado" }} /></>}
      {cur === "suscripciones" && <RecordsPanel kind="subscription" columns={["amount", "period", "renewal_date", "category", "last_used", "needed"]} defaults={{ period: "mensual", needed: "si" }} importable
        note="El Tablero avisa de renovaciones en 14 días, servicios sin uso en 45 días, dudosos y posibles duplicados por categoría." />}
      {cur === "inversiones" && <RecordsPanel kind="investment" columns={["asset_type", "invested", "current_value", "risk", "review_date"]}
        note="Registro y seguimiento. Jarvis no recomienda activos ni opera dinero; para investigar un mercado usa la Mesa de oportunidades, que entrega fuentes." />}
      {cur === "documentos" && <RecordsPanel kind="admin_doc" columns={["type", "counterparty", "due_date", "amount"]} defaults={{ type: "contrato" }}
        note="Vencimientos a 30 días aparecen en el Tablero. La lista de revisión es para tu abogado o contador: Jarvis no da asesoría legal." />}
    </div>
  );
}
