# Biblioteca CIDATA

Catálogo en línea de la biblioteca **CIDATA**, migrado desde Microsoft Access y
desplegado en **Cloudflare Workers + D1**.

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
├── src/                        # Hono + Drizzle + auth + FTS
├── public/                     # HTML/CSS/JS estáticos
├── migrations/                 # Migraciones D1 (Wrangler + Drizzle)
├── test/                       # Tests unitarios (Vitest)
├── tools/
│   ├── etl/                    # Proyecto Python/uv: Access -> SQLite -> D1
│   │   └── src/biblioteca/
│   └── create_user.mjs         # Genera SQL para el usuario administrador
├── data/                       # Datos locales (IGNORADO por git)
│   ├── biblioteca.accdb
│   └── derived/                # CSV, SQLite, seed.sql, admin.sql
├── .github/workflows/          # CI y despliegue automático
├── wrangler.jsonc              # Configuración del Worker y D1
├── drizzle.config.ts
├── tsconfig.json
└── package.json                # Dependencias y scripts del Worker + ETL
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
npx wrangler login
npx wrangler d1 create biblioteca
```

Copia el `database_id` que imprime Wrangler en `wrangler.jsonc` y ejecuta de
nuevo los tipos:

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
npx wrangler d1 execute biblioteca --local --file=./data/derived/admin.sql
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
export D1_DATABASE_ID=...   # database_id de wrangler.jsonc
npm run data:upload -- --remote --method api
```

Más detalles en [`tools/etl/README.md`](tools/etl/README.md).

## Despliegue en Cloudflare

Este proyecto es un **Worker** con assets estáticos y D1, no un sitio de
Cloudflare Pages. El Worker vive en la **raíz del repositorio**, que es la
estructura que Cloudflare detecta por defecto: `wrangler.jsonc`, `src/`,
`public/` y `package.json` están en la raíz. Por eso `npx wrangler deploy`
funciona directamente, sin configurar una subcarpeta.

La integración Git de Cloudflare no es un producto aparte: está en el Worker,
en **Settings → Builds**. No busques un menú llamado “Workers Builds”.

`wrangler.jsonc` ya contiene el `database_id` de la base D1 y el nombre
`cidata-library`, que coincide con el Worker conectado a Git. Si creas otra
base u otro Worker, actualiza esos valores.

### Despliegue directo desde tu máquina

No necesitas GitHub Actions ni Pages:

```sh
npx wrangler login
npm run db:migrate:remote
npm run data:upload -- --remote
npm run deploy
```

`npm run deploy` ejecuta `wrangler deploy` en la raíz y usa el `database_id`
de `wrangler.jsonc`.

Aplica el usuario administrador remoto:

```sh
npm run db:admin -- tu@email.com
npx wrangler d1 execute biblioteca --remote --file=./data/derived/admin.sql
```

### Despliegue automático desde Git

En el Worker `cidata-library` → **Settings → Builds**:

- **Root directory:** `/`
- **Build command:** `npm run build` (opcional; también puede quedar vacío)
- **Deploy command:** `npx wrangler deploy` (el valor por defecto) o
  `npm run deploy`

Las migraciones **no** se ejecutan en el build. Aplícalas manualmente antes de
desplegar un cambio de esquema:

```sh
npm run db:migrate:remote
```

Si quieres que el build también migre, el token de build necesita permiso de
D1 y el deploy command sería
`npm run db:migrate:remote && npm run deploy`. Para este proyecto las
migraciones se aplican a mano, así que el deploy command simple es suficiente.

### GitHub Actions (opcional)

El workflow `.github/workflows/deploy.yml` existe como alternativa de CI/CD,
pero **no es necesario** y no es la ruta recomendada. Está configurado solo
para ejecución manual (`workflow_dispatch`), así que no se dispara en cada
push. Si no lo quieres, se puede eliminar sin afectar al despliegue directo ni
a la integración Git del Worker.

Si lo usas, configura estos secrets en GitHub:

| Secret | Valor |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | Token con permisos de Workers Scripts:Edit y D1:Edit |
| `CLOUDFLARE_ACCOUNT_ID` | ID de la cuenta de Cloudflare |

El token se crea en **My Profile → API Tokens**. La plantilla
“Edit Cloudflare Workers” sirve; añade **D1:Edit** si no lo incluye. El job usa
el environment `production` de GitHub; puedes añadir aprobación manual en
**Settings → Environments**.

`.github/workflows/ci.yml` ejecuta typecheck, tests y lint de Python en cada
push y pull request. No despliega desde PRs.

## Scripts

| Script | Qué hace |
| --- | --- |
| `npm run dev` | Worker en local con D1 local. |
| `npm run build` | Igual que `npm run check`; es el build command de Cloudflare. |
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

