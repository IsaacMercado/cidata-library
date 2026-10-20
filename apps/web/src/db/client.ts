import { drizzle } from "drizzle-orm/d1";

export interface Env {
  DB: D1Database;
  ASSETS: Fetcher;
}

export interface AppVariables {
  usuario: { id: number; email: string };
}

/** Cliente Drizzle ligado al binding D1 del Worker. */
export function crearDb(env: Env) {
  return drizzle(env.DB);
}
