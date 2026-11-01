import { defineConfig } from "vite";
import { resolve } from "node:path";

export default defineConfig({
  base: "/",
  build: {
    outDir: "dist",
    emptyOutDir: true,
    sourcemap: false,
    assetsDir: "assets",
    rollupOptions: {
      input: {
        main: resolve(__dirname, "index.html"),
        admin: resolve(__dirname, "admin.html"),
        login: resolve(__dirname, "login.html"),
        users: resolve(__dirname, "users.html"),
      },
    },
  },
  server: {
    proxy: {
      "/api": "http://127.0.0.1",
    },
  },
});
