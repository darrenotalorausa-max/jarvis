import { useState } from "react";
import { api, fmtNum, label, url, type FileRow, type Rec } from "../api";
import { useApp, useData } from "../store";
import { RecordsPanel } from "../components/RecordsPanel";
import { DeliverableList, JobList, Needs, UploadButton, useFiles, useLaunch, useRecords } from "../components/shared";
import { Badge, Btn, Check, FieldRow, Modal, Panel, Select, Stat, Tabs, Text } from "../components/ui";

function Head({ title, sub }: { title: string; sub: string }) {
  return <div className="page__head"><div><h1 className="page__title">{title}</h1><p className="page__sub">{sub}</p></div></div>;
}
const lines = (s: string) => s.split("\n").map((x) => x.trim()).filter(Boolean);

// ---------- Mesa de oportunidades

export function Opportunities() {
  const launch = useLaunch();
  const files = useFiles();
  const projects = useRecords("project");
  const [f, setF] = useState<Record<string, any>>({ language: "es", max_queries: 4, max_pages: 6, freshness: "" });
  const [picked, setPicked] = useState<string[]>([]);
  const set = (k: string) => (v: any) => setF((x) => ({ ...x, [k]: v }));
  const docs = (files.data || []).filter((x) => /\.(pdf|txt|md|csv|html?|json)$/i.test(x.name));
  const go = () => launch("opportunity_research", { ...f, urls: lines(f.urls || ""), file_ids: picked, max_queries: Number(f.max_queries), max_pages: Number(f.max_pages) }, `Oportunidades: ${(f.question || f.category || "material aportado").slice(0, 80)}`);
  const T = (k: string, lab: string, ph?: string) => <FieldRow label={lab}><Text value={f[k]} onChange={set(k)} placeholder={ph} /></FieldRow>;
  return (
    <div className="page">
      <Head title="Mesa de oportunidades" sub="Investiga con búsqueda real, URLs y archivos. Cada afirmación conserva su fuente, su fecha de consulta y sus límites. No revisa todo internet ni garantiza productos ganadores." />
      <Needs caps={[]} optional={["busqueda", "extraccion"]} />
      <div className="grid grid--side">
        <Panel title="Nueva investigación" note="Sin proveedor de búsqueda puedes investigar aportando URLs o archivos. Sin modelo de texto se entrega la evidencia recopilada sin análisis automático: nada se inventa.">
          <form className="form" onSubmit={(e) => { e.preventDefault(); go(); }}>
            <FieldRow label="Pregunta libre" wide><Text area rows={2} value={f.question} onChange={set("question")} placeholder="¿Qué problema, público o categoría quieres explorar?" /></FieldRow>
            {T("category", "Categoría")}{T("exclusions", "Exclusiones", "Separadas por comas")}
            <FieldRow label="Tipo de negocio"><Select value={f.business_type} onChange={set("business_type")} empty="—" options={["ecommerce", "infoproducto", "servicio_b2b", "clipping", "marca_personal", "otro"].map((x) => [x, label(x)])} /></FieldRow>
            <FieldRow label="Tipo de oferta"><Select value={f.offer_type} onChange={set("offer_type")} empty="—" options={[["fisico", "Producto físico"], ["digital", "Producto digital"], ["servicio", "Servicio"], ["software", "Software"]]} /></FieldRow>
            {T("country", "País")}{T("country_code", "Código de país para la búsqueda", "ES, MX, US…")}{T("language", "Idioma (código)", "es")}
            {T("price_range", "Rango de precios")}{T("buyer_type", "Tipo de comprador")}{T("logistics", "Restricciones de logística")}
            {T("competition", "Competencia")}{T("seasonality", "Estacionalidad")}{T("recurrence", "Recurrencia del problema")}{T("target_margin", "Margen objetivo")}
            <FieldRow label="Frescura de las fuentes"><Select value={f.freshness} onChange={set("freshness")} options={[["", "Sin límite"], ["pd", "Último día"], ["pw", "Última semana"], ["pm", "Último mes"], ["py", "Último año"]]} /></FieldRow>
            <FieldRow label="Límite de consultas (1–8)"><Text type="number" value={f.max_queries} onChange={set("max_queries")} /></FieldRow>
            <FieldRow label="Límite de páginas a leer (1–15)"><Text type="number" value={f.max_pages} onChange={set("max_pages")} /></FieldRow>
            <FieldRow label="Proyecto"><Select value={f.project_id} onChange={set("project_id")} empty="Sin proyecto" options={(projects.data || []).map((p) => [p.id, p.title])} /></FieldRow>
            <FieldRow label="URLs a incluir (una por línea)" wide><Text area rows={2} value={f.urls} onChange={set("urls")} placeholder="https://…" /></FieldRow>
            <FieldRow group label="Archivos a incluir" wide hint="PDF, texto, Markdown, CSV, HTML o JSON.">
              <div className="stack">
                {docs.map((d) => <Check key={d.id} checked={picked.includes(d.id)} onChange={(v) => setPicked((p) => (v ? [...p, d.id] : p.filter((x) => x !== d.id)))}>{d.name}</Check>)}
                <div><UploadButton accept=".pdf,.txt,.md,.csv,.html,.htm,.json" onDone={(row) => { files.reload(); setPicked((p) => [...p, row.id]); }}>Subir documento</UploadButton></div>
              </div>
            </FieldRow>
            <div className="row row--end field--wide"><Btn kind="primary" type="submit" disabled={!(f.question || f.category || f.urls || picked.length)}>Investigar</Btn></div>
          </form>
        </Panel>
        <div className="stack">
          <Panel title="Investigaciones en curso"><JobList types={["opportunity_research"]} empty="Aún no has lanzado ninguna investigación." /></Panel>
        </div>
      </div>
      <Panel title="Expedientes"><DeliverableList kind="dossier" empty="Lanza una investigación para obtener un expediente editable con hechos, hipótesis, fuentes y plan de validación." /></Panel>
    </div>
  );
}

