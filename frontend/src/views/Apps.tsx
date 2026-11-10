import { useState } from "react";
import { api } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, Empty, FieldRow, Modal, Panel, Select, Skeleton, Tabs, Text, useConfirm } from "../components/ui";

type Conn = Record<string, any>;
const varsOf = (a: any): string[] => Array.from(new Set((JSON.stringify([a.path, a.query, a.body]).match(/\{([a-z_][a-z0-9_]*)\}/g) || []).map((x) => x.slice(1, -1))));

function AppForm({ preset, id, conn, onClose }: { preset?: any; id?: string; conn?: Conn; onClose: () => void }) {
  const { run, notify } = useApp();
  const base = conn || { name: preset.label, base_url: preset.base_url, options: { preset: id, auth: preset.auth, actions: preset.actions, headers: preset.headers || {}, client_id: "" }, enabled: true, terms_accepted: false };
  const [f, setF] = useState<Conn>({ ...base, secret: "" });
  const [def, setDef] = useState(JSON.stringify(base.options.actions, null, 2));
  const [adv, setAdv] = useState(false);
  const oauth = f.options.auth?.type === "oauth";
  const save = async () => {
    let actions;
    try { actions = JSON.parse(def); } catch { notify("La definición de acciones no es JSON válido.", "error"); return; }
    const body: Conn = { name: f.name, base_url: f.base_url, enabled: f.enabled, terms_accepted: f.terms_accepted, options: { ...f.options, actions } };
    if (f.secret) body.secret = f.secret;
    const out = await run(conn ? api(`/connections/${conn.id}`, { method: "PATCH", body }) : api("/connections", { body: { ...body, provider: "api" } }), "App guardada");
    if (out) onClose();
  };
  return (
    <Modal title={conn ? `Editar ${conn.name}` : `Conectar ${preset.label}`} onClose={onClose} wide>
      <div className="form">
        <FieldRow label="Nombre"><Text value={f.name} onChange={(v) => setF({ ...f, name: v })} /></FieldRow>
        <FieldRow label="URL base de la API" hint="Sustituye las partes en mayúsculas (TU-TIENDA, TU-SITIO) por las tuyas."><Text value={f.base_url} onChange={(v) => setF({ ...f, base_url: v })} /></FieldRow>
        <FieldRow label="Autenticación"><Select value={f.options.auth?.type} onChange={(v) => setF({ ...f, options: { ...f.options, auth: { ...f.options.auth, type: v } } })}
          options={[["bearer", "Token (Authorization: Bearer)"], ["header", "Clave en una cabecera"], ["query", "Clave en la URL"], ["basic", "Usuario:contraseña (Basic)"], ["oauth", "OAuth 2.0"], ["none", "Ninguna"]]} /></FieldRow>
        {["header", "query"].includes(f.options.auth?.type) && <FieldRow label="Nombre de la cabecera o parámetro"><Text value={f.options.auth?.name} onChange={(v) => setF({ ...f, options: { ...f.options, auth: { ...f.options.auth, name: v } } })} /></FieldRow>}
        {oauth && <FieldRow label="Client ID" hint={`Registra en tu proveedor esta URL de redirección: http://127.0.0.1:${location.port || 8765}/api/oauth/callback`}><Text value={f.options.client_id} onChange={(v) => setF({ ...f, options: { ...f.options, client_id: v } })} /></FieldRow>}
        {f.options.auth?.type !== "none" && <FieldRow label={oauth ? "Client secret" : "Credencial"} wide hint={(conn?.has_secret ? "Guardada; escribe solo para sustituirla. " : "") + (preset?.credential || "Se guarda en el almacén de credenciales, nunca en la base de datos.")}>
          <input className="input" type="password" autoComplete="new-password" value={f.secret} onChange={(e) => setF({ ...f, secret: e.target.value })} placeholder={conn?.has_secret ? "•••••••• (sin cambios)" : ""} /></FieldRow>}
        <FieldRow group label="Activación" wide><div className="stack">
          <Check checked={!!f.enabled} onChange={(v) => setF({ ...f, enabled: v })}>Habilitada</Check>
          <Check checked={!!f.terms_accepted} onChange={(v) => setF({ ...f, terms_accepted: v })}>He revisado las condiciones de este servicio y acepto enviarle las peticiones que yo ejecute o apruebe</Check>
        </div></FieldRow>
        <div className="field--wide"><Btn small kind="ghost" onClick={() => setAdv(!adv)}>{adv ? "Ocultar" : "Editar"} acciones (avanzado)</Btn></div>
        {adv && <FieldRow label="Acciones (JSON)" wide hint="Cada acción: id, label, method, path (relativa a la URL base, con {variables}), query, body y write. Todo lo que no sea GET se trata como escritura salvo que pongas write: false.">
          <Text area rows={12} value={def} onChange={setDef} /></FieldRow>}
      </div>
      <p className="note">Las acciones de lectura se ejecutan al momento. Las de escritura crean un trabajo que espera tu aprobación con la petición exacta. Plantilla según la documentación pública del servicio: no se ha comprobado con una cuenta real.</p>
      <div className="row row--end"><Btn onClick={onClose}>Cancelar</Btn><Btn kind="primary" onClick={save}>Guardar</Btn></div>
    </Modal>
  );
}

