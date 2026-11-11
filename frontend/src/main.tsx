import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./styles.css";
import "./doomsday/doomsday.css";
import { App } from "./doomsday/App";
import { AppProvider } from "./store";
import { Onboarding } from "./views/Onboarding";
import { Btn } from "./components/ui";

// El tema se aplica antes de pintar para que no haya destello: oscuro salvo que el usuario haya elegido otro.
let theme = "dark";
try { theme = localStorage.getItem("doomsday.tema") || "dark"; } catch { /* sin almacenamiento */ }
document.documentElement.dataset.theme = ["dark", "light", "auto"].includes(theme) ? theme : "dark";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider
      fallback={(error, retry) => (
        <div className="splash">
          {error ? <div className="stack"><p className="page__title">No se pudo conectar con Vision</p><p className="muted">{error}</p><div><Btn kind="primary" onClick={retry}>Reintentar</Btn></div></div> : <p className="muted">Iniciando Vision…</p>}
        </div>
      )}
      onboarding={(boot, reload) => <Onboarding boot={boot} reload={reload} />}
    >
      <App />
    </AppProvider>
  </StrictMode>,
);
