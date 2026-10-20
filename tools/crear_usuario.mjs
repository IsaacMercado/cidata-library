#!/usr/bin/env node
// Crea data/derived/admin.sql con un INSERT/UPDATE de usuarios.
// Usa los mismos parámetros que apps/web/src/auth.ts
// (PBKDF2-SHA256, 10.000 iteraciones).
//
// Uso (desde la raíz del repo):
//   npm run db:admin -- tu@email.com
// y luego:
//   npx wrangler d1 execute biblioteca --remote --file=./data/derived/admin.sql
//
// La contraseña se pide por stdin para no dejarla en el historial.

import { stdin, stdout } from "node:process";
import { createInterface } from "node:readline";
import { webcrypto } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// Ver la nota de presupuesto de CPU en apps/web/src/auth.ts
// (plan gratuito: 10 ms por petición).
const ITER = 10_000;

function pregunta(texto, oculto = false) {
  const rl = createInterface({
    input: stdin,
    output: oculto ? undefined : stdout,
    terminal: true,
  });
  return new Promise((res) =>
    rl.question(texto, (r) => {
      rl.close();
      res(r);
    }),
  );
}

function aBase64(bytes) {
  return Buffer.from(bytes).toString("base64");
}

async function hashPassword(password) {
  const sal = webcrypto.getRandomValues(new Uint8Array(16));
  const clave = await webcrypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = new Uint8Array(
    await webcrypto.subtle.deriveBits(
      { name: "PBKDF2", salt: sal, iterations: ITER, hash: "SHA-256" },
      clave,
      256,
    ),
  );
  return `pbkdf2$${ITER}$${aBase64(sal)}$${aBase64(bits)}`;
}

const email = (process.argv[2] ?? "").trim().toLowerCase();
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
  console.error("Uso: npm run db:admin -- email@example.com");
  process.exit(1);
}

const password = await pregunta("Contraseña: ", true);
console.log();
if (password.length < 8) {
  console.error("La contraseña debe tener al menos 8 caracteres.");
  process.exit(1);
}

const hash = await hashPassword(password);
const sql =
  "-- Usuario inicial (generado, no editar a mano).\n" +
  `INSERT INTO "usuarios" ("email", "hash") VALUES ('${email.replaceAll("'", "''")}', '${hash}')\n` +
  'ON CONFLICT("email") DO UPDATE SET "hash" = excluded."hash";\n';

const raiz = join(dirname(fileURLToPath(import.meta.url)), "..");
const destino = join(raiz, "data", "derived", "admin.sql");
mkdirSync(dirname(destino), { recursive: true });
writeFileSync(destino, sql, "utf-8");

console.log(`OK -> ${destino}`);
console.log(
  "Aplica con: npx wrangler d1 execute biblioteca --remote --file=./data/derived/admin.sql",
);