function AppCard({ c, onChanged }: { c: Conn; onChanged: () => void }) {
  const { space, run, notify, refreshJobs } = useApp();
  const [vars, setVars] = useState<Record<string, string>>({});
  const [action, setAction] = useState<string>(c.options.actions?.[0]?.id || "");
  const [result, setResult] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  const [edit, setEdit] = useState(false);
  const [confirm, node] = useConfirm();
  const a = (c.options.actions || []).find((x: any) => x.id === action);
  const go = async () => {
    setBusy(true); setResult(null);
    if (a.write) {
      const r: any = await run(api(`/apps/${c.id}/request`, { body: { space: space.id, action, variables: vars } }));
      if (r) { notify(`Solicitud creada (${r.job.id}). Revísala y apruébala en «Pendientes de aprobación».`, "info"); refreshJobs(); onChanged(); }
    } else {
      const r = await run(api(`/apps/${c.id}/run`, { body: { action, variables: vars } }));
      if (r) setResult(r);
    }
    setBusy(false);
  };
  const authorize = async () => { const r: any = await run(api("/oauth/start", { body: { connection_id: c.id } })); if (r) window.open(r.url, "_blank", "noopener"); };
  return (
    <Panel title={c.name} actions={<><Badge value={c.status} text={c.status_label} />
      {c.options.auth?.type === "oauth" && <Btn small kind="amber" onClick={authorize}>Autorizar</Btn>}
      <Btn small onClick={async () => { const t: any = await run(api(`/connections/${c.id}/test`, { method: "POST" })); if (t) notify(`${c.name}: ${t.detail}`, t.ok ? "ok" : "error"); onChanged(); }}>Probar</Btn>
      <Btn small onClick={() => setEdit(true)}>Editar</Btn>
      <Btn small kind="ghost" onClick={() => confirm(`¿Desconectar «${c.name}» y borrar su credencial?`, async () => { await run(api(`/connections/${c.id}`, { method: "DELETE" }), "App desconectada"); onChanged(); }, true)}>Quitar</Btn></>}>
      <p className="small muted wrap">{c.base_url}{c.last_error && c.status !== "operativa" ? <span className="amber"> · {c.last_error}</span> : ""}</p>
      {!c.options.actions?.length ? <p className="muted small">Sin acciones definidas. Pulsa Editar → acciones para añadir la primera.</p> : (
        <div className="form" style={{ marginTop: 12 }}>
          <FieldRow label="Acción"><Select value={action} onChange={(v) => { setAction(v); setResult(null); }} options={c.options.actions.map((x: any) => [x.id, `${x.label}${x.write ? " · escritura" : ""}`])} /></FieldRow>
          {a && varsOf(a).map((v) => <FieldRow key={v} label={v.replace(/_/g, " ")}><Text value={vars[v]} onChange={(x) => setVars({ ...vars, [v]: x })} placeholder={v === "limite" ? "20" : ""} /></FieldRow>)}
          <div className="row" style={{ alignSelf: "end" }}><Btn kind={a?.write ? "amber" : "primary"} busy={busy} onClick={go}>{a?.write ? "Solicitar (requiere aprobación)" : "Ejecutar"}</Btn>
            {a && <span className="small mono">{a.method} {a.path}</span>}</div>
        </div>
      )}
      {result && <><p className="small muted" style={{ marginTop: 10 }}>HTTP {result.status} · {result.request.method} {result.request.url}{result.truncated ? " · respuesta recortada" : ""}</p>
        <pre className="diff" style={{ maxHeight: 320, overflowY: "auto" }}>{result.json !== null ? JSON.stringify(result.json, null, 2) : result.text}</pre></>}
      {edit && <AppForm conn={c} onClose={() => { setEdit(false); onChanged(); }} />}
      {node}
    </Panel>
  );
}

function Pending({ id, onDone }: { id: string; onDone: () => void }) {
  const { run, refreshJobs } = useApp();
  const p = useData<any>(() => api(`/apps/pending/${id}`), [id]);
  if (!p.data) return <Skeleton />;
  const r = p.data.preview;
  return (
    <div className="jobrow">
      <div className="jobrow__top"><strong className="wrap">{p.data.job.title}</strong><Badge value="warn" text="Espera tu aprobación" /></div>
      <pre className="diff">{r.method} {r.url}{Object.keys(r.query || {}).length ? `\n? ${JSON.stringify(r.query)}` : ""}{r.body ? `\n${JSON.stringify(r.body, null, 2)}` : ""}</pre>
      <div className="row"><Btn kind="amber" onClick={async () => { await run(api(`/apps/pending/${id}/approve`, { body: { expires_hours: 1 } }), "Aprobada: se ejecuta una sola vez"); refreshJobs(); onDone(); }}>Aprobar esta petición exacta</Btn>
        <Btn kind="ghost" onClick={async () => { await run(api(`/jobs/${id}/cancel`, { method: "POST" }), "Solicitud cancelada"); refreshJobs(); onDone(); }}>Rechazar</Btn></div>
    </div>
  );
}

