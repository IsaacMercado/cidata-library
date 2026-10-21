import { defineConfig } from "drizzle-kit";

// Drizzle writes SQL to ./migrations, the same directory used by
// `wrangler d1 migrations apply` (Cloudflare's official convention).
export default defineConfig({
  dialect: "sqlite",
  schema: "./src/db/schema.ts",
  out: "./migrations",
});
