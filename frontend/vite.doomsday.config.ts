import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// Doomsday: segunda aplicación del mismo proyecto. Comparte componentes con Jarvis; se compila aparte y la sirve su propio backend (puerto 8766).
export default defineConfig({
  plugins: [react()],
  server: { host: "127.0.0.1", port: 5174, open: "/doomsday.html", proxy: { "/api": { target: "http://127.0.0.1:8766", changeOrigin: false } } },
  build: { outDir: "dist-doomsday", sourcemap: false, chunkSizeWarningLimit: 900, rollupOptions: { input: "doomsday.html" } },
});
