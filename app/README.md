# Biblioteca en línea (Worker + D1)

App de la biblioteca migrada desde Access: lectura pública (listado, ficha y
búsqueda avanzada FTS5) y escritura con login (sesiones en D1 + cookie
httpOnly). Sin dependencias pesadas: **Drizzle**, **Hono**, **zod** y
`@hono/zod-validator`; el hash es PBKDF2 con WebCrypto.

- Esquema Drizzle: `src/db/schema.ts` (`Biblioteca` + `usuarios` + `sesiones`).
- API (`src/index.ts`): `GET /api/libros` (listado/FTS), `GET /api/libros/:id`,
  `POST/PUT/DELETE` con sesión, `GET /api/meta`, `POST /api/auth/login|logout`,
  `GET /api/auth/yo`. Toda la entrada se valida con **zod** (400 en español).
- Páginas: `index.html` (buscar), `libro.html` (ficha), `login.html`,
  `editar.html` y `nuevo.html` (estas dos exigen sesión: sin cookie redirigen
  al login; requiere `run_worker_first` en `wrangler.jsonc`, ya configurado).
- Migraciones: `drizzle/0001_init.sql` (tabla + 6 índices),
  `drizzle/0002_fts.sql` (FTS5 + triggers + rebuild),
  `drizzle/0003_auth.sql` (usuarios/sesiones). No re-apliques ficheros ya
  aplicados: usa `db:apply` con el fichero concreto.

## 1. Crear la base D1

```sh
cd app
npx wrangler login
npx wrangler d1 create biblioteca
```

Pega el `database_id` en `wrangler.jsonc`.

## 2. Migrar y cargar datos (orden)

```sh
npm run db:apply:local -- ./drizzle/0001_init.sql
npm run db:apply:local -- ./drizzle/0002_fts.sql
npm run db:apply:local -- ./drizzle/0003_auth.sql
npm run seed:dump            # genera seed/seed.sql (4545 filas, gitignored)
npm run db:seed:local
npm run db:usuario -- tu@email.com   # genera seed/admin.sql (gitignored)
npx wrangler d1 execute biblioteca --local --file=./seed/admin.sql
npx wrangler dev             # http://localhost:8787
```

Repite con `db:apply:remote` / `db:seed:remote` y luego `npm run deploy`.

## 3. Autenticación

- Tablas `usuarios` (email único, hash `pbkdf2$iter$sal$hash`) y `sesiones`
  (sha256 del token, expira en 7 días). En BD nunca hay contraseñas ni
  tokens en claro.
- Cookie `biblio_sesion`: httpOnly, `SameSite=Lax`, `Secure` en https.
- Credenciales erróneas responden 401 genérico (no revela si existe el email).
- Hash PBKDF2-SHA256 a **10.000 iteraciones** (~2-5 ms CPU): el plan gratuito
  corta cada petición a los 10 ms de CPU. Solo se paga en el login (sesión de
  7 días); validar sesión es 1 lectura D1 + 1 sha256. Usa una contraseña
  administradora larga: con 10k iteraciones, una clave débil sería vulnerable
  solo si alguien obtiene una copia de la BD.

## 4. Búsqueda avanzada

- **Simple**: palabras con AND implícito, insensible a tildes
  (`rustica` encuentra "Rústico"), operadores neutralizados.
- **Avanzada (FTS5)**: frases `"…"`, `AND/OR/NOT`, prefijos `term*` y filtros
  por columna `{Titulo Autor} : …`. Ranking BM25 + fragmento resaltado.
- Opcionalmente se limita con las casillas de campo de la página.
