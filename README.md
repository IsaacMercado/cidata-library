# Biblioteca

Catálogo de biblioteca migrado desde Microsoft Access y desplegado en
**Cloudflare Workers + D1**.

- **Consulta pública**: listado, ficha y búsqueda de texto completo (FTS5,
  insensible a tildes).
- **Escritura con sesión**: crear, editar y eliminar registros (cookie
  `httpOnly`, sesiones en D1, PBKDF2 con WebCrypto).
- **Sin servidores que mantener**: Worker, assets estáticos y base D1.
- **ETL en Python** independiente del Worker para extraer Access y cargar los
  datos (útil mientras la base definitiva no está lista).

## Estructura

```text
.
├── apps/
│   └── web/                    # Worker de Cloudflare
│       ├── src/                # Hono + Drizzle + auth + FTS
│       ├── public/             # HTML/CSS/JS estáticos
│       ├── migrations/         # Migraciones D1 (Wrangler + Drizzle)
│       ├── test/               # Tests unitarios (Vitest)
│       ├── wrangler.jsonc      # Configuración del Worker y D1
│       └── package.json
├── tools/
│   ├── etl/                    # Proyecto Python/uv: Access -> SQLite -> D1
│   │   └── src/biblioteca/
│   └── crear_usuario.mjs       # Genera SQL para el usuario administrador
├── data/                       # Datos locales (IGNORADO por git)
│   ├── biblioteca.accdb
│   └── derived/                # CSV, SQLite, seed.sql, admin.sql
├── .github/workflows/          # CI y despliegue automático
└── package.json                # Workspace npm y scripts raíz
```

`data/` **nunca se versiona**: contiene la base Access, datos personales y
seeds generados.

## Requisitos