export function Apps() {
  const { boot, jobs, run, nav, doneTick } = useApp();
  const [tab, setTab] = useState<"mis" | "catalogo" | "externos">("mis");
  const [tick, setTick] = useState(0);
  const [adding, setAdding] = useState<string | null>(null);
  const [token, setToken] = useState("");
  const conns = useData<Conn[]>(async () => (await api<Conn[]>("/connections")).filter((c) => c.provider === "api"), [tick, doneTick]);
  const pending = jobs.filter((j) => j.type === "connector_action" && j.status === "waiting_approval");
  const bump = () => setTick((n) => n + 1);
  const presets = boot.connector_presets || {};
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">Apps conectadas</h1>
        <p className="page__sub">Conecta cualquier servicio que tenga API: tienda, pagos, anuncios, redes, documentos o tus propias herramientas. Leer es inmediato; escribir en un sistema externo siempre pasa por tu aprobación, con la petición exacta a la vista.</p></div>
        <Btn onClick={() => nav("biblioteca/conexiones/" + encodeURIComponent("Conectar cualquier app.md"))}>Guía</Btn></div>
      <Tabs value={tab} onChange={setTab} tabs={[["mis", `Mis apps${conns.data?.length ? ` (${conns.data.length})` : ""}`], ["catalogo", "Catálogo"], ["externos", "Conectar otros programas a Jarvis"]]} />
      {tab === "mis" && <>
        {pending.length > 0 && <Panel title={`Pendientes de aprobación (${pending.length})`}>{pending.map((j) => <Pending key={j.id} id={j.id} onDone={bump} />)}</Panel>}
        {!conns.data ? <Skeleton /> : !conns.data.length ? <Empty title="Aún no has conectado ninguna app" action={<Btn kind="primary" onClick={() => setTab("catalogo")}>Ver el catálogo</Btn>}>
          Elige una plantilla (Shopify, Stripe, Notion, Meta, YouTube, Google Drive…) o define una API personalizada. Para Claude, ChatGPT y demás modelos de IA usa Conexiones.</Empty>
          : conns.data.map((c) => <AppCard key={c.id} c={c} onChanged={bump} />)}
      </>}
      {tab === "catalogo" && <div className="grid grid--3">
        {Object.entries(presets).map(([id, p]: any) => (
          <Panel key={id} title={p.label} actions={<Btn small kind="primary" onClick={() => setAdding(id)}>Conectar</Btn>}>
            <p className="small muted wrap">{p.actions.length ? p.actions.map((a: any) => a.label).join(" · ") : "Define tus propias acciones."}</p>
            <p className="small" style={{ marginTop: 8 }}>{p.usa_oauth ? <Badge value="info" text="OAuth 2.0" /> : <Badge value="mute" text="Clave o token" />} {p.actions.some((a: any) => a.write) && <Badge value="warn" text="Incluye escritura con aprobación" />}</p>
          </Panel>
        ))}
      </div>}
      {tab === "externos" && <>
        <Panel title="Claude, ChatGPT y otros asistentes (MCP)" note="El servidor MCP expone solo las herramientas internas de Jarvis sobre un espacio de negocio: consultar, lanzar trabajos, anotar y pausar agentes. Nunca tus espacios personales, ni acciones externas.">
          <p>Con este servidor, un cliente MCP como Claude Desktop puede usar Jarvis como herramienta: «busca oportunidades en…», «¿qué tengo pendiente?». Añade esto a la configuración de servidores MCP de tu cliente, cambiando la ruta por la carpeta donde instalaste Jarvis:</p>
          <pre className="diff">{`{
  "mcpServers": {
    "jarvis": {
      "command": "C:\\\\RUTA\\\\A\\\\jarvis\\\\.venv\\\\Scripts\\\\python.exe",
      "args": ["-m", "jarvis.mcp_server"],
      "cwd": "C:\\\\RUTA\\\\A\\\\jarvis\\\\backend"
    }
  }
}`}</pre>
        </Panel>
        <Panel title="Cualquier programa: n8n, Make, atajos del celular, scripts" note="El token solo permite enviar órdenes a Jarvis (las mismas que escribes en Comando). Generar uno nuevo invalida el anterior.">
          <div className="row"><Btn kind="primary" onClick={async () => { const r: any = await run(api("/token", { method: "POST" })); if (r) setToken(r.token); }}>Generar token de API</Btn></div>
          {token && <><p className="note note--amber">Cópialo ahora: no volverá a mostrarse.</p><pre className="diff">{token}</pre></>}
          <pre className="diff">{`curl -X POST http://127.0.0.1:${location.port || 8765}/api/ext/command \\
  -H "Authorization: Bearer TU_TOKEN" -H "Content-Type: application/json" \\
  -d '{"text": "tarea: revisar pedidos de hoy"}'`}</pre>
        </Panel>
      </>}
      {adding && <AppForm id={adding} preset={presets[adding]} onClose={() => { setAdding(null); bump(); setTab("mis"); }} />}
    </div>
  );
}
