import { useState } from "react";
import { api, fmtNum, label, type Rec } from "../api";
import { useApp, useData } from "../store";
import { RecordsPanel } from "../components/RecordsPanel";
import { JobList, Needs, useLaunch, useRecords } from "../components/shared";
import { Badge, Btn, ErrorBox, FieldRow, Modal, Panel, Select, Skeleton, Stat, Tabs, Text } from "../components/ui";

// Color de cada negocio: solo como marca pequeña de identidad, nunca como relleno.
const HUE: Record<string, string> = { ecom: "var(--accent)", b2b: "var(--ok)", clip: "#c59bff", brands: "#f28b6b" };
const TOOLS: [string, string, string][] = [
  ["opportunity_research", "Investigación con fuentes", "Busca, lee y entrega un expediente con evidencia. Necesita búsqueda web o URLs."],
  ["lead_search", "Búsqueda de empresas", "Encuentra candidatos públicos y registra observaciones verificables."],
  ["content_batch", "Lote de contenido", "Ángulos, hooks y guiones para una marca. Necesita modelo de texto y una marca."],
];

function Seal({ value, hue }: { value: number | null; hue: string }) {
  const pct = value === null ? null : Math.round(value * 100);
  return (
    <svg viewBox="0 0 64 64" className="seal" role="img" aria-label={pct === null ? "Sin misiones registradas" : `${pct} % de misiones verificadas`}>
      <circle cx="32" cy="32" r="27" fill="none" stroke="var(--s3)" strokeWidth="4" />
      {pct !== null && <circle cx="32" cy="32" r="27" fill="none" stroke={hue} strokeWidth="4" strokeLinecap="round" pathLength="100" strokeDasharray={`${pct} 100`} transform="rotate(-90 32 32)" />}
      <text x="32" y="37" textAnchor="middle" className="seal__text">{pct === null ? "—" : `${pct}`}</text>
    </svg>
  );
}

