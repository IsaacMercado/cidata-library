import { eq, lt } from "drizzle-orm";
import { deleteCookie, setCookie } from "hono/cookie";
import { Hono } from "hono";
import type { Context, Next } from "hono";
import { crearDb, type AppVariables, type Env } from "./db/client";
import { sesiones, usuarios } from "./db/schema";
import { esquemaLogin, validar } from "./validacion";

export const COOKIE_SESION = "biblio_sesion";
const SESION_SEGUNDOS = 7 * 24 * 3600;
// 10k iteraciones ~= 2-5 ms de CPU: el plan gratuito limita a 10 ms/peticion.
// Solo se paga en el login (la sesion dura 7 dias); el resto de peticiones
// solo hacen 1 lectura D1 (I/O, no cuenta como CPU) + 1 sha256.
// Mantener sincronizado con scripts/crear_usuario.mjs.
const PBKDF2_ITER = 10_000;

// --- Primitivas (WebCrypto; mismos parametros que scripts/crear_usuario.mjs)

function aBase64(bytes: Uint8Array): string {
  let s = "";
  for (const b of bytes) s += String.fromCharCode(b);
  return btoa(s);
}

function deBase64(s: string): Uint8Array {
  const bin = atob(s);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

function aHex(bytes: Uint8Array): string {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

/** Lee una cookie de la cabecera (hono/cookie solo acepta Context). */
function leerCookie(peticion: Request, nombre: string): string | undefined {
  const cabecera = peticion.headers.get("Cookie");
  if (!cabecera) return undefined;
  for (const parte of cabecera.split(";")) {
    const i = parte.indexOf("=");
    if (i < 0) continue;
    if (parte.slice(0, i).trim() === nombre) {
      return decodeURIComponent(parte.slice(i + 1).trim());
    }
  }
  return undefined;
}

async function sha256Hex(texto: string): Promise<string> {
  const hash = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(texto),
  );
  return aHex(new Uint8Array(hash));
}

async function pbkdf2(
  password: string,
  sal: Uint8Array,
  iter: number,
): Promise<Uint8Array> {
  const clave = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt: sal, iterations: iter, hash: "SHA-256" },
    clave,
    256,
  );
  return new Uint8Array(bits);
}

/** Formato: pbkdf2$iteraciones$sal_base64$hash_base64 */
export async function hashPassword(password: string): Promise<string> {
  const sal = crypto.getRandomValues(new Uint8Array(16));
  const hash = await pbkdf2(password, sal, PBKDF2_ITER);
  return `pbkdf2$${PBKDF2_ITER}$${aBase64(sal)}$${aBase64(hash)}`;
}

function comparacionConstante(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let diff = 0;
  for (let i = 0; i < a.length; i++) diff |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return diff === 0;
}

export async function verificarPassword(
  password: string,
  almacenado: string,
): Promise<boolean> {
  const partes = almacenado.split("$");
  if (partes.length !== 4 || partes[0] !== "pbkdf2") return false;
  const iter = Number.parseInt(partes[1] ?? "", 10);
  if (!Number.isInteger(iter) || iter <= 0 || iter > 1_000_000) return false;
  let sal: Uint8Array;
  try {
    sal = deBase64(partes[2] ?? "");
  } catch {
    return false;
  }
  const hash = await pbkdf2(password, sal, iter);
  return comparacionConstante(
    `pbkdf2$${iter}$${partes[2]}$${aBase64(hash)}`,
    almacenado,
  );
}

// --- Sesiones en D1 + cookie httpOnly

export interface Sesion {
  id: number;
  email: string;
}

function esHex64(s: string): boolean {
  return /^[0-9a-f]{64}$/.test(s);
}

export async function sesionActual(
  db: ReturnType<typeof crearDb>,
  peticion: Request,
): Promise<Sesion | null> {
  const token = leerCookie(peticion, COOKIE_SESION);
  if (!token || !esHex64(token)) return null;
  const filas = await db
    .select({ id: usuarios.id, email: usuarios.email, expira: sesiones.expira })
    .from(sesiones)
    .innerJoin(usuarios, eq(sesiones.usuarioId, usuarios.id))
    .where(eq(sesiones.token, await sha256Hex(token)))
    .limit(1)
    .all();
  const fila = filas[0];
  if (!fila || fila.expira <= Math.floor(Date.now() / 1000)) return null;
  return { id: fila.id, email: fila.email };
}

function ponerCookie(
  c: Context,
  token: string | null,
  seguro: boolean,
): void {
  if (token === null) {
    deleteCookie(c, COOKIE_SESION, { path: "/" });
    return;
  }
  setCookie(c, COOKIE_SESION, token, {
    httpOnly: true,
    path: "/",
    sameSite: "Lax",
    secure: seguro,
    maxAge: SESION_SEGUNDOS,
  });
}

/** Protege la API: sin sesion valida responde 401 JSON. */
export async function requireAuth(
  c: Context<{ Bindings: Env; Variables: AppVariables }>,
  next: Next,
): Promise<Response | void> {
  const db = crearDb(c.env);
  const sesion = await sesionActual(db, c.req.raw);
  if (!sesion) {
    return c.json(
      {
        error: "auth_required",
        mensaje: "Inicia sesión para escribir. Ve a /login.",
      },
      401,
    );
  }
  c.set("usuario", sesion);
  await next();
}

/** Protege una pagina HTML: sin sesion redirige al login (conserva la URL). */
export async function requireAuthPagina(
  c: Context<{ Bindings: Env; Variables: AppVariables }>,
  next: Next,
): Promise<Response | void> {
  const db = crearDb(c.env);
  const sesion = await sesionActual(db, c.req.raw);
  if (!sesion) {
    const url = new URL(c.req.url);
    const destino = `/login?next=${encodeURIComponent(url.pathname + url.search)}`;
    return c.redirect(destino, 302);
  }
  await next();
}

// --- Sub-app /api/auth

export const authApp = new Hono<{ Bindings: Env; Variables: AppVariables }>();

authApp.post("/login", validar("json", esquemaLogin), async (c) => {
  const db = crearDb(c.env);
  const { email, password } = c.req.valid("json");
  const filas = await db
    .select()
    .from(usuarios)
    .where(eq(usuarios.email, email))
    .limit(1)
    .all();
  const usuario = filas[0];
  if (!usuario || !(await verificarPassword(password, usuario.hash))) {
    return c.json({ error: "credenciales", mensaje: "Email o contraseña incorrectos." }, 401);
  }
  const crudo = crypto.getRandomValues(new Uint8Array(32));
  const token = aHex(crudo);
  const ahora = Math.floor(Date.now() / 1000);
  await db.delete(sesiones).where(lt(sesiones.expira, ahora)).run();
  await db
    .insert(sesiones)
    .values({
      token: await sha256Hex(token),
      usuarioId: usuario.id,
      expira: ahora + SESION_SEGUNDOS,
    })
    .run();
  ponerCookie(c, token, new URL(c.req.url).protocol === "https:");
  return c.json({ email: usuario.email });
});

authApp.post("/logout", async (c) => {
  const db = crearDb(c.env);
  const token = leerCookie(c.req.raw, COOKIE_SESION);
  if (token && esHex64(token)) {
    await db.delete(sesiones).where(eq(sesiones.token, await sha256Hex(token))).run();
  }
  ponerCookie(c, null, false);
  return c.json({ salio: true });
});

authApp.get("/yo", async (c) => {
  const db = crearDb(c.env);
  const sesion = await sesionActual(db, c.req.raw);
  if (!sesion) return c.json({ error: "auth_required" }, 401);
  return c.json({ email: sesion.email });
});