// ---------- Leads y ofertas B2B

export function Leads() {
  const { space, run, nav } = useApp();
  const launch = useLaunch();
  const [tab, setTab] = useState<"buscar" | "leads" | "propuestas" | "servicios" | "exclusiones">("buscar");
  const [f, setF] = useState<Record<string, any>>({ language: "es", max_candidates: 8 });
  const [prop, setProp] = useState<Rec | null>(null);
  const [pf, setPf] = useState<Record<string, any>>({});
  const services = useRecords("service");
  const set = (k: string) => (v: any) => setF((x) => ({ ...x, [k]: v }));
  const T = (k: string, lab: string, ph?: string) => <FieldRow label={lab}><Text value={f[k]} onChange={set(k)} placeholder={ph} /></FieldRow>;
  return (
    <div className="page">
      <Head title="Leads y ofertas B2B" sub="Busca empresas en fuentes públicas, registra solo observaciones verificables y prepara propuestas revisables. Jarvis no envía mensajes: entrega borradores y exportaciones." />
      <Tabs value={tab} onChange={setTab} tabs={[["buscar", "Buscar"], ["leads", "Leads"], ["propuestas", "Propuestas"], ["servicios", "Servicios que ofrezco"], ["exclusiones", "Exclusiones"]]} />
      {tab === "buscar" && <>
        <Needs caps={[]} optional={["busqueda", "extraccion"]} />
        <div className="grid grid--side">
          <Panel title="Buscar candidatos" note="Sin búsqueda puedes pegar una lista de webs. Sin modelo de texto los leads se crean con empresa, web, fuente, fecha y canal público; la observación queda pendiente.">
            <form className="form" onSubmit={(e) => { e.preventDefault(); launch("lead_search", { ...f, urls: lines(f.urls || ""), max_candidates: Number(f.max_candidates) }, `Leads: ${(f.sector || "lista de webs").slice(0, 80)}`); }}>
              {T("sector", "Sector")}{T("location", "Ubicación")}{T("language", "Idioma (código)")}{T("client_type", "Tipo de cliente")}
              {T("signals", "Señales públicas a buscar", "p. ej. sin reserva online")}{T("active_offer", "Oferta activa que deben tener")}
              <FieldRow label="Servicio que puedo prestar" wide><Text area rows={2} value={f.service} onChange={set("service")} /></FieldRow>
              <FieldRow label="Máximo de candidatos a investigar (1–25)"><Text type="number" value={f.max_candidates} onChange={set("max_candidates")} /></FieldRow>
              <FieldRow label="Webs a incluir (una por línea)" wide><Text area rows={2} value={f.urls} onChange={set("urls")} placeholder="https://…" /></FieldRow>
              <div className="row row--end field--wide"><Btn kind="primary" type="submit" disabled={!(f.sector || f.urls)}>Buscar empresas</Btn></div>
            </form>
          </Panel>
          <Panel title="Búsquedas y propuestas en curso"><JobList types={["lead_search", "lead_proposal"]} /></Panel>
        </div>
      </>}
      {tab === "leads" && <RecordsPanel kind="lead" columns={["website", "public_channel", "observation", "next_action"]} importable
        note="Exporta a CSV para llevar los leads a tu CRM. Los duplicados por dominio se omiten al importar y al buscar."
        rowActions={(r) => <Btn small onClick={() => { setProp(r); setPf({ service: r.data.service || "" }); }}>Preparar propuesta</Btn>} />}
      {tab === "propuestas" && <Panel title="Propuestas" actions={<Btn small onClick={async () => { const d: any = await run(api("/deliverables", { body: { space: space.id, kind: "proposal", title: "Propuesta manual" } })); if (d) nav(`revision/${d.id}`); }}>Propuesta manual en blanco</Btn>}>
        <DeliverableList kind="proposal" empty="Prepara una propuesta desde un lead, o crea una manual en blanco si no tienes un modelo de texto configurado." />
      </Panel>}
      {tab === "servicios" && <RecordsPanel kind="service" columns={["description", "price_from", "timeline"]} note="Tu catálogo: se usa como base de las propuestas. El precio nunca se inventa; si no lo indicas queda «por definir»." />}
      {tab === "exclusiones" && <RecordsPanel kind="exclusion" columns={["domain", "reason"]} note="Los dominios o nombres listados aquí nunca se investigan ni se convierten en lead." />}
      {prop && (
        <Modal title={`Preparar propuesta para ${prop.title}`} onClose={() => setProp(null)}>
          <Needs caps={["extraccion"]} />
          <div className="stack">
            <FieldRow label="Servicio del catálogo"><Select value={pf.service_id} onChange={(v) => setPf({ ...pf, service_id: v })} empty="Describir abajo" options={(services.data || []).map((s) => [s.id, s.title])} /></FieldRow>
            <FieldRow label="Servicio (texto libre)"><Text area rows={2} value={pf.service} onChange={(v) => setPf({ ...pf, service: v })} /></FieldRow>
            <FieldRow label="Precio (opcional; si lo dejas vacío queda «por definir»)"><Text value={pf.price} onChange={(v) => setPf({ ...pf, price: v })} /></FieldRow>
            <FieldRow label="Indicaciones"><Text area rows={2} value={pf.notes} onChange={(v) => setPf({ ...pf, notes: v })} /></FieldRow>
            <div className="row row--end"><Btn onClick={() => setProp(null)}>Cancelar</Btn><Btn kind="primary" onClick={async () => { await launch("lead_proposal", { lead_id: prop.id, ...pf }, `Propuesta: ${prop.title}`); setProp(null); setTab("buscar"); }}>Preparar borrador</Btn></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------- Fábrica de contenido

export function Content() {
  const launch = useLaunch();
  const [tab, setTab] = useState<"generar" | "briefs" | "lotes">("generar");
  const brands = useRecords("brand");
  const briefs = useRecords("brief");
  const [f, setF] = useState<Record<string, any>>({ objective: "confianza", count: 5, format: "vertical 9:16" });
  const set = (k: string) => (v: any) => setF((x) => ({ ...x, [k]: v }));
  const fromBrief = (id: string) => {
    const b = (briefs.data || []).find((x) => x.id === id);
    if (b) setF((x) => ({ ...x, brief_id: id, brand_id: b.brand_id || x.brand_id, project_id: b.project_id, ...Object.fromEntries(["objective", "channel", "audience", "product", "references", "facts", "count"].filter((k) => b.data[k]).map((k) => [k, b.data[k]])) }));
    else setF((x) => ({ ...x, brief_id: "" }));
  };
  return (
    <div className="page">
      <Head title="Fábrica de contenido" sub="Brief → ángulos → hooks → guiones → shot list → variantes. Cada lote usa solo la biblioteca de su marca y los hechos comprobados que aportes; lo no respaldado se marca «por verificar»." />
      <Tabs value={tab} onChange={setTab} tabs={[["generar", "Generar lote"], ["briefs", "Briefs"], ["lotes", "Lotes"]]} />
      {tab === "generar" && <>
        <Needs caps={["extraccion"]} />
        <div className="grid grid--side">
          <Panel title="Nuevo lote" note="Si no hay API de imagen o video, el lote es un paquete de producción con prompts utilizables, no videos terminados. Importa después los activos producidos en el Editor audiovisual.">
            <form className="form" onSubmit={(e) => { e.preventDefault(); launch("content_batch", { ...f, count: Number(f.count) }, `Contenido: ${f.objective}`); }}>
              <FieldRow label="Partir de un brief"><Select value={f.brief_id} onChange={fromBrief} empty="Sin brief" options={(briefs.data || []).map((b) => [b.id, b.title])} /></FieldRow>
              <FieldRow label="Marca" hint={!brands.data?.length ? "Registra una marca en Proyectos, marcas y biblioteca." : undefined}><Select value={f.brand_id} onChange={set("brand_id")} empty="Sin marca" options={(brands.data || []).map((b) => [b.id, b.title])} /></FieldRow>
              <FieldRow label="Objetivo"><Select value={f.objective} onChange={set("objective")} options={[["viralidad", "Viralidad"], ["confianza", "Confianza"], ["captacion", "Captación"], ["ventas", "Ventas"]]} /></FieldRow>
              <FieldRow label="Canal"><Text value={f.channel} onChange={set("channel")} placeholder="TikTok, Reels, YouTube Shorts…" /></FieldRow>
              <FieldRow label="Formato"><Text value={f.format} onChange={set("format")} /></FieldRow>
              <FieldRow label="Piezas (1–20)"><Text type="number" value={f.count} onChange={set("count")} /></FieldRow>
              <FieldRow label="Responsable"><Text value={f.owner} onChange={set("owner")} /></FieldRow>
              <FieldRow label="Producto u oferta" wide><Text area rows={2} value={f.product} onChange={set("product")} /></FieldRow>
              <FieldRow label="Audiencia" wide><Text area rows={2} value={f.audience} onChange={set("audience")} /></FieldRow>
              <FieldRow label="Hechos comprobados (uno por línea)" wide hint="Solo lo que puedas demostrar. Todo lo demás se marcará para verificar."><Text area rows={3} value={f.facts} onChange={set("facts")} /></FieldRow>
              <FieldRow label="Referencias de estilo" wide><Text area rows={2} value={f.references} onChange={set("references")} /></FieldRow>
              <FieldRow label="Recursos propios autorizados disponibles" wide><Text area rows={2} value={f.assets} onChange={set("assets")} placeholder="Qué material tienes: tomas, fotos, testimonios reales con permiso…" /></FieldRow>
              <div className="row row--end field--wide"><Btn kind="primary" type="submit">Generar lote</Btn></div>
            </form>
          </Panel>
          <Panel title="Lotes en curso"><JobList types={["content_batch"]} empty="Aún no has generado ningún lote." /></Panel>
        </div>
      </>}
      {tab === "briefs" && <RecordsPanel kind="brief" columns={["objective", "channel", "count"]} />}
      {tab === "lotes" && <Panel title="Lotes de contenido"><DeliverableList kind="content_batch" empty="Genera un lote para revisarlo, editarlo, aprobarlo y exportarlo." /></Panel>}
    </div>
  );
}

// ---------- Constructor Shopify

export function Shopify() {
  const { space, doneTick } = useApp();
  const launch = useLaunch();
  const files = useFiles();
  const [tab, setTab] = useState<"productos" | "paquetes">("productos");
  const [target, setTarget] = useState<Rec | null>(null);
  const [images, setImages] = useState<string[]>([]);
  const [theme, setTheme] = useState("");
  const [ai, setAi] = useState(true);
  const [preview, setPreview] = useState<FileRow | null>(null);
  const imgs = (files.data || []).filter((x) => (x.mime || "").startsWith("image/"));
  const zips = (files.data || []).filter((x) => x.name.endsWith(".zip") && x.origin === "upload");
  const previews = useData<FileRow[]>(async () => (await api<FileRow[]>("/files", { query: { space: space.id, origin: "job" } })).filter((x) => x.name.endsWith("-preview.html")), [space.id, doneTick]);
  return (
    <div className="page">
      <Head title="Constructor Shopify" sub="Genera una sección de página de producto autocontenida (Liquid + schema), su plantilla JSON, el contenido por campos y un ZIP con instrucciones. No es una tienda completa ni toca tu tema activo." />
      <Tabs value={tab} onChange={setTab} tabs={[["productos", "Productos"], ["paquetes", "Paquetes generados"]]} />
      {tab === "productos" && <>
        <RecordsPanel kind="product" columns={["price", "market", "theme_target"]} rowActions={(r) => <Btn small onClick={() => { setTarget(r); setImages([]); setTheme(""); }}>Generar paquete</Btn>}
          note="Prohibido por diseño: reseñas inventadas, urgencia o escasez falsas y resultados garantizados. Los beneficios sin respaldo en tus especificaciones se excluyen." />
        <Panel title="Paquetes en curso"><JobList types={["shopify_package"]} empty="Crea un producto y pulsa «Generar paquete»." /></Panel>
      </>}
      {tab === "paquetes" && <>
        <Panel title="Paquetes"><DeliverableList kind="shopify" empty="Aún no hay paquetes. Genera uno desde la pestaña Productos." /></Panel>
        <Panel title="Vista previa" note="Vista previa aproximada generada por Jarvis con el mismo CSS de la sección. No es el render de Shopify: pruébalo en un duplicado de tu tema.">
          <div className="row" style={{ marginBottom: 10 }}>
            {(previews.data || []).map((p) => <Btn small key={p.id} kind={preview?.id === p.id ? "primary" : "default"} onClick={() => setPreview(p)}>{p.name.replace("-preview.html", "")}</Btn>)}
            {!previews.data?.length && <span className="muted small">Sin vistas previas todavía.</span>}
          </div>
          {preview && <iframe className="iframe" sandbox="" title="Vista previa del paquete" src={url(`/files/${preview.id}/preview`, { space: space.id })} />}
        </Panel>
      </>}
      {target && (
        <Modal title={`Generar paquete: ${target.title}`} onClose={() => setTarget(null)}>
          <Needs caps={[]} optional={["extraccion"]} />
          <div className="stack">
            <FieldRow group label="Imágenes del producto (con derechos de uso)">
              <div className="stack">
                {imgs.map((d) => <Check key={d.id} checked={images.includes(d.id)} onChange={(v) => setImages((p) => (v ? [...p, d.id] : p.filter((x) => x !== d.id)))}>{d.name}</Check>)}
                <div><UploadButton accept="image/png,image/jpeg,image/webp" multiple onDone={(row) => { files.reload(); setImages((p) => [...p, row.id]); }}>Subir imagen</UploadButton></div>
              </div>
            </FieldRow>
            <FieldRow group label="Tema objetivo (ZIP exportado de Shopify, opcional)" hint="Solo se lee para informar de compatibilidad. Nunca se modifica.">
              <div className="row"><div style={{ flex: 1 }}><Select value={theme} onChange={setTheme} empty="Sin tema adjunto" options={zips.map((z) => [z.id, z.name])} /></div><UploadButton accept=".zip" onDone={(row) => { files.reload(); setTheme(row.id); }}>Subir ZIP</UploadButton></div>
            </FieldRow>
            <Check checked={ai} onChange={setAi}>Redactar el copy con el modelo de texto si está disponible (si no, se usan solo tus campos)</Check>
            <div className="row row--end"><Btn onClick={() => setTarget(null)}>Cancelar</Btn>
              <Btn kind="primary" onClick={async () => { await launch("shopify_package", { product_id: target.id, image_file_ids: images, theme_file_id: theme || null, use_ai: ai }, `Paquete Shopify: ${target.title}`); setTarget(null); }}>Generar</Btn></div>
          </div>
        </Modal>
      )}
    </div>
  );
}

// ---------- Clipping

export function Clipping() {
  const { space, boot, run, reload, doneTick } = useApp();
  const launch = useLaunch();
  const [tab, setTab] = useState<"comparador" | "campanas" | "clips">("comparador");
  const [importUrl, setImportUrl] = useState("");
  const [tick, setTick] = useState(0);
  const minCpm = boot.settings.min_cpm ?? "";
  const s = useData<any>(() => api("/clipping/summary", { query: { space: space.id, min_cpm: minCpm } }), [space.id, minCpm, doneTick, tick]);
  const t = s.data?.totales;
  return (
    <div className="page">
      <Head title="Clipping" sub="Compara campañas y registra por separado vistas totales, vistas elegibles, ingreso estimado, aprobado y cobrado. Los datos se actualizan manualmente: no hay conector automático con plataformas de campañas." />
      <Tabs value={tab} onChange={setTab} tabs={[["comparador", "Comparador y alertas"], ["campanas", "Campañas"], ["clips", "Clips publicados"]]} />
      {tab === "comparador" && <>
        <Panel title="Estados del dinero (no se suman entre sí)" note={s.data?.nota}>
          {t && <div className="stats">
            <Stat label="Vistas totales" value={fmtNum(t.vistas_totales, 0)} hint="No generan ingreso por sí solas" />
            <Stat label="Vistas elegibles" value={fmtNum(t.vistas_elegibles, 0)} hint="Informadas por ti" />
            <Stat label="Ingreso estimado" value={`${fmtNum(t.ingreso_estimado_usd)} USD`} hint="Elegibles × CPM; sin confirmar" />
            <Stat label="Aprobado" value={`${fmtNum(t.aprobado_usd)} USD`} hint="Confirmado por el organizador" />
            <Stat label="Cobrado" value={`${fmtNum(t.cobrado_usd)} USD`} tone="ok" hint="Recibido" />
          </div>}
        </Panel>
        <Panel title="Comparador de campañas" actions={<div className="row"><span className="small muted">Preferencia de CPM mínimo</span>
          <div style={{ width: 150 }}><Select value={String(minCpm)} onChange={async (v) => { await run(api("/settings", { method: "PATCH", body: { min_cpm: v ? Number(v) : null } })); reload(); }} options={[["", "Sin preferencia"], ["1", "≥ 1,00 USD"], ["1.5", "≥ 1,50 USD"], ["2", "≥ 2,00 USD"]]} /></div></div>}
          note="La preferencia de CPM solo ordena y marca; un CPM alto no garantiza ingresos.">
          {!s.data?.campanas.length ? <p className="muted">Registra campañas en la pestaña Campañas para compararlas.</p> : (
            <div className="tablewrap"><table>
              <thead><tr><th>Campaña</th><th className="num">CPM</th><th className="num">Presupuesto</th><th>Plataformas</th><th>Fin</th><th className="num">Elegibles</th><th className="num">Estimado</th><th className="num">Aprobado</th><th className="num">Cobrado</th><th>Fuente</th></tr></thead>
              <tbody>{s.data.campanas.map((c: any) => (
                <tr key={c.id}>
                  <td className="wrap">{c.titulo} <Badge value={c.estado} />{c.alertas.length > 0 && <div className="small amber">{c.alertas.length} alerta(s)</div>}</td>
                  <td className="num">{c.cpm_usd === null || c.cpm_usd === undefined ? <span className="amber">falta</span> : fmtNum(c.cpm_usd)} {c.cumple_cpm === true && <Badge value="ok" text="cumple" />}{c.cumple_cpm === false && <Badge value="mute" text="bajo" />}</td>
                  <td className="num">{fmtNum(c.presupuesto_usd, 0)}</td><td className="small">{c.plataformas.join(", ") || "—"}</td><td className="small">{c.fin || "—"}</td>
                  <td className="num">{c.vistas_elegibles === null ? "sin datos" : fmtNum(c.vistas_elegibles, 0)}</td><td className="num">{c.ingreso_estimado_usd === null ? "—" : fmtNum(c.ingreso_estimado_usd)}</td>
                  <td className="num">{fmtNum(c.aprobado_usd)}</td><td className="num">{fmtNum(c.cobrado_usd)}</td>
                  <td className="small">{c.fuente ? <a href={c.fuente} target="_blank" rel="noreferrer noopener">ver</a> : "—"} {c.fecha_fuente || ""}</td>
                </tr>
              ))}</tbody>
            </table></div>
          )}
        </Panel>
        <Panel title={`Alertas (${s.data?.alertas.length || 0})`}>
          {!s.data?.alertas.length ? <p className="muted small">Sin alertas.</p> : s.data.alertas.map((a: any, i: number) => (
            <div key={i} className="check-row" style={{ gridTemplateColumns: "190px 1fr" }}><Badge value="warn" text={label(a.tipo)} /><div className="wrap"><strong>{a.campana}</strong>: {a.texto}</div></div>
          ))}
        </Panel>
      </>}
      {tab === "campanas" && <>
        <Panel title="Importar campaña desde una URL accesible" note="La página se lee una sola vez. Con modelo de texto se extraen los campos (CPM y presupuesto solo si su cita aparece en la página); sin él se guarda la fuente y completas los campos a mano.">
          <form className="row" onSubmit={(e) => { e.preventDefault(); launch("clipping_import_url", { url: importUrl }, "Importar campaña"); setImportUrl(""); }}>
            <div style={{ flex: 1, minWidth: 220 }}><Text value={importUrl} onChange={setImportUrl} placeholder="https://…" /></div><Btn type="submit" disabled={!importUrl.trim()}>Importar</Btn>
          </form>
          <JobList types={["clipping_import_url"]} limit={3} empty=" " />
        </Panel>
        <RecordsPanel kind="campaign" columns={["organizer", "cpm_usd", "budget_usd", "end_date"]} importable onChanged={() => setTick((n) => n + 1)} />
      </>}
      {tab === "clips" && <RecordsPanel kind="clip" columns={["campaign_id", "views_total", "views_eligible", "approved_usd", "paid_usd", "review_status"]} importable onChanged={() => setTick((n) => n + 1)}
        note="El ingreso estimado se calcula solo con vistas elegibles. «Aprobado» y «cobrado» son importes que introduces tú según lo que confirme y pague el organizador." />}
    </div>
  );
}
