import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O proxy encaminha /api → backend FastAPI (porta 8000) em desenvolvimento,
// evitando qualquer configuração de CORS no navegador.
export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      "/api": { target: "http://localhost:8000", changeOrigin: true },
    },
  },
});
