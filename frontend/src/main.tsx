import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "@fontsource-variable/inter/opsz.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "./styles.css";
import { App } from "./App";
import { AppProvider } from "./store";
import { Onboarding } from "./views/Onboarding";
import { Btn } from "./components/ui";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <AppProvider
      fallback={(error, retry) => (
        <div className="splash">
          {error ? <div className="stack"><p className="page__title">No se pudo conectar con Jarvis</p><p className="muted">{error}</p><div><Btn kind="primary" onClick={retry}>Reintentar</Btn></div></div> : <p className="muted">Iniciando Jarvis OS…</p>}
        </div>
      )}
      onboarding={(boot, reload) => <Onboarding boot={boot} reload={reload} />}
    >
      <App />
    </AppProvider>
  </StrictMode>,
);