export function Business() {
  const { space, run, reload, boot, nav, doneTick } = useApp();
  const launch = useLaunch();
  const [tab, setTab] = useState<"resumen" | "misiones" | "decisiones" | "alertas" | "horarios" | "agentes" | "manual">("resumen");
  const [tick, setTick] = useState(0);
  const [exec, setExec] = useState<Rec | null>(null);
  const [tool, setTool] = useState("opportunity_research");
  const [brand, setBrand] = useState("");
  const [input, setInput] = useState("");
  const s = useData<any>(() => api("/business/summary", { query: { space: space.id } }), [space.id, doneTick, tick, boot.settings.agents_paused]);
  const brands = useRecords("brand");
  const bump = () => setTick((n) => n + 1);
  const paused = !!boot.settings.agents_paused;
  const setPaused = async (v: boolean) => { await run(api("/settings", { method: "PATCH", body: { agents_paused: v } }), v ? "Agentes en pausa" : "Agentes reanudados"); await reload(); };
  const start = async () => {
    if (!exec) return;
    const text = input.trim() || exec.data.action || exec.title;
    const params = tool === "opportunity_research" ? { question: text, max_queries: 3, max_pages: 5, project_id: exec.project_id }
      : tool === "lead_search" ? { sector: text, max_candidates: 6 } : { brand_id: brand || null, product: text, objective: "confianza", count: 5 };
    const job = await launch(tool, params, `Misión: ${exec.title}`.slice(0, 180));
    if (job) {
      await run(api(`/records/${exec.id}`, { method: "PATCH", body: { space: space.id, status: "en_cola", data: { evidence: [exec.data.evidence, `Trabajo ${job.id}`].filter(Boolean).join("\n") } } }));
      setExec(null);
      bump();
    }
  };
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">Centro de negocios</h1>
        <p className="page__sub">Tus cuatro negocios en un solo tablero: misiones por sección, avance verificado con evidencia, dinero real y agentes. Una misión solo cuenta como hecha cuando cumple su criterio de cierre y adjunta evidencia.</p></div>
        <Btn kind={paused ? "primary" : "amber"} onClick={() => setPaused(!paused)}>{paused ? "Reanudar agentes" : "Pausar todos los agentes"}</Btn></div>
      {paused && <div className="banner"><span><strong>Agentes en pausa.</strong> No se inicia ningún trabajo nuevo hasta que reanudes. Los avisos y la interfaz siguen funcionando.</span></div>}
      <Tabs value={tab} onChange={setTab} tabs={[["resumen", "Resumen"], ["misiones", "Misiones"], ["decisiones", "Decisiones"], ["alertas", "Monitores y alertas"], ["horarios", "Agentes con horario"], ["agentes", "Agentes"], ["manual", "Manual e integraciones"]]} />
      {s.error && <ErrorBox message={s.error} retry={s.reload} />}
      {tab === "resumen" && (!s.data ? <Skeleton /> : <>
        <div className="grid grid--2">
          {s.data.negocios.map((b: any) => (
            <Panel key={b.id} title={<span className="bizname"><i style={{ background: HUE[b.id] }} />{b.nombre}</span>} actions={<Btn small kind="ghost" onClick={() => setTab("misiones")}>Misiones</Btn>}>
              <div className="biz">
                <Seal value={b.avance} hue={HUE[b.id]} />
                <div className="stack">
                  <p>{b.avance === null ? <span className="muted">Sin misiones registradas todavía.</span> : <><strong>{b.verificadas}</strong> de {b.misiones} misiones verificadas · {b.abiertas} abiertas</>}</p>
                  <div className="row">
                    {b.por_aprobar > 0 && <Badge value="warn" text={`${b.por_aprobar} por aprobar`} />}
                    {b.bloqueadas > 0 && <Badge value="warn" text={`${b.bloqueadas} bloqueadas`} />}
                    {b.fallidas > 0 && <Badge value="fail" text={`${b.fallidas} fallidas`} />}
                    <span className="small muted">{b.proyectos} proyecto(s)</span>
                  </div>
                </div>
              </div>
              <div className="sections" aria-label="Avance por sección">
                {Object.entries(s.data.secciones).map(([id, name]: any) => {
                  const sec = b.por_seccion[id];
                  return <div key={id} className="sections__cell" title={`${name}: ${sec.total ? `${sec.verificadas} de ${sec.total} verificadas` : "sin misiones"}`}>
                    <span className="mono">{name.slice(0, 1)}</span>
                    <i><b style={{ transform: `scaleX(${sec.total ? sec.verificadas / sec.total : 0})`, background: HUE[b.id] }} /></i>
                    <span className="small muted">{sec.total ? `${sec.verificadas}/${sec.total}` : "—"}</span>
                  </div>;
                })}
              </div>
              <p className="small muted" style={{ marginTop: 12 }}>
                {b.economia ? b.economia.map((e: any) => `Cobrado ${fmtNum(e.cobrado)} ${e.moneda} · gastos ${fmtNum(e.gastos_pagados)} · contribución ${fmtNum(e.contribucion)}`).join(" | ") : "Dinero: sin datos (registra movimientos en un proyecto de este tipo)."}
              </p>
            </Panel>
          ))}
        </div>
        <Panel title="Transversal" note={s.data.nota}>
          <div className="stats">
            <Stat label="Agentes en ejecución" value={s.data.agentes.en_ejecucion} hint={`${s.data.agentes.en_cola} en cola · ${s.data.agentes.en_espera} en espera`} />
            <Stat label="Por revisar" value={s.data.transversal.por_revisar} tone={s.data.transversal.por_revisar ? "amber" : undefined} hint={`${s.data.transversal.borradores} borradores`} />
            <Stat label="Leads" value={s.data.transversal.leads} />
            <Stat label="Decisiones abiertas" value={s.data.transversal.decisiones_abiertas} />
            <Stat label="Clipping cobrado" value={s.data.transversal.clipping ? `${fmtNum(s.data.transversal.clipping.cobrado_usd)} USD` : "sin datos"} hint={s.data.transversal.alertas_clipping ? `${s.data.transversal.alertas_clipping} alertas` : undefined} />
          </div>
        </Panel>
      </>)}
      {tab === "misiones" && <RecordsPanel kind="mission" columns={["business", "section", "priority", "closure", "evidence"]} importable onChanged={bump}
        defaults={{ business: "ecom", section: "A_base_estable" }}
        rowActions={(r) => <Btn small disabled={["completada_verificada", "cancelada", "no_aplica"].includes(r.status)} onClick={() => { setExec(r); setInput(r.data.action || r.title); }}>Ejecutar</Btn>}
        note="Estados: pendiente → preparada → en cola → ejecutando → esperando (integración, datos o aprobación) → verificación → completada verificada. El último exige criterio de cierre y evidencia. Importa misiones por CSV con cualquier columna que quieras asignar." />}
      {tab === "decisiones" && <RecordsPanel kind="decision" columns={["business", "verdict", "hypothesis", "limit", "review_date"]} defaults={{ verdict: "continuar" }}
        note="Cada decisión —continuar, corregir, detener o ampliar— va con su hipótesis, su límite, su ventana y la evidencia en la que se apoya." />}
      {tab === "alertas" && <>
        <RecordsPanel kind="monitor" columns={["type", "every_hours", "last_run", "last_result"]} hideFields={["last_run", "last_result"]} defaults={{ type: "tareas_vencidas", every_hours: 6, notify: true }} onChanged={bump}
          rowActions={(r, reloadRow) => <Btn small onClick={async () => { const o: any = await run(api("/monitors/run", { body: { space: space.id, id: r.id, force: false } })); if (o) { run(Promise.resolve(), `${o.hallazgos} hallazgo(s), ${o.nuevos} nuevo(s), ${o.avisos} aviso(s)`); reloadRow(); bump(); } }}>Ejecutar ahora</Btn>}
          note="Cada monitor revisa datos reales con la frecuencia indicada, no repite un mismo hallazgo y avisa a tus canales del celular (máximo 12 avisos de monitores al día). Son reglas fijas, sin IA. Se detienen con «Pausar todos los agentes»." />
        <RecordsPanel key={tick} kind="alert" columns={["type", "detected", "notes"]} title="Alertas" />
      </>}
      {tab === "horarios" && <RecordsPanel kind="schedule" columns={["order", "frequency", "hour", "last_run", "last_result"]} hideFields={["last_run", "last_result"]} defaults={{ frequency: "diario", hour: 9, notify: true }} onChanged={bump}
        rowActions={(r, reloadRow) => <Btn small onClick={async () => { const o: any = await run(api("/schedules/run", { body: { space: space.id, id: r.id } })); if (o) { run(Promise.resolve(), o.error ? `No se pudo: ${o.respuesta}` : `Ejecutado: ${o.respuesta}`); reloadRow(); bump(); } }}>Ejecutar ahora</Btn>}
        note="Cada agente lanza a su hora la orden que escribas, igual que si la dijeras en Comando: «Busca oportunidades en accesorios para mascotas», «Resume lo pendiente», «Genera contenido para la marca Nova». Funcionan mientras Jarvis esté abierto, respetan la pausa de agentes y los presupuestos, y te avisan al celular con el resultado. Pulsa «Ejecutar ahora» para probar la orden antes de dejarla sola." />}
      {tab === "agentes" && <>
        <Panel title="Agentes disponibles hoy" note="Los agentes son los trabajos reales de Jarvis. Se ejecutan en paralelo hasta el límite configurado (2 por defecto, video de uno en uno), con cola persistente, cancelación y reanudación tras reinicio.">
          <div className="tablewrap"><table><thead><tr><th>Agente</th><th>Qué hace de verdad</th><th>Necesita</th></tr></thead><tbody>
            {[["Investigación", "Busca, lee fuentes y arma expedientes con citas verificadas", "Búsqueda web o URLs; modelo de texto para analizar"],
              ["Ventas B2B", "Encuentra empresas, registra observaciones y redacta propuestas", "Búsqueda web; modelo de texto"],
              ["Contenido", "Genera lotes de guiones por marca", "Modelo de texto"],
              ["Producción de video", "Recorta, reencuadra, subtitula y exporta con FFmpeg", "FFmpeg; transcripción opcional"],
              ["E-commerce", "Construye el paquete de página de producto para Shopify", "Nada; modelo de texto opcional"],
              ["Clipping", "Importa campañas y calcula estados sin mezclarlos", "Nada; modelo de texto opcional"],
              ["Calidad y permisos", "Comprobaciones automáticas, versiones y aprobaciones ligadas a versión", "Nada"],
              ["Jefe de gabinete (Jarvis)", "Interpreta órdenes por texto, voz o Telegram y lanza los demás", "Nada; modelo de texto para órdenes libres"]].map((r) => <tr key={r[0]}><td><strong>{r[0]}</strong></td><td className="wrap">{r[1]}</td><td className="small wrap">{r[2]}</td></tr>)}
          </tbody></table></div>
        </Panel>
        <Panel title="Actividad" actions={<Btn small onClick={() => nav("sistema")}>Ver todos los trabajos</Btn>}><JobList limit={10} /></Panel>
      </>}
      {tab === "manual" && <>
        <Panel title="Manual DOOMSDAY.html">
          <p><Badge value="warn" text="No importado" /> El archivo <span className="mono">DOOMSDAY.html</span> no se ha entregado a Jarvis, así que no hay ninguna tarea del manual cargada. No se ha inventado ninguna.</p>
          <p className="note">Cuando lo aportes se construirá el extractor que lea sus secciones A–F para los cuatro negocios, conserve cada texto original y genere la matriz de cobertura. Mientras tanto puedes registrar misiones a mano o importarlas por CSV en la pestaña Misiones, con los mismos campos: acción, cómo, entregable, criterio de cierre, parte de IA, intervención humana, activación y dependencia.</p>
        </Panel>
        <Panel title="Integraciones del plan" note="«Disponible» significa implementado en Jarvis; todas las conexiones externas siguen pendientes de comprobarse con tus credenciales.">
          <div className="tablewrap"><table><thead><tr><th>Integración</th><th>Estado en Jarvis</th><th>Cómo se cubre hoy</th></tr></thead><tbody>
            {[["Modelos de IA (Gemini/Gemma, Groq, compatible con OpenAI, Ollama)", "ok", "Disponible", "Conexiones"],
              ["Búsqueda web (Tavily, Brave)", "ok", "Disponible", "Conexiones"],
              ["Telegram (avisos y órdenes)", "ok", "Disponible", "Conexiones"],
              ["WhatsApp Business (avisos)", "ok", "Disponible, solo saliente", "Conexiones; ventana de 24 h de Meta"],
              ["ntfy (push al celular)", "ok", "Disponible", "Conexiones"],
              ["FFmpeg", "ok", "Disponible", "Editor audiovisual"],
              ["Webhooks / n8n", "ok", "Disponible, saliente con aprobación", "Envío externo desde Revisión"],
              ["Shopify", "warn", "Solo exportación", "ZIP de sección y plantilla; sin conexión a la tienda"],
              ["Claude y ChatGPT por API", "ok", "Disponible", "Conexiones"],
              ["Shopify, Stripe, PayPal, Notion, Cloudflare, GitHub, WooCommerce, Meta, TikTok, YouTube", "ok", "Disponible por conector universal", "Apps conectadas; lectura directa y escritura con aprobación"],
              ["Google Drive, Sheets, Gmail", "ok", "Disponible con OAuth propio", "Apps conectadas; necesitas tu client ID de Google Cloud"],
              ["Google Ads", "mute", "No implementado", "Su API exige token de desarrollador; usa CSV"],
              ["Higgsfield (imagen y video)", "mute", "No implementado", "Jarvis entrega prompts; importas los activos al editor"]].map((r) => <tr key={r[0]}><td className="wrap">{r[0]}</td><td><Badge value={r[1]} text={r[2]} /></td><td className="small wrap">{r[3]}</td></tr>)}
          </tbody></table></div>
        </Panel>
        <Panel title="Referencias"><div className="row">
          <Btn onClick={() => nav("biblioteca/negocios/" + encodeURIComponent("Modelos de negocio (tiers).md"))}>Modelos de negocio</Btn>
          <Btn onClick={() => nav("biblioteca/herramientas/" + encodeURIComponent("Mis enlaces de herramientas.md"))}>Herramientas</Btn>
          <Btn onClick={() => nav("biblioteca")}>Biblioteca completa</Btn>
        </div></Panel>
      </>}
      {exec && (
        <Modal title={`Ejecutar misión: ${exec.title}`} onClose={() => setExec(null)}>
          <div className="stack">
            <dl className="kv">
              <dt>Negocio</dt><dd>{label(exec.data.business)} · {label(exec.data.section)}</dd>
              <dt>Criterio de cierre</dt><dd>{exec.data.closure || <span className="amber">sin definir: no podrá verificarse</span>}</dd>
              <dt>Parte humana</dt><dd>{exec.data.human_part || "—"}</dd>
            </dl>
            <FieldRow label="Herramienta" hint={TOOLS.find((t) => t[0] === tool)?.[2]}><Select value={tool} onChange={setTool} options={TOOLS.map((t) => [t[0], t[1]])} /></FieldRow>
            {tool === "content_batch" && <FieldRow label="Marca"><Select value={brand} onChange={setBrand} empty="Sin marca" options={(brands.data || []).map((b) => [b.id, b.title])} /></FieldRow>}
            <FieldRow label="Qué debe hacer"><Text area rows={3} value={input} onChange={setInput} /></FieldRow>
            <Needs caps={tool === "content_batch" ? ["extraccion"] : []} optional={tool === "content_batch" ? [] : ["busqueda", "extraccion"]} />
            <p className="note">Plan: se crea un trabajo en la cola con límites de 40 llamadas y 30 minutos; verás su progreso en Agentes. El resultado llega como entregable a Revisión. La misión pasa a «en cola» y guarda el ID del trabajo como evidencia; marcarla «completada verificada» sigue siendo decisión tuya. Si ninguna herramienta encaja, la misión es manual: ejecútala tú y adjunta la evidencia.</p>
            <div className="row row--end"><Btn onClick={() => setExec(null)}>Cancelar</Btn><Btn kind="primary" onClick={start}>Lanzar</Btn></div>
          </div>
        </Modal>
      )}
    </div>
  );
}
