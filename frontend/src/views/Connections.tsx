import { useState } from "react";
import { api, ApiError, fmtDate } from "../api";
import { useApp, useData } from "../store";
import { Badge, Btn, Check, Empty, FieldRow, Modal, Panel, Select, Skeleton, Text, useConfirm } from "../components/ui";

type Conn = Record<string, any>;
type Meta = { providers: Record<string, any>; capabilities: Record<string, string> };

/** Formulario de conexión. No depende del contexto de la app para poder usarse también en el primer inicio. */
export function ConnectionForm({ meta, conn, onClose, onSaved, notify, only }: { meta: Meta; conn?: Conn; onClose: () => void; onSaved: (c: Conn) => void; notify: (t: string, k?: "ok" | "error" | "info") => void; only?: string[] }) {
  const [provider, setProvider] = useState<string>(conn?.provider || (only?.[0] ?? "ollama"));
  const spec = meta.providers[provider];
  const [f, setF] = useState<Conn>(conn ? { ...conn, secret: "" } : { name: "", base_url: "", model: "", capabilities: null, enabled: true, terms_accepted: false, is_paid: false, timeout_s: 60, max_tokens: 2048, concurrency: 1, data_policy: "negocio", options: {} });
  const [models, setModels] = useState<any[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [saved, setSaved] = useState<Conn | undefined>(conn);
  const [result, setResult] = useState<{ ok: boolean; detail: string } | null>(null);
  const set = (k: string) => (v: any) => setF((x) => ({ ...x, [k]: v }));
  const opt = (k: string) => (v: any) => setF((x) => ({ ...x, options: { ...(x.options || {}), [k]: v } }));
  const caps: string[] = f.capabilities || spec.capabilities;
  const allCaps: string[] = [...spec.capabilities, ...spec.optional];
  const local = spec.local;
  const guard = async <T,>(p: Promise<T>): Promise<T | undefined> => { try { return await p; } catch (e) { notify(e instanceof ApiError ? e.message : "Error inesperado", "error"); return undefined; } };

  const persist = async (): Promise<Conn | undefined> => {
    const body: Conn = { ...f, provider, capabilities: caps, base_url: f.base_url || spec.base_url };
    for (const k of ["status", "status_label", "has_secret", "secret_hint", "is_local", "provider_label", "id", "created_at", "updated_at", "last_error", "last_checked_at", "confirmed_quota", "blocked_until"]) delete body[k];
    if (!body.secret) delete body.secret;
    const out = await guard(saved ? api<Conn>(`/connections/${saved.id}`, { method: "PATCH", body }) : api<Conn>("/connections", { body }));
    if (out) { setSaved(out); setF((x) => ({ ...x, secret: "" })); }
    return out;
  };
  const save = async (thenTest: boolean) => {
    setBusy(true);
    setResult(null);
    const out = await persist();
    if (out && thenTest) {
      const t = await guard(api<any>(`/connections/${out.id}/test`, { method: "POST" }));
      if (t) { setResult({ ok: t.ok, detail: t.detail }); setSaved(t.connection); if (t.ok) notify("Conexión comprobada", "ok"); }
    } else if (out) { notify("Conexión guardada", "ok"); onSaved(out); }
    setBusy(false);
  };
  const listModels = async () => {
    setBusy(true);
    const out = await persist();
    if (out) { const r = await guard(api<{ items: any[] }>(`/connections/${out.id}/models`)); if (r) { setModels(r.items); if (!r.items.length) notify("El proveedor no devolvió ningún modelo para esta credencial.", "info"); } }
    setBusy(false);
  };
  const isLlm = ["ollama", "gemini", "groq", "openai_compat"].includes(provider);

  return (
    <Modal title={conn ? `Editar conexión: ${conn.name}` : "Nueva conexión"} onClose={() => (saved ? onSaved(saved) : onClose())} wide>
      <div className="form">
        <FieldRow label="Proveedor" hint={spec.help}>
          <Select value={provider} onChange={(v) => { setProvider(v); setModels(null); setF((x) => ({ ...x, capabilities: null, base_url: "", model: "" })); }} options={Object.entries(meta.providers).filter(([k]) => !only || only.includes(k)).map(([k, v]: any) => [k, v.label])} />
        </FieldRow>
        <FieldRow label="Nombre"><Text value={f.name} onChange={set("name")} placeholder={spec.label} /></FieldRow>
        {provider !== "whisper_local" && <FieldRow label="URL" hint={spec.base_url ? `Por defecto: ${spec.base_url}` : "Obligatoria"} wide><Text value={f.base_url} onChange={set("base_url")} placeholder={spec.base_url || "https://…"} /></FieldRow>}
        {spec.needs_secret && <FieldRow label="Credencial" wide hint={saved?.has_secret ? `Guardada (${saved.secret_hint}). Escribe solo para sustituirla; nunca se muestra completa.` : "Se guarda del lado servidor; no vuelve a mostrarse."}>
          <input className="input" type="password" autoComplete="new-password" value={f.secret || ""} placeholder={saved?.has_secret ? "•••••••• (sin cambios)" : "Pega aquí la clave de API"} onChange={(e) => set("secret")(e.target.value)} />
        </FieldRow>}
        {isLlm && <FieldRow group label="Modelo" wide hint="No se fija ningún modelo por defecto: elige uno del listado real de tu cuenta.">
          <div className="row">
            <div style={{ flex: 1, minWidth: 180 }}>{models?.length ? <Select value={f.model} onChange={set("model")} empty="Elige un modelo" options={models.map((m) => [m, m])} /> : <input className="input" aria-label="Modelo" value={f.model ?? ""} placeholder="ID del modelo" onChange={(e) => set("model")(e.target.value)} autoComplete="off" />}</div>
            <Btn onClick={listModels} busy={busy}>Listar modelos disponibles</Btn>
          </div>
        </FieldRow>}
        {provider === "whisper_local" && <FieldRow label="Modelo local" hint="tiny, base, small, medium…"><Text value={f.model} onChange={set("model")} placeholder="base" /></FieldRow>}
        {provider === "elevenlabs" && <>
          <FieldRow group label="Voice ID autorizado" hint="Usa solo voces que tengas derecho a utilizar. No se clonan voces de terceros.">
            <div className="row"><div style={{ flex: 1 }}>{models?.length ? <Select value={f.options?.voice_id} onChange={opt("voice_id")} empty="Elige una voz" options={models.map((m: any) => [m.id, `${m.name}${m.category ? ` (${m.category})` : ""}`])} /> : <Text value={f.options?.voice_id} onChange={opt("voice_id")} />}</div><Btn onClick={listModels} busy={busy}>Listar voces</Btn></div>
          </FieldRow>
          <FieldRow label="Modelo de voz (opcional)"><Text value={f.model} onChange={set("model")} placeholder="Predeterminado del proveedor" /></FieldRow>
        </>}
        <FieldRow group label="Capacidades" wide hint="Marca solo las que este proveedor y modelo soporten de verdad.">
          <div className="row">{allCaps.map((c) => <Check key={c} checked={caps.includes(c)} onChange={(v) => set("capabilities")(v ? [...caps, c] : caps.filter((x) => x !== c))}>{meta.capabilities[c] || c}</Check>)}</div>
        </FieldRow>
        {caps.includes("transcripcion") && provider !== "whisper_local" && <FieldRow label="Modelo de transcripción" hint="ID exacto del modelo de audio en tu cuenta."><Text value={f.options?.transcription_model} onChange={opt("transcription_model")} /></FieldRow>}
        {provider !== "webhook" && <>
          <FieldRow label="Tiempo máximo (s)"><Text type="number" value={f.timeout_s} onChange={set("timeout_s")} /></FieldRow>
          {isLlm && <FieldRow label="Máximo de tokens de salida"><Text type="number" value={f.max_tokens} onChange={set("max_tokens")} /></FieldRow>}
          <FieldRow label="Concurrencia"><Text type="number" value={f.concurrency} onChange={set("concurrency")} /></FieldRow>
          <FieldRow label="Límite por minuto (configurado)" hint="Tu propio tope; no es la cuota confirmada del proveedor."><Text type="number" value={f.rpm_limit} onChange={set("rpm_limit")} /></FieldRow>
          <FieldRow label="Límite diario (configurado)"><Text type="number" value={f.daily_limit} onChange={set("daily_limit")} /></FieldRow>
        </>}
        {!local && provider !== "webhook" && <FieldRow label="Política de datos">
          <Select value={f.data_policy} onChange={set("data_policy")} options={[["negocio", "Solo datos de negocio"], ["todo", "También datos de espacios personales"]]} />
        </FieldRow>}
        {!local && provider !== "webhook" && <FieldRow group label="Costo" wide>
          <div className="stack">
            <Check checked={!!f.is_paid} onChange={set("is_paid")}>Esta conexión factura por uso (de pago)</Check>
            {f.is_paid && <div className="form">
              {isLlm ? <><FieldRow label="Precio entrada (USD por millón de tokens)"><Text type="number" value={f.price_in} onChange={set("price_in")} /></FieldRow>
                <FieldRow label="Precio salida (USD por millón de tokens)"><Text type="number" value={f.price_out} onChange={set("price_out")} /></FieldRow></>
                : <FieldRow label={provider === "elevenlabs" ? "Precio por carácter (USD)" : "Precio por consulta o minuto (USD)"}><Text type="number" value={f.price_unit} onChange={set("price_unit")} /></FieldRow>}
              <FieldRow label="Presupuesto mensual (USD)" hint="Obligatorio para usar una conexión de pago."><Text type="number" value={f.monthly_budget_usd} onChange={set("monthly_budget_usd")} /></FieldRow>
            </div>}
            <span className="field__hint">Los precios los introduces tú según la tarifa vigente de tu proveedor; Jarvis no los conoce ni puede verificar tu facturación. Una suscripción de chat no equivale a acceso por API.</span>
          </div>
        </FieldRow>}
        <FieldRow group label="Activación" wide>
          <div className="stack">
            <Check checked={!!f.enabled} onChange={set("enabled")}>Habilitada</Check>
            {!local && <Check checked={!!f.terms_accepted} onChange={set("terms_accepted")}>He revisado y acepto las condiciones de uso y la política de datos de este proveedor para los datos que le enviaré</Check>}
          </div>
        </FieldRow>
      </div>
      {result && <p className={`note${result.ok ? "" : " note--amber"}`} role="status"><strong>{result.ok ? "Prueba correcta." : "La prueba falló."}</strong> {result.detail}</p>}
      <div className="row row--end">
        <Btn onClick={() => (saved ? onSaved(saved) : onClose())}>Cerrar</Btn>
        <Btn onClick={() => save(false)} busy={busy}>Guardar</Btn>
        <Btn kind="primary" onClick={() => save(true)} busy={busy}>Guardar y probar conexión</Btn>
      </div>
    </Modal>
  );
}

export function Connections() {
  const { boot, space, run, notify, reload, doneTick } = useApp();
  const [tick, setTick] = useState(0);
  const list = useData<Conn[]>(() => api("/connections"), [tick]);
  const avail = useData<Record<string, any>>(() => api("/availability", { query: { space: space.id } }), [space.id, tick, doneTick]);
  const [editing, setEditing] = useState<Conn | "new" | null>(null);
  const [testing, setTesting] = useState("");
  const [confirm, confirmNode] = useConfirm();
  const bump = () => setTick((n) => n + 1);
  const paid = !!boot.settings.allow_paid;
  const test = async (c: Conn) => {
    setTesting(c.id);
    const t: any = await run(api(`/connections/${c.id}/test`, { method: "POST" }));
    if (t) notify(`${c.name}: ${t.ok ? "prueba correcta" : "prueba fallida"}. ${t.detail}`, t.ok ? "ok" : "error");
    setTesting("");
    bump();
  };
  const setPaid = (v: boolean) => {
    const apply = async () => { await run(api("/settings", { method: "PATCH", body: { allow_paid: v } }), v ? "Gasto de pago activado" : "Gasto de pago desactivado"); reload(); bump(); };
    if (v) confirm("Vas a permitir el uso de conexiones de pago dentro del presupuesto mensual que definas en cada una. Jarvis reserva una estimación antes de cada llamada, pero la factura real la emite el proveedor. ¿Activar?", apply);
    else apply();
  };
  return (
    <div className="page">
      <div className="page__head"><div><h1 className="page__title">Conexiones</h1>
        <p className="page__sub">Política FREE / LOCAL FIRST: primero proveedores locales, después nube sin costo declarado y, solo si lo activas, de pago con presupuesto. Jarvis nunca cambia a pago por su cuenta ni rota cuentas para evadir límites.</p></div>
        <Btn kind="primary" onClick={() => setEditing("new")}>Nueva conexión</Btn></div>
      {!boot.secrets_backend.protected && <div className="banner"><span><strong>Almacén de credenciales:</strong> {boot.secrets_backend.label}. Las claves quedan fuera de la carpeta de datos y de los respaldos, pero sin cifrado del sistema.</span></div>}
      <div className="grid grid--side">
        <Panel title="Conexiones configuradas">
          {!list.data ? <Skeleton /> : !list.data.length ? (
            <Empty title="Aún no hay conexiones" action={<Btn kind="primary" onClick={() => setEditing("new")}>Añadir la primera</Btn>}>
              Sin conexiones funcionan proyectos, archivos, tareas, revisión manual, importación/exportación, video con FFmpeg y los comandos directos de Jarvis. Para investigar o redactar con IA, añade Ollama (local) o un proveedor en la nube.
            </Empty>
          ) : list.data.map((c) => (
            <div key={c.id} className="jobrow">
              <div className="jobrow__top"><strong className="wrap">{c.name}</strong><Badge value={c.status} text={c.status_label} /></div>
              <div className="small muted wrap">{c.provider_label}{c.model ? ` · ${c.model}` : ""} · {c.capabilities.map((x: string) => boot.capabilities[x] || x).join(", ")} · {c.is_local ? "local" : c.is_paid ? `de pago (presupuesto ${c.monthly_budget_usd ?? "sin definir"} USD/mes)` : "nube, sin costo declarado"}</div>
              {c.last_error && c.status !== "operativa" && <div className="small amber wrap">Último error: {c.last_error}</div>}
              <div className="small muted wrap">
                Cuota configurada: {c.rpm_limit || c.daily_limit ? [c.rpm_limit && `${c.rpm_limit}/min`, c.daily_limit && `${c.daily_limit}/día`].filter(Boolean).join(", ") : "ninguna"} ·
                {" "}Cuota confirmada por el proveedor: {Object.keys(c.confirmed_quota || {}).length > 1 ? Object.entries(c.confirmed_quota).filter(([k]) => k !== "_observado").slice(0, 3).map(([k, v]) => `${k.replace("x-ratelimit-", "")}=${v}`).join(", ") + ` (observada ${fmtDate(c.confirmed_quota._observado)})` : "no observada"}
                {c.last_checked_at && <> · Última comprobación {fmtDate(c.last_checked_at)}</>}
              </div>
              <div className="row">
                <Btn small onClick={() => test(c)} busy={testing === c.id}>Probar conexión</Btn>
                <Btn small onClick={() => setEditing(c)}>Editar</Btn>
                <Btn small kind="ghost" onClick={() => confirm(`¿Eliminar la conexión «${c.name}» y su credencial guardada?`, async () => { await run(api(`/connections/${c.id}`, { method: "DELETE" }), "Conexión eliminada"); bump(); }, true)}>Eliminar</Btn>
              </div>
            </div>
          ))}
        </Panel>
        <div className="stack">
          <Panel title="Política de costo" note="Costos mostrados en Jarvis = uso reportado × precios que tú configuras. La factura del proveedor es la referencia definitiva.">
            <Check checked={paid} onChange={setPaid}>Permitir conexiones de pago (desactivado por defecto)</Check>
            <p className="small muted" style={{ marginTop: 8 }}>{paid ? "Activado: solo se usan si no hay alternativa local o sin costo, y siempre dentro de su presupuesto mensual." : "Desactivado: las conexiones marcadas como de pago no se usan nunca."}</p>
          </Panel>
          <Panel title={`Disponible en «${space.name}»`} note={`Política de IA del espacio: ${boot.ai_policies[space.ai_policy]}. Se cambia en Proyectos → Espacios.`}>
            {Object.entries(boot.capabilities).map(([id, name]) => {
              const a = avail.data?.[id];
              return <div key={id} className="check-row" style={{ gridTemplateColumns: "1fr auto" }}>
                <div>{name}<div className="small muted wrap">{a?.disponible ? a.conexiones.join(" → ") : a?.motivos?.join("; ") || "Sin conexión con esta capacidad"}</div></div>
                <Badge value={a?.disponible ? "ok" : "mute"} text={a?.disponible ? "Disponible" : "No disponible"} />
              </div>;
            })}
          </Panel>
        </div>
      </div>
      {editing && <ConnectionForm meta={boot} conn={editing === "new" ? undefined : editing} notify={notify} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); bump(); }} />}
      {confirmNode}
    </div>
  );
}
