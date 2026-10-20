#!/usr/bin/env node
// Create data/derived/admin.sql with an INSERT/UPDATE for a user.
// Uses the same parameters as apps/web/src/auth.ts
// (PBKDF2-SHA256, 10,000 iterations).
//
// Usage (from the repository root):
//   npm run db:admin -- you@email.com
// then:
//   npx wrangler d1 execute biblioteca --remote --file=./data/derived/admin.sql
//
// The password is read from stdin so it never ends up in shell history.

import { stdin, stdout } from "node:process";
import { createInterface } from "node:readline";
import { webcrypto } from "node:crypto";
import { mkdirSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

// See the CPU budget note in apps/web/src/auth.ts
// (free plan: 10 ms per request).
const PBKDF2_ITERATIONS = 10_000;

function ask(prompt, hidden = false) {
  const readline = createInterface({
    input: stdin,
    output: hidden ? undefined : stdout,
    terminal: true,
  });
  return new Promise((resolve) =>
    readline.question(prompt, (answer) => {
      readline.close();
      resolve(answer);
    }),
  );
}

function toBase64(bytes) {
  return Buffer.from(bytes).toString("base64");
}

async function hashPassword(password) {
  const salt = webcrypto.getRandomValues(new Uint8Array(16));
  const key = await webcrypto.subtle.importKey(
    "raw",
    new TextEncoder().encode(password),
    "PBKDF2",
    false,
    ["deriveBits"],
  );
  const bits = new Uint8Array(
    await webcrypto.subtle.deriveBits(
      { name: "PBKDF2", salt, iterations: PBKDF2_ITERATIONS, hash: "SHA-256" },
      key,
      256,
    ),
  );
  return `pbkdf2$${PBKDF2_ITERATIONS}$${toBase64(salt)}$${toBase64(bits)}`;
}

const email = (process.argv[2] ?? "").trim().toLowerCase();
if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
  console.error("Usage: npm run db:admin -- email@example.com");
  process.exit(1);
}

const password = await ask("Contraseña: ", true);
console.log();
if (password.length < 8) {
  console.error("La contraseña debe tener al menos 8 caracteres.");
  process.exit(1);
}

const hash = await hashPassword(password);
const sql =
  "-- Initial user (generated, do not edit by hand).\n" +
  `INSERT INTO "usuarios" ("email", "hash") VALUES ('${email.replaceAll("'", "''")}', '${hash}')\n` +
  'ON CONFLICT("email") DO UPDATE SET "hash" = excluded."hash";\n';

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const destination = join(root, "data", "derived", "admin.sql");
mkdirSync(dirname(destination), { recursive: true });
writeFileSync(destination, sql, "utf-8");

console.log(`OK -> ${destination}`);
console.log(
  "Apply with: npx wrangler d1 execute biblioteca --remote --file=./data/derived/admin.sql",
);
