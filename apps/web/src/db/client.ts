import { drizzle } from "drizzle-orm/d1";

export interface Env {
  DB: D1Database;
  ASSETS: Fetcher;
}

export interface AppVariables {
  user: { id: number; email: string };
}

/** Drizzle client bound to the Worker's D1 binding. */
export function createDb(env: Env) {
  return drizzle(env.DB);
}
