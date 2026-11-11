import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "../api";
import { useApp, useData } from "../store";
import { Core, type CoreState, type DialItem } from "../components/Core";
import { cue } from "../sound";
import { Check, FieldRow, Select, Skeleton } from "../components/ui";

const DIAL: DialItem[] = [
  { id: "negocios", short: "Negocios", label: "Centro de negocios" }, { id: "oportunidades", short: "Oportunidades", label: "Mesa de oportunidades" }, { id: "leads", short: "Leads", label: "Leads y ofertas B2B" },
  { id: "contenido", short: "Contenido", label: "Fábrica de contenido" }, { id: "video", short: "Video", label: "Editor audiovisual" }, { id: "shopify", short: "Shopify", label: "Constructor Shopify" },
  { id: "clipping", short: "Clipping", label: "Clipping" }, { id: "revision", short: "Revisión", label: "Revisión y aprobación" }, { id: "proyectos", short: "Proyectos", label: "Proyectos, marcas y biblioteca" },
  { id: "operaciones", short: "Economía", label: "Operaciones y economía" }, { id: "personal", short: "Personal", label: "Espacio personal" }, { id: "biblioteca", short: "Biblioteca", label: "Biblioteca" },
  { id: "conexiones", short: "Conexiones", label: "Conexiones" }, { id: "apps", short: "Apps", label: "Apps conectadas" }, { id: "sistema", short: "Sistema", label: "Trabajos, uso y diagnóstico" },
];
/** Hora si es de hoy; si no, día y mes. */
const when = (iso?: string | null) => { if (!iso) return ""; const d = new Date(iso); return d.toDateString() === new Date().toDateString() ? d.toLocaleTimeString("es", { hour: "2-digit", minute: "2-digit" }) : d.toLocaleDateString("es", { day: "numeric", month: "short" }); };
const TONE: Record<string, string> = { running: "live", completed: "ok", failed: "bad", cancelled: "mute" };
type Msg = { id: number | string; role: string; content: string; data?: any; created_at?: string };
type VoicePrefs = { stt: string; tts: string; autoSend: boolean };