- El esquema Drizzle vive en `src/db/schema.ts`.
- `npm run db:generate` genera una migración nueva en `migrations/`.
- `npm run db:fts` crea una migración custom (para SQL de FTS5/triggers).
- Revisa siempre el SQL generado y commitéalo.
- `wrangler d1 migrations apply` registra las migraciones aplicadas en la
  tabla `d1_migrations`. No edites migraciones ya aplicadas: crea una nueva.
- `migrations/meta/` es el historial interno de Drizzle; Wrangler lo
  ignora.

Si ya tenías una D1 creada antes de adoptar `wrangler d1 migrations apply`,
marca las migraciones existentes como aplicadas antes de seguir (o recrea la
base). Para un entorno local puedes borrar
`.wrangler/state/v3/d1` y volver a migrar.

## Búsqueda

- **Simple**: palabras con AND implícito, insensible a mayúsculas y tildes
  (`rustica` encuentra “Rústico”); los operadores se neutralizan.
- **Avanzada (FTS5)**: frases `"…"`, `AND/OR/NOT`, prefijos `term*` y filtros
  por columna `{Titulo Autor} : …`. Ranking BM25 y fragmento resaltado.
- Se puede limitar con las casillas de campo de la página.

## Seguridad

### Sesiones: no hay `secret_key`

Este proyecto **no usa cookies firmadas ni JWT**. Usa sesiones opacas del lado
del servidor, así que no necesita una clave secreta para firmar la cookie:

1. En el login (`src/auth.ts`) se generan 32 bytes aleatorios con
   `crypto.getRandomValues` (256 bits).
2. El token en claro va en la cookie `httpOnly`; en D1 se guarda únicamente su
   SHA-256 (`sesiones.token`).
3. En cada petición se hashea el token de la cookie y se busca esa fila en D1.
   Si existe, no ha expirado y el usuario existe, la sesión es válida.
4. El logout borra la fila; también se puede revocar una sesión borrando su
   fila en D1.

No hay firma que verificar, por eso no hay `SESSION_SECRET`. La autoridad es la
fila de D1, no la integridad criptográfica de la cookie. Ventajas: el token no
se guarda en claro y las sesiones se pueden revocar. Si en el futuro se
quisiera una sesión *stateless* firmada (por ejemplo JWT), sí habría que crear
un secreto con `npx wrangler secret put SESSION_SECRET`; ese sería otro diseño,
con revocación más difícil.

La cookie se llama `biblio_session` en HTTP local y
`__Host-biblio_session` en producción HTTPS. `__Host-` exige `Secure`, `Path=/`
y ningún atributo `Domain`; además se usa `HttpOnly` y `SameSite=Lax`.

### CSRF y escritura

- Las rutas de escritura (`POST`, `PUT`, `DELETE`) exigen sesión válida.
- Un middleware en `src/index.ts` rechaza peticiones con `Origin` de
  otro sitio y con `Sec-Fetch-Site` distinto de `same-origin`/`none`.
- La API espera `Content-Type: application/json`; un formulario cross-site
  simple no puede enviar JSON sin pasar por un preflight CORS que el Worker no
  autoriza.
- `SameSite=Lax` evita el envío normal de la cookie en peticiones cross-site.
- Las páginas `/editar` y `/nuevo` (y sus `.html`) están protegidas en el
  Worker; no las quites de `run_worker_first` en `wrangler.jsonc`.

### Contraseñas

- Se guardan como `pbkdf2$iteraciones$sal$hash` (PBKDF2-SHA256, 10.000
  iteraciones). El login ejecuta PBKDF2 incluso si el email no existe, para no
  filtrar qué cuentas existen por diferencias de tiempo.
- 10.000 iteraciones es un compromiso con el límite de CPU del plan gratuito
  de Workers (10 ms por petición). Si pasas a un plan de pago, sube
  `PBKDF2_ITERATIONS` en `src/auth.ts` y en
  `tools/create_user.mjs` a la vez, y regenera los hashes existentes.
- El login no tiene rate limiting propio. Para producción se recomienda añadir
  Cloudflare Rate Limiting/WAF o Turnstile, o poner la aplicación detrás de
  Cloudflare Access si solo la usa el personal de la biblioteca.
- `data/derived/admin.sql` contiene un hash de contraseña: no lo compartas ni
  lo versiones (ya está ignorado).

### Secretos de despliegue

Los únicos secretos son los de la cuenta de Cloudflare para CI:

| Secret | Uso |
| --- | --- |
| `CLOUDFLARE_API_TOKEN` | Workers Scripts:Edit + D1:Edit |
| `CLOUDFLARE_ACCOUNT_ID` | ID de la cuenta |

Se configuran en GitHub (**Settings → Secrets and variables → Actions**), no
en el código. No hay ningún `SESSION_SECRET` que configurar con el diseño
actual.
