import { useEffect, useRef, useState } from "react";
import { api, ApiError, fmtDate } from "../api";
import { useApp, useData } from "../store";
import { Core, type CoreState } from "../components/Core";
import { JobList } from "../components/shared";
import { Badge, Btn, Check, FieldRow, Panel, Select, Skeleton, Stat } from "../components/ui";

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
      try { r.start(); setListening(true); startMeter(); } catch { notify("No se pudo iniciar el micrófono. Sigue por texto.", "error"); }
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

  return (
    <div className="command">
      <div className="stack">
        <Panel title="Pendiente" actions={<Btn small onClick={() => send("Resume lo pendiente")}>Resumir</Btn>}>
          {!p ? <Skeleton /> : <>
            <div className="stats">
              <Stat label="Por aprobar" value={p.por_aprobar} tone={p.por_aprobar ? "amber" : undefined} />
              <Stat label="Borradores" value={p.borradores} />
              <Stat label="Tareas abiertas" value={p.tareas_abiertas} hint={p.tareas_vencidas ? `${p.tareas_vencidas} vencidas` : undefined} />
              <Stat label="Trabajos en espera" value={p.trabajos_en_espera} tone={p.trabajos_en_espera ? "amber" : undefined} />
            </div>
            {p.detalle.por_aprobar.map((d: any) => <div key={d.id} className="small" style={{ marginTop: 8 }}><button className="linkbtn" onClick={() => nav(`revision/${d.id}`)}>{d.titulo}</button> <span className="muted">· {d.tipo}</span></div>)}
            {p.detalle.en_espera.map((j: any) => <p key={j.id} className="note note--amber wrap">{j.titulo}: {j.motivo}</p>)}
          </>}
        </Panel>
        <Panel title={`Capacidades en «${space.name}»`} actions={<Btn small onClick={() => nav("conexiones")}>Conexiones</Btn>}>
          {Object.entries(boot.capabilities).map(([id, name]) => (
            <div key={id} className="check-row" style={{ gridTemplateColumns: "1fr auto" }}>
              <div>{name}{disp[id]?.conexiones?.length > 0 && <div className="small muted">{disp[id].conexiones.join(", ")}</div>}</div>
              <Badge value={disp[id]?.disponible ? "ok" : "mute"} text={disp[id]?.disponible ? "Disponible" : "No configurada"} />
            </div>
          ))}
          <p className="note">Sin proveedores de IA siguen funcionando proyectos, archivos, tareas, revisión, importación/exportación, video con FFmpeg y los comandos directos.</p>
        </Panel>
      </div>

      <div className="command__center">
        <Core state={state} detail={detail} progress={progress} running={running} count={awaiting} levelRef={level} />
        <Panel className="grid" title="Jarvis">
          <div className="chat" aria-live="polite">
            {!msgs.length && <p className="muted small">Escribe una orden o mantén pulsado el micrófono. Ejemplos: «Busca oportunidades en accesorios para mascotas», «Resume lo pendiente», «tarea: llamar al gestor», «ayuda».</p>}
            {msgs.map((m) => (
              <div key={m.id} className={`msg msg--${m.role}`}>
                {m.content}
                {m.role === "jarvis" && m.data && (
                  <span className="msg__meta">
                    {m.data.job && <><button className="linkbtn" onClick={() => nav(`sistema/${m.data.job.id}`)}>{m.data.job.id}</button> · {m.data.job.status_label} · </>}
                    {m.data.deliverables?.map((d: string) => <button key={d} className="linkbtn" onClick={() => nav(`revision/${d}`)}>{d} </button>)}
                    {m.data.mode === "modelo" ? `interpretado por ${m.data.model}` : m.data.mode === "comando" ? "comando directo, sin modelo" : m.data.mode === "sin_modelo" ? "sin modelo disponible" : ""}
                    {m.created_at ? ` · ${fmtDate(m.created_at)}` : ""}
                  </span>
                )}
              </div>
            ))}
            <div ref={chatEnd} />
          </div>
          <form className="composer" onSubmit={(e) => { e.preventDefault(); send(text, heard.current && text === heard.current ? "voz" : "texto"); }}>
            <label className="sr" htmlFor="orden">Orden para Jarvis</label>
            <textarea id="orden" className="input" rows={2} value={text} placeholder="Escribe una orden… (Intro para enviar)" onChange={(e) => setText(e.target.value)}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(text, heard.current && text === heard.current ? "voz" : "texto"); } }} />
            <button type="button" className="mic" aria-pressed={listening} aria-label={listening ? "Micrófono abierto: suelta para terminar" : "Mantén pulsado para hablar"} disabled={!sttReady || busy}
              title={sttReady ? "Mantén pulsado para hablar" : "Voz no disponible: configúrala abajo"}
              onPointerDown={(e) => { e.currentTarget.setPointerCapture(e.pointerId); startListening(); }} onPointerUp={stopListening} onPointerCancel={stopListening}
              onKeyDown={(e) => { if ((e.key === " " || e.key === "Enter") && !e.repeat) { e.preventDefault(); startListening(); } }} onKeyUp={(e) => { if (e.key === " " || e.key === "Enter") stopListening(); }}>
              <svg viewBox="0 0 24 24"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>
            </button>
            <Btn kind="primary" type="submit" busy={busy} disabled={!text.trim()}>Enviar</Btn>
          </form>
          <div className="row" style={{ justifyContent: "space-between" }}>
            <span className={`micstate${listening ? " micstate--on" : ""}`}><i />{listening ? "MICRÓFONO ABIERTO" : "Micrófono cerrado"}</span>
            <span className="row">
              {speaking && <Btn small onClick={stopSpeaking}>Silenciar</Btn>}
              <Btn small kind="ghost" onClick={() => setShowVoice(!showVoice)}>Voz</Btn>
              <Btn small kind="ghost" onClick={async () => { await run(api("/assistant/history", { method: "DELETE", query: { space: space.id } }), "Conversación borrada"); setMsgs([]); }}>Borrar conversación</Btn>
            </span>
          </div>
          {showVoice && (
            <div className="stack">
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
        </Panel>
      </div>

      <div className="stack">
        <Panel title="Actividad" actions={<Btn small onClick={() => nav("sistema")}>Ver todo</Btn>}>
          <JobList limit={7} empty="Sin trabajos en este espacio. Lanza uno desde una orden o desde cualquier módulo." />
        </Panel>
        <Panel title="Accesos">
          <div className="row">
            {[["oportunidades", "Oportunidades"], ["leads", "Leads"], ["contenido", "Contenido"], ["video", "Video"], ["revision", "Revisión"], ["personal", "Personal"]].map(([r, t]) => <Btn small key={r} onClick={() => nav(r)}>{t}</Btn>)}
          </div>
          {!overview.data?.worker_alive && <p className="note note--amber">El worker no está activo: los trabajos quedarán en cola hasta que reinicies Jarvis con el lanzador.</p>}
        </Panel>
      </div>
    </div>
  );
}
