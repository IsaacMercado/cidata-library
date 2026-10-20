import { eq, lt } from "drizzle-orm";
import { deleteCookie, setCookie } from "hono/cookie";
import { Hono } from "hono";
import type { Context, Next } from "hono";
import { createDb, type AppVariables, type Env } from "./db/client";
import { sessions, users } from "./db/schema";
import { loginSchema, validate } from "./validation";

// Opaque, server-side sessions: the cookie contains a 256-bit random token
// and D1 stores only its SHA-256. There is no signing key because there is
// nothing to sign or verify cryptographically; the database row is the
// authority. See the security section in README.md.
const SESSION_COOKIE_DEV = "biblio_session";
const SESSION_COOKIE_PROD = "__Host-biblio_session";
const SESSION_TTL_SECONDS = 7 * 24 * 3600;
// 10k iterations ~= 2-5 ms of CPU: the free plan caps each request at 10 ms.
// Only paid on login (sessions last 7 days); all other requests do one D1
// read plus one SHA-256.
// Keep in sync with tools/create_user.mjs.
const PBKDF2_ITERATIONS = 10_000;

// Valid PBKDF2 hash used when the email does not exist, so both branches pay
// the same CPU cost (prevents trivial email enumeration through timing).
const DUMMY_PASSWORD_HASH =
  "pbkdf2$10000$AAAAAAAAAAAAAAAAAAAAAA==$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=";

// --- Primitives (WebCrypto; same parameters as tools/create_user.mjs)

function toBase64(bytes: Uint8Array): string {
  let result = "";
  for (const byte of bytes) result += String.fromCharCode(byte);
  return btoa(result);
}

function fromBase64(value: string): Uint8Array {
  const binary = atob(value);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
  return bytes;
}

function toHex(bytes: Uint8Array): string {
  return [...bytes].map((byte) => byte.toString(16).padStart(2, "0")).join("");
}

/** Read a cookie header (hono/cookie only accepts a Context). */
function readCookie(request: Request, name: string): string | undefined {
  const header = request.headers.get("Cookie");
  if (!header) return undefined;
  for (const part of header.split(";")) {
    const separator = part.indexOf("=");
    if (separator < 0) continue;
    if (part.slice(0, separator).trim() === name) {
      try {
        return decodeURIComponent(part.slice(separator + 1).trim());
      } catch {
        return undefined;
      }
    }
  }
  return undefined;
}

function isSecureRequest(request: Request): boolean {
  return new URL(request.url).protocol === "https:";
}

function sessionCookieName(secure: boolean): string {
  // __Host- requires Secure, Path=/ and no Domain attribute.
  return secure ? SESSION_COOKIE_PROD : SESSION_COOKIE_DEV;
}

async function sha256Hex(text: string): Promise<string> {
  const hash = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(text),
  );
  return toHex(new Uint8Array(hash));
}

async function pbkdf2(
  password: string,
  salt: Uint8Array,
  iterations: number,
): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = await crypto.subtle.deriveBits(
    { name: "PBKDF2", salt, iterations, hash: "SHA-256" },
    key,
    256,
  );
  return new Uint8Array(bits);
}

/** Format: pbkdf2$iterations$salt_base64$hash_base64 */
export async function hashPassword(password: string): Promise<string> {
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const hash = await pbkdf2(password, salt, PBKDF2_ITERATIONS);
  return `pbkdf2$${PBKDF2_ITERATIONS}$${toBase64(salt)}$${toBase64(hash)}`;
}

function constantTimeEqual(a: string, b: string): boolean {
  if (a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i++) {
    difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  }
  return difference === 0;
}

export async function verifyPassword(
  password: string,
  stored: string,
): Promise<boolean> {
  const parts = stored.split("$");
  if (parts.length !== 4 || parts[0] !== "pbkdf2") return false;
  const iterations = Number.parseInt(parts[1] ?? "", 10);
  if (!Number.isInteger(iterations) || iterations <= 0 || iterations > 1_000_000) {
    return false;
  }
  let salt: Uint8Array;
  try {
    salt = fromBase64(parts[2] ?? "");
  } catch {
    return false;
  }
  const hash = await pbkdf2(password, salt, iterations);
  return constantTimeEqual(
    `pbkdf2$${iterations}$${parts[2]}$${toBase64(hash)}`,
    stored,
  );
}

// --- Sessions in D1 + httpOnly cookie

export interface SessionUser {
  id: number;
  email: string;
}

function isHex64(value: string): boolean {
  return /^[0-9a-f]{64}$/.test(value);
}

