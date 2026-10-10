import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

// Dev: `npm run dev` proxies /api to the Python server printed by `uv run mono-it-tax`.
export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/api": process.env.MONO_IT_TAX_API ?? "http://127.0.0.1:8000" } },
  test: { environment: "node" },
});