- Node.js 20+ y npm 10+
- Python 3.12+ y [uv](https://docs.astral.sh/uv/)
- Cuenta de Cloudflare

## Puesta en marcha

### 1. Dependencias

```sh
npm install
uv sync --project tools/etl
```

### 2. Crear la base D1

```sh
cd apps/web
npx wrangler login
npx wrangler d1 create biblioteca
```

Copia el `database_id` que imprime Wrangler en
`apps/web/wrangler.jsonc` y ejecuta de nuevo los tipos:

```sh
npm run cf-typegen
```

### 3. Migrar y cargar datos en local

Desde la raíz:

```sh
npm run db:migrate:local

# Access -> data/derived/{biblioteca.sqlite,biblioteca.csv,schema.sql}
npm run data:extract
# SQLite -> data/derived/seed.sql
npm run data:sql
# Subir a la D1 local
npm run data:upload -- --local
```

El comando `data:extract` espera `data/biblioteca.accdb`. Puedes pasar otra
ruta:

```sh
uv run --project tools/etl biblioteca-etl export /ruta/a/otra.accdb data/derived
```

### 4. Usuario administrador

```sh
npm run db:admin -- tu@email.com
cd apps/web
npx wrangler d1 execute biblioteca --local --file=../../data/derived/admin.sql
```

La contraseña se pide por consola y nunca se guarda en claro.

### 5. Desarrollo

```sh
npm run dev
# http://localhost:8787
```

## Datos: base anterior y base nueva

El contrato es la tabla `Biblioteca` con las mismas columnas. Mientras no
tengas los datos definitivos:

1. Reemplaza `data/biblioteca.accdb` (o pasa otra ruta a `export`).
2. Ejecuta `npm run data:extract && npm run data:sql`.
3. Sube con `npm run data:upload -- --remote`.

La carga usa `INSERT ... ON CONFLICT("ID") DO UPDATE`:

- Es **idempotente**: puedes repetirla sin duplicar filas.
- Actualiza por `ID`; si la base nueva usa otros IDs para los mismos libros,
  revisa el mapeo antes de subir.
- `--truncate` vacía la tabla antes de cargar (destructivo; úsalo solo si el
  catálogo anterior debe reemplazarse por completo).
- Los triggers de FTS5 mantienen el índice automáticamente.

Para subir por API HTTP (servidores/CI) en lugar de Wrangler:

```sh
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
export D1_DATABASE_ID=...   # database_id de apps/web/wrangler.jsonc
npm run data:upload -- --remote --via api
```

Más detalles en [`tools/etl/README.md`](tools/etl/README.md).

## Despliegue en Cloudflare

### Migraciones y primer despliegue manual

```sh
npm run db:migrate:remote
npm run data:upload -- --remote
npm run deploy
```

Aplica el usuario administrador remoto:

```sh
cd apps/web
npx wrangler d1 execute biblioteca --remote --file=../../data/derived/admin.sql
```

### Despliegue automático con GitHub Actions

El workflow `.github/workflows/deploy.yml` se ejecuta al hacer push a `main`
(o manualmente desde **Actions → Deploy production**):

1. `npm ci`
2. typecheck + bundle de prueba
3. tests
4. `wrangler d1 migrations apply biblioteca --remote`
5. `wrangler deploy`

Configura estos **secrets** en el repositorio
(**Settings → Secrets and variables → Actions**):

| Secret | Valor |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | Token con permisos de Workers Scripts:Edit y D1:Edit |
| `CLOUDFLARE_ACCOUNT_ID` | ID de la cuenta de Cloudflare |

El token se crea en **My Profile → API Tokens**. La plantilla
“Edit Cloudflare Workers” sirve; añade **D1:Edit** si no lo incluye.

El job usa el environment `production` de GitHub. Puedes añadir reglas de
protección (aprobación manual) en **Settings → Environments** sin cambiar el
workflow.

`.github/workflows/ci.yml` ejecuta typecheck, tests y lint de Python en cada
push y pull request. No despliega desde PRs.

## Scripts

| Script | Qué hace |
| --- | --- |
| `npm run dev` | Worker en local con D1 local. |
| `npm run check` | Typecheck + `wrangler deploy --dry-run`. |
| `npm test` | Tests unitarios del Worker. |
| `npm run deploy` | Despliega el Worker. |
| `npm run cf-typegen` | Regenera `worker-configuration.d.ts` desde `wrangler.jsonc`. |
| `npm run db:migrate:local` | Aplica migraciones a D1 local. |
| `npm run db:migrate:remote` | Aplica migraciones a D1 remoto. |
| `npm run data:extract` | Access → CSV/SQLite/esquema. |
| `npm run data:sql` | SQLite → `seed.sql` idempotente. |
| `npm run data:upload -- --local\|--remote` | Carga a D1. |
| `npm run db:admin -- email` | Genera `data/derived/admin.sql`. |

## Migraciones y esquema

- El esquema Drizzle vive en `apps/web/src/db/schema.ts`.
- `npm run db:generate` genera una migración nueva en `apps/web/migrations/`.
- `npm run db:fts` crea una migración custom (para SQL de FTS5/triggers).
- Revisa siempre el SQL generado y commitéalo.
- `wrangler d1 migrations apply` registra las migraciones aplicadas en la
  tabla `d1_migrations`. No edites migraciones ya aplicadas: crea una nueva.
- `apps/web/migrations/meta/` es el historial interno de Drizzle; Wrangler lo
  ignora.

Si ya tenías una D1 creada antes de adoptar `wrangler d1 migrations apply`,
marca las migraciones existentes como aplicadas antes de seguir (o recrea la
base). Para un entorno local puedes borrar
`apps/web/.wrangler/state/v3/d1` y volver a migrar.

## Búsqueda

- **Simple**: palabras con AND implícito, insensible a mayúsculas y tildes
  (`rustica` encuentra “Rústico”); los operadores se neutralizan.
- **Avanzada (FTS5)**: frases `"…"`, `AND/OR/NOT`, prefijos `term*` y filtros
  por columna `{Titulo Autor} : …`. Ranking BM25 y fragmento resaltado.
- Se puede limitar con las casillas de campo de la página.

## Seguridad

- Las contraseñas se guardan como `pbkdf2$iteraciones$sal$hash`
  (PBKDF2-SHA256, 10.000 iteraciones, pensado para el límite de CPU del plan
  gratuito). Ajusta `PBKDF2_ITER` en `apps/web/src/auth.ts` y en
  `tools/crear_usuario.mjs` si cambias de plan.
- Las sesiones guardan solo el SHA-256 del token; la cookie es `httpOnly`,
  `SameSite=Lax` y `Secure` en HTTPS.
- `data/derived/admin.sql` contiene un hash de contraseña: no lo compartas ni
  lo versiones (ya está ignorado).
- Las rutas `/editar` y `/nuevo` (y sus `.html`) están protegidas por el
  Worker; no las quites de `run_worker_first` en `wrangler.jsonc`.
