import { defineConfig } from "vite";
import reactPlugin from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [reactPlugin()],
  server: {
    port: 5173,
    host: "0.0.0.0"
  },
  preview: {
    port: 4173
  }
});
