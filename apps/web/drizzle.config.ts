import { defineConfig } from "drizzle-kit";

// Drizzle genera SQL en ./migrations, el mismo directorio que usa
// `wrangler d1 migrations apply` (convención oficial de Cloudflare).
export default defineConfig({
  dialect: "sqlite",
  schema: "./src/db/schema.ts",
  out: "./migrations",
});