export async function getCurrentSession(
  db: ReturnType<typeof createDb>,
  request: Request,
): Promise<SessionUser | null> {
  const secure = isSecureRequest(request);
  const token =
    readCookie(request, sessionCookieName(secure)) ??
    readCookie(request, SESSION_COOKIE_DEV) ??
    readCookie(request, SESSION_COOKIE_PROD);
  if (!token || !isHex64(token)) return null;

  const rows = await db
    .select({
      id: users.id,
      email: users.email,
      expiresAt: sessions.expiresAt,
    })
    .from(sessions)
    .innerJoin(users, eq(sessions.userId, users.id))
    .where(eq(sessions.token, await sha256Hex(token)))
    .limit(1)
    .all();

  const row = rows[0];
  if (!row || row.expiresAt <= Math.floor(Date.now() / 1000)) return null;
  return { id: row.id, email: row.email };
}

function setSessionCookie(
  c: Context,
  token: string | null,
  secure: boolean,
): void {
  const name = sessionCookieName(secure);
  if (token === null) {
    deleteCookie(c, name, { path: "/", secure });
    // Also clear the other cookie name (local/production switch).
    const otherName =
      name === SESSION_COOKIE_PROD ? SESSION_COOKIE_DEV : SESSION_COOKIE_PROD;
    deleteCookie(c, otherName, {
      path: "/",
      secure: otherName === SESSION_COOKIE_PROD,
    });
    return;
  }
  setCookie(c, name, token, {
    httpOnly: true,
    path: "/",
    sameSite: "Lax",
    secure,
    maxAge: SESSION_TTL_SECONDS,
  });
}

/** Protect the API: returns 401 JSON without a valid session. */
export async function requireAuth(
  c: Context<{ Bindings: Env; Variables: AppVariables }>,
  next: Next,
): Promise<Response | void> {
  const db = createDb(c.env);
  const session = await getCurrentSession(db, c.req.raw);
  if (!session) {
    return c.json(
      {
        error: "auth_required",
        message: "Inicia sesión para escribir. Ve a /login.",
      },
      401,
    );
  }
  c.set("user", session);
  await next();
}

/** Protect an HTML page: redirect to login and preserve the target URL. */
export async function requireAuthPage(
  c: Context<{ Bindings: Env; Variables: AppVariables }>,
  next: Next,
): Promise<Response | void> {
  const db = createDb(c.env);
  const session = await getCurrentSession(db, c.req.raw);
  if (!session) {
    const url = new URL(c.req.url);
    const target = `/login?next=${encodeURIComponent(url.pathname + url.search)}`;
    return c.redirect(target, 302);
  }
  await next();
}

// --- /api/auth sub-app

export const authRoutes = new Hono<{
  Bindings: Env;
  Variables: AppVariables;
}>();

authRoutes.post("/login", validate("json", loginSchema), async (c) => {
  const db = createDb(c.env);
  const { email, password } = c.req.valid("json");
  const normalizedEmail = email.toLowerCase();

  const rows = await db
    .select()
    .from(users)
    .where(eq(users.email, normalizedEmail))
    .limit(1)
    .all();
  const user = rows[0];

  // Always run PBKDF2, even for unknown emails (timing equalization).
  const valid = await verifyPassword(
    password,
    user?.passwordHash ?? DUMMY_PASSWORD_HASH,
  );
  if (!user || !valid) {
    return c.json(
      { error: "invalid_credentials", message: "Email o contraseña incorrectos." },
      401,
    );
  }

  const rawToken = crypto.getRandomValues(new Uint8Array(32));
  const token = toHex(rawToken);
  const now = Math.floor(Date.now() / 1000);

  await db.delete(sessions).where(lt(sessions.expiresAt, now)).run();
  await db
    .insert(sessions)
    .values({
      token: await sha256Hex(token),
      userId: user.id,
      expiresAt: now + SESSION_TTL_SECONDS,
    })
    .run();

  setSessionCookie(c, token, isSecureRequest(c.req.raw));
  return c.json({ email: user.email });
});

authRoutes.post("/logout", async (c) => {
  const db = createDb(c.env);
  const secure = isSecureRequest(c.req.raw);
  const token =
    readCookie(c.req.raw, sessionCookieName(secure)) ??
    readCookie(c.req.raw, SESSION_COOKIE_DEV) ??
    readCookie(c.req.raw, SESSION_COOKIE_PROD);
  if (token && isHex64(token)) {
    await db
      .delete(sessions)
      .where(eq(sessions.token, await sha256Hex(token)))
      .run();
  }
  setSessionCookie(c, null, secure);
  return c.json({ loggedOut: true });
});

authRoutes.get("/me", async (c) => {
  const db = createDb(c.env);
  const session = await getCurrentSession(db, c.req.raw);
  if (!session) return c.json({ error: "auth_required" }, 401);
  return c.json({ email: session.email });
});
