// Sonidos sintetizados con Web Audio (originales, sin archivos). Se pueden desactivar desde la barra superior.
let ctx: AudioContext | null = null;
const KEY = "jarvis.sonido";

export const soundOn = () => { try { return localStorage.getItem(KEY) !== "no"; } catch { return true; } };
export const setSound = (on: boolean) => { try { localStorage.setItem(KEY, on ? "si" : "no"); } catch { /* sin almacenamiento */ } };

function audio(): AudioContext | null {
  if (!soundOn()) return null;
  try {
    ctx = ctx || new AudioContext();
    return ctx;
  } catch { return null; }
}

function tone(ac: AudioContext, out: AudioNode, freq: number, start: number, dur: number, peak: number, type: OscillatorType = "sine", glideTo?: number) {
  const o = ac.createOscillator(), g = ac.createGain();
  o.type = type;
  o.frequency.setValueAtTime(freq, start);
  if (glideTo) o.frequency.exponentialRampToValueAtTime(glideTo, start + dur);
  g.gain.setValueAtTime(0.0001, start);
  g.gain.exponentialRampToValueAtTime(peak, start + Math.min(0.08, dur / 3));
  g.gain.exponentialRampToValueAtTime(0.0001, start + dur);
  o.connect(g).connect(out);
  o.start(start);
  o.stop(start + dur + 0.05);
}

/** Encendido: barrido grave que sube, acorde abierto que se despliega y un destello agudo. ~2 s. */
function bootNow(ac: AudioContext) {
  const t = ac.currentTime + 0.02;
  const master = ac.createGain();
  master.gain.value = 0.5;
  const lp = ac.createBiquadFilter();
  lp.type = "lowpass";
  lp.frequency.setValueAtTime(500, t);
  lp.frequency.exponentialRampToValueAtTime(7000, t + 1.1);
  master.connect(lp).connect(ac.destination);
  tone(ac, master, 55, t, 1.2, 0.22, "sawtooth", 110);                 // energía que sube
  [[220, 0.25], [329.63, 0.42], [440, 0.58], [659.25, 0.74]].forEach(([f, d]) => tone(ac, master, f, t + d, 1.5 - d * 0.6, 0.11, "triangle"));
  tone(ac, master, 1760, t + 0.95, 0.9, 0.035);                         // destello
  tone(ac, master, 2637, t + 1.05, 0.7, 0.018);
}

/** Intenta sonar al abrir; si el navegador exige un gesto, suena en la primera pulsación o tecla. Una vez por sesión. */
export function bootSound() {
  try { if (sessionStorage.getItem("jarvis.boot")) return; } catch { /* continúa */ }
  const ac = audio();
  if (!ac) return;
  const play = () => { try { sessionStorage.setItem("jarvis.boot", "1"); } catch { /* sin almacenamiento */ } bootNow(ac); };
  if (ac.state === "running") { play(); return; }
  const onGesture = () => { ac.resume().then(play).catch(() => undefined); window.removeEventListener("pointerdown", onGesture); window.removeEventListener("keydown", onGesture); };
  window.addEventListener("pointerdown", onGesture, { once: true });
  window.addEventListener("keydown", onGesture, { once: true });
}

/** Señales breves ligadas a hechos: trabajo completado, fallo, micrófono abierto. */
export function cue(kind: "done" | "fail" | "mic" | "tick") {
  const ac = audio();
  if (!ac || ac.state !== "running") return;
  const t = ac.currentTime + 0.01;
  const g = ac.createGain();
  g.gain.value = 0.35;
  g.connect(ac.destination);
  if (kind === "done") { tone(ac, g, 660, t, 0.16, 0.12, "triangle"); tone(ac, g, 990, t + 0.11, 0.26, 0.1, "triangle"); }
  else if (kind === "fail") { tone(ac, g, 330, t, 0.18, 0.12, "triangle"); tone(ac, g, 220, t + 0.14, 0.3, 0.1, "triangle"); }
  else if (kind === "mic") tone(ac, g, 880, t, 0.09, 0.08);
  else tone(ac, g, 1320, t, 0.05, 0.04);
}
