import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

const backendTarget = process.env.MYROLL_BACKEND_URL ?? "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: "127.0.0.1",
    port: Number(process.env.MYROLL_FRONTEND_PORT ?? 5173),
    proxy: {
      "/api": backendTarget,
      "/health": backendTarget
    }
  },
  test: {
    environment: "jsdom",
    setupFiles: "./src/test/setup.ts",
    globals: true,
    include: ["src/**/*.test.ts", "src/**/*.test.tsx"]
  }
});
