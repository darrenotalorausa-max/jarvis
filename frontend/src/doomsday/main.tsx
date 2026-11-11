import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "../styles.css";
import "./doomsday.css";
import { AppProvider } from "../store";
import { Btn } from "../components/ui";
import { App } from "./App";

// El tema se aplica antes de pintar para que no haya destello: oscuro salvo que el usuario haya elegido otro.
let theme = "dark";
try { theme = localStorage.getItem("doomsday.tema") || "dark"; } catch { /* sin almacenamiento */ }
document.documentElement.dataset.theme = ["dark", "light", "auto"].includes(theme) ? theme : "dark";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider
      fallback={(error, retry) => (
        <div className="splash">
          {error ? <div className="stack"><p className="page__title">No se pudo conectar con Doomsday</p><p className="muted">{error}</p><div><Btn kind="primary" onClick={retry}>Reintentar</Btn></div></div> : <p className="muted">Iniciando Doomsday…</p>}
        </div>
      )}
      onboarding={(_boot, reload) => (
        <div className="splash"><div className="stack"><p className="page__title">Preparando Doomsday</p><p className="muted">Se están creando las cuatro capas de datos.</p><div><Btn kind="primary" onClick={reload}>Continuar</Btn></div></div></div>
      )}
    >
      <App />
    </AppProvider>
  </StrictMode>,
);