const SR: any = typeof window !== "undefined" ? (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition : undefined;
const canRecord = typeof navigator !== "undefined" && !!navigator.mediaDevices?.getUserMedia && typeof MediaRecorder !== "undefined";
const canSpeak = typeof window !== "undefined" && "speechSynthesis" in window;
const MIC_ERRORS: Record<string, string> = {
  "not-allowed": "El navegador denegó el permiso del micrófono. Puedes seguir por texto.", "service-not-allowed": "El reconocimiento de voz del navegador no está permitido aquí.",
  "no-speech": "No se detectó voz.", "audio-capture": "No se encontró ningún micrófono.", network: "El reconocimiento del navegador necesita conexión y no respondió.",
};

export function Command() {
  const { space, boot, jobs, nav, notify, run, reload, doneTick } = useApp();
  const [msgs, setMsgs] = useState<Msg[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [speaking, setSpeaking] = useState(false);
  const [failed, setFailed] = useState<string | null>(null);
  const [showVoice, setShowVoice] = useState(false);
  const saved = (boot.settings.voice || {}) as Partial<VoicePrefs>;
  const prefs: VoicePrefs = { stt: saved.stt || (SR ? "navegador" : "ninguno"), tts: saved.tts || "ninguno", autoSend: !!saved.autoSend };
  const overview = useData<any>(() => api("/overview", { query: { space: space.id } }), [space.id, doneTick, msgs.length]);
  const rec = useRef<any>(null);
  const speakingRef = useRef(false);
  const chatEnd = useRef<HTMLDivElement>(null);
  const heard = useRef("");
  const level = useRef(0);
  const meter = useRef<{ ctx: AudioContext; raf: number; own?: MediaStream } | null>(null);

  // Medidor del nivel real del micrófono para la onda del núcleo. No graba ni guarda audio: solo calcula el volumen.
  async function startMeter(stream?: MediaStream) {
    try {
      const src = stream || await navigator.mediaDevices.getUserMedia({ audio: true });
      const ctx = new AudioContext();
      const an = ctx.createAnalyser();
      an.fftSize = 512;
      ctx.createMediaStreamSource(src).connect(an);
      const buf = new Uint8Array(an.fftSize);
      const m = { ctx, raf: 0, own: stream ? undefined : src };
      const loop = () => {
        an.getByteTimeDomainData(buf);
        let sum = 0;
        for (const v of buf) sum += ((v - 128) / 128) ** 2;
        level.current = Math.sqrt(sum / buf.length);
        m.raf = requestAnimationFrame(loop);
      };
      loop();
      meter.current = m;
    } catch { /* sin medidor: la onda usa un nivel mínimo */ }
  }
  function stopMeter() {
    const m = meter.current;
    if (!m) return;
    cancelAnimationFrame(m.raf);
    m.own?.getTracks().forEach((t) => t.stop());
    m.ctx.close().catch(() => undefined);
    meter.current = null;
    level.current = 0;
  }

  useEffect(() => { api<Msg[]>("/assistant/history", { query: { space: space.id } }).then(setMsgs).catch(() => setMsgs([])); }, [space.id]);
  // Solo se desplaza la conversación, nunca la página.
  useEffect(() => { const box = chatEnd.current?.parentElement; if (box) box.scrollTop = box.scrollHeight; }, [msgs.length]);
  useEffect(() => () => { stopSpeaking(); stopMeter(); try { rec.current?.stop?.(); } catch { /* ya detenido */ } }, []);

  const savePrefs = async (p: Partial<VoicePrefs>) => { await run(api("/settings", { method: "PATCH", body: { voice: { ...prefs, ...p } } })); reload(); };
  const setSpeak = (v: boolean) => { speakingRef.current = v; setSpeaking(v); };
  function stopSpeaking() {
    if (canSpeak) window.speechSynthesis.cancel();
    setSpeak(false);
  }
  async function speak(out: string) {
    if (prefs.tts === "ninguno" || !out) return;
    if (prefs.tts === "elevenlabs") {
      try {
        const res = await api<Response>("/voice/speak", { body: { space: space.id, text: out }, raw: true });
        const audio = new Audio(URL.createObjectURL(await res.blob()));
        audio.onplay = () => setSpeak(true);
        audio.onended = audio.onerror = () => { setSpeak(false); URL.revokeObjectURL(audio.src); };
        await audio.play();
        return;
      } catch (e) {
        notify(`Voz de ElevenLabs no disponible (${(e as Error).message}). ${canSpeak ? "Uso la voz del navegador." : "Sigo solo con texto."}`, "info");
        if (!canSpeak) return;
      }
    }
    if (!canSpeak) return;
    const u = new SpeechSynthesisUtterance(out);
    u.lang = "es-ES";
    const v = window.speechSynthesis.getVoices().find((x) => x.lang.toLowerCase().startsWith("es"));
    if (v) u.voice = v;
    u.rate = 1.02;
    u.onstart = () => setSpeak(true);
    u.onend = u.onerror = () => setSpeak(false);
    window.speechSynthesis.speak(u);
  }

  async function send(value: string, origin: "texto" | "voz" = "texto") {
    const t = value.trim();
    if (!t || busy) return;
    setBusy(true);
    setFailed(null);
    setText("");
    setMsgs((m) => [...m, { id: `u${Date.now()}`, role: "usuario", content: t }]);
    try {
      const out = await api<any>("/assistant", { body: { space: space.id, text: t, origin } });
      setMsgs((m) => [...m, { id: `j${Date.now()}`, role: "jarvis", content: out.reply, data: out }]);
      if (out.error) setFailed("La orden no pudo ejecutarse");
      speak(out.speak || "");
    } catch (e) {
      const m = e instanceof ApiError ? e.message : "Error inesperado";
      setFailed(m);
      setMsgs((x) => [...x, { id: `e${Date.now()}`, role: "jarvis", content: `No pude procesar la orden: ${m}`, data: { error: true } }]);
    } finally {
      setBusy(false);
    }
  }

  // ---- Pulsar para hablar. El micrófono solo está abierto mientras se mantiene pulsado el botón.
  async function startListening() {
    if (listening || prefs.stt === "ninguno") return;
    stopSpeaking(); // la voz de Jarvis nunca debe convertirse en una orden
    heard.current = "";
    if (prefs.stt === "navegador" && SR) {
      const r = new SR();
      r.lang = "es-ES";
      r.interimResults = true;
      r.continuous = true;
      r.onresult = (ev: any) => {
        if (speakingRef.current) return;
        heard.current = Array.from(ev.results as any[]).map((x: any) => x[0].transcript).join(" ");
        setText(heard.current);
      };
      r.onerror = (ev: any) => { if (ev.error !== "aborted") notify(MIC_ERRORS[ev.error] || `Fallo del reconocimiento de voz (${ev.error}). Sigue por texto.`, "error"); };
      r.onend = () => { stopMeter(); setListening(false); rec.current = null; if (prefs.autoSend && heard.current.trim()) send(heard.current, "voz"); };
      rec.current = r;
      try { r.start(); setListening(true); startMeter(); cue("mic"); } catch { notify("No se pudo iniciar el micrófono. Sigue por texto.", "error"); }
    } else if (prefs.stt === "servidor" && canRecord) {
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const chunks: Blob[] = [];
        const mr = new MediaRecorder(stream);
        mr.ondataavailable = (e) => chunks.push(e.data);
        mr.onstop = async () => {
          stopMeter();
          stream.getTracks().forEach((t) => t.stop()); // micrófono cerrado de inmediato
          setListening(false);
          rec.current = null;
          const form = new FormData();
          form.set("space", space.id);
          form.set("audio", new Blob(chunks, { type: mr.mimeType || "audio/webm" }), "orden.webm");
          setBusy(true);
          try {
            const out = await api<{ text: string }>("/voice/transcribe", { form });
            if (prefs.autoSend && out.text) { setBusy(false); send(out.text, "voz"); return; }
            setText(out.text);
          } catch (e) {
            notify(`No se pudo transcribir: ${(e as Error).message} Escribe la orden por texto.`, "error");
          }
          setBusy(false);
        };
        rec.current = mr;
        mr.start();
        startMeter(stream);
        cue("mic");
        setListening(true);
      } catch {
        notify(MIC_ERRORS["not-allowed"], "error");
      }
    } else {
      notify("Este navegador no ofrece captura de voz con la opción elegida. Cambia el modo de voz o escribe la orden.", "error");
    }
  }
  function stopListening() {
    try { rec.current?.stop?.(); } catch { /* ya detenido */ }
  }

  const runningJobs = jobs.filter((j) => j.status === "running");
  const running = runningJobs.length;
  const progress = running ? runningJobs.reduce((a, j) => a + (j.progress || 0), 0) / running : null;
  const p = overview.data?.pendientes;
  const awaiting = (p?.por_aprobar || 0) + jobs.filter((j) => j.status === "waiting_approval").length;
  const state: CoreState = listening ? "listening" : speaking ? "speaking" : failed ? "error" : busy || running ? "processing" : awaiting ? "approval" : "idle";
  const detail = listening ? undefined : failed ? failed.slice(0, 80) : busy ? "Interpretando tu orden" : running ? `${running} trabajo(s) en ejecución` : awaiting ? `${awaiting} decisión(es) pendiente(s)` : p?.trabajos_en_espera ? `Sin actividad; ${p.trabajos_en_espera} trabajo(s) en espera de configuración o cuota` : undefined;
  const sttReady = prefs.stt === "navegador" ? !!SR : prefs.stt === "servidor" ? canRecord : false;
  const disp = overview.data?.disponibilidad || {};

  const rows: [string, number, boolean][] = p ? [["Por aprobar", p.por_aprobar, p.por_aprobar > 0], ["Borradores", p.borradores, false], ["Tareas abiertas", p.tareas_abiertas, p.tareas_vencidas > 0], ["Trabajos en espera", p.trabajos_en_espera, p.trabajos_en_espera > 0]] : [];
  const submit = () => send(text, heard.current && text === heard.current ? "voz" : "texto");

  return (
    <div className="command">
      <aside className="hud" aria-label="Pendiente y capacidades">
        <section className="hud__sec">
          <header className="hud__h"><h2>Pendiente</h2><button className="hud__link" onClick={() => send("Resume lo pendiente")}>Resumir</button></header>
          {!p ? <Skeleton /> : <>
            {rows.map(([name, n, warn]) => <div key={name} className="hud__row"><span>{name}</span><b className={warn ? "amber" : undefined}>{n}</b></div>)}
            {p.tareas_vencidas > 0 && <p className="hud__note amber">{p.tareas_vencidas} tarea(s) vencida(s).</p>}
            {p.detalle.por_aprobar.map((d: any) => <p key={d.id} className="hud__note"><button className="linkbtn" onClick={() => nav(`revision/${d.id}`)}>{d.titulo}</button> <span className="muted">{d.tipo}</span></p>)}
            {p.detalle.en_espera.map((j: any) => <p key={j.id} className="hud__note amber wrap">{j.titulo}: {j.motivo}</p>)}
          </>}
        </section>
        <section className="hud__sec">
          <header className="hud__h"><h2>Capacidades en «{space.name}»</h2><button className="hud__link" onClick={() => nav("conexiones")}>Conexiones</button></header>
          {Object.entries(boot.capabilities).map(([id, name]) => {
            const on = !!disp[id]?.disponible;
            return <div key={id} className={`hud__cap${on ? " hud__cap--on" : ""}`}><i aria-hidden="true" /><span>{name}</span><em>{on ? (disp[id].conexiones || []).join(", ") || "Disponible" : "No configurada"}</em></div>;
          })}
          <p className="hud__note">Sin IA siguen funcionando proyectos, archivos, tareas, revisión, importación, video y las órdenes directas.</p>
        </section>
      </aside>

      <div className="command__center">
        <Core state={state} detail={detail} progress={progress} running={running} count={awaiting} levelRef={level} dial={DIAL} />
        <div className="chat" aria-live="polite">
          {!msgs.length && <p className="chat__hint">Escribe una orden o mantén pulsado el micrófono. Por ejemplo: «Busca oportunidades en accesorios para mascotas», «Resume lo pendiente», «tarea: llamar al gestor» o «ayuda».</p>}
          {msgs.map((m) => (
            <div key={m.id} className={`msg msg--${m.role}${m.data?.error ? " msg--error" : ""}`}>
              {m.content}
              {m.role === "jarvis" && m.data && (
                <span className="msg__meta">
                  {m.data.job && <><button className="linkbtn" onClick={() => nav(`sistema/${m.data.job.id}`)}>{m.data.job.id}</button> · {m.data.job.status_label} · </>}
                  {m.data.deliverables?.map((d: string) => <button key={d} className="linkbtn" onClick={() => nav(`revision/${d}`)}>{d} </button>)}
                  {m.data.mode === "modelo" ? `interpretado por ${m.data.model}` : m.data.mode === "comando" ? "orden directa, sin modelo" : m.data.mode === "sin_modelo" ? "sin modelo disponible" : ""}
                  {m.created_at ? ` · ${when(m.created_at)}` : ""}
                </span>
              )}
            </div>
          ))}
          <div ref={chatEnd} />
        </div>
        <form className="composer" onSubmit={(e) => { e.preventDefault(); submit(); }}>
          <label className="sr" htmlFor="orden">Orden para Jarvis</label>
          <textarea id="orden" rows={1} value={text} placeholder="Dile algo a Jarvis" onChange={(e) => setText(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }} />
          <button type="button" className="mic" aria-pressed={listening} aria-label={listening ? "Micrófono abierto: suelta para terminar" : "Mantén pulsado para hablar"} disabled={!sttReady || busy}
            title={sttReady ? "Mantén pulsado para hablar" : "Voz no disponible: actívala en «Voz»"}
            onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); startListening(); }} onPointerUp={stopListening} onPointerCancel={stopListening}
            onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); startListening(); } }} onKeyUp={(e) => { if (e.key === " " || e.key === "Enter") stopListening(); }}>
            <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
          </button>
          <button type="submit" className="send" disabled={!text.trim() || busy} aria-label="Enviar" title="Enviar (Intro)">
            <svg viewBox="0 0 24 24"><path d="M12 19V5M6 11l6-6 6 6" /></svg>
          </button>
        </form>
        <div className="command__foot">
          <span className={`micstate${listening ? " micstate--on" : ""}`}><i />{listening ? "Micrófono abierto" : "Micrófono cerrado"}</span>
          <span className="row">
            {speaking && <button className="hud__link" onClick={stopSpeaking}>Silenciar</button>}
            <button className="hud__link" aria-expanded={showVoice} onClick={() => setShowVoice(!showVoice)}>Voz</button>
            <button className="hud__link" onClick={async () => { await run(api("/assistant/history", { method: "DELETE", query: { space: space.id } }), "Conversación borrada"); setMsgs([]); }}>Borrar conversación</button>
          </span>
        </div>
        {showVoice && (
          <div className="hud__voice stack">
            <div className="form">
              <FieldRow label="Entrada de voz" hint={prefs.stt === "navegador" ? "El reconocimiento del navegador puede enviar el audio al servicio del fabricante del navegador." : prefs.stt === "servidor" ? "El audio se envía al proveedor de transcripción configurado y se elimina al terminar." : "Solo texto."}>
                <Select value={prefs.stt} onChange={(v) => savePrefs({ stt: v })} options={[["ninguno", "Desactivada"], ["navegador", `Reconocimiento del navegador${SR ? "" : " (no disponible aquí)"}`], ["servidor", `Transcripción configurada en Conexiones${canRecord ? "" : " (sin grabación en este navegador)"}`]]} />
              </FieldRow>
              <FieldRow label="Respuesta por voz" hint="La respuesta por texto siempre está disponible.">
                <Select value={prefs.tts} onChange={(v) => savePrefs({ tts: v })} options={[["ninguno", "Desactivada"], ["navegador", `Voz del sistema/navegador${canSpeak ? "" : " (no disponible aquí)"}`], ["elevenlabs", "ElevenLabs (requiere conexión configurada)"]]} />
              </FieldRow>
            </div>
            <Check checked={prefs.autoSend} onChange={(v) => savePrefs({ autoSend: v })}>Enviar la orden al soltar el micrófono (si no, la transcripción queda editable antes de enviar)</Check>
            <p className="note">Jarvis no escucha de forma permanente ni guarda grabaciones: el micrófono solo se abre mientras mantienes pulsado el botón, y el audio temporal se borra tras transcribirlo.</p>
          </div>
        )}
      </div>

      <aside className="hud" aria-label="Actividad y sistema">
        <section className="hud__sec">
          <header className="hud__h"><h2>Actividad</h2><button className="hud__link" onClick={() => nav("sistema")}>Ver todo</button></header>
          {!jobs.length ? <p className="hud__note">Aún no hay trabajos en este espacio. Lanza uno con una orden o desde cualquier módulo.</p>
            : jobs.slice(0, 7).map((j) => (
              <button key={j.id} className={`hud__act hud__act--${TONE[j.status] || (j.status.startsWith("waiting") ? "warn" : "mute")}`} onClick={() => nav(`sistema/${j.id}`)}>
                <i aria-hidden="true" /><span>{j.title}</span><em>{j.status_label}{j.status === "running" ? ` · ${Math.round((j.progress || 0) * 100)} %` : ""} · {when(j.finished_at || j.created_at)}</em>
              </button>
            ))}
        </section>
        <section className="hud__sec">
          <header className="hud__h"><h2>Sistema</h2></header>
          <div className="hud__row hud__row--text"><span>Worker</span><b>{overview.data?.worker_alive ? "Activo" : "Detenido"}</b></div>
          <div className="hud__row hud__row--text"><span>Agentes</span><b className={boot.settings.agents_paused ? "amber" : undefined}>{boot.settings.agents_paused ? "En pausa" : `${running} en ejecución`}</b></div>
          <div className="hud__row hud__row--text"><span>IA en este espacio</span><b>{boot.ai_policies[space.ai_policy]}</b></div>
          {!overview.data?.worker_alive && overview.data && <p className="hud__note amber">El worker no está activo: los trabajos quedan en cola hasta que reinicies Jarvis.</p>}
          <p className="hud__note">Las marcas del anillo exterior llevan a cada módulo. <span className="mono">Ctrl K</span> busca en todo.</p>
        </section>
      </aside>
    </div>
  );
}
