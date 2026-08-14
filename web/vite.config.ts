import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// Dev proxy: /api -> FastAPI. Override client base with VITE_API_BASE if needed.
export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ""),
      },
    },
  },
});
