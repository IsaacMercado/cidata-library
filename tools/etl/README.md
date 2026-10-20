# ETL de la biblioteca (Python)

Herramientas para extraer la base Microsoft Access y cargar los datos en
Cloudflare D1. **No forma parte del Worker**: es un proyecto `uv` independiente.

## Requisitos

- Python 3.12+
- [uv](https://docs.astral.sh/uv/)
- Node/npm (solo para la subida con Wrangler o el script de usuarios)

## Flujo recomendado

Desde la raíz del repositorio:

```sh
# 1) Access -> data/derived/{biblioteca.csv,biblioteca.sqlite,schema.sql}
npm run data:extract

# 2) SQLite -> data/derived/seed.sql (idempotente por ID)
npm run data:sql

# 3) Subir a D1 remoto con Wrangler (sesión ya iniciada)
npm run data:upload -- --remote
```

Para probar primero contra la D1 local:

```sh
npm run db:migrate:local
uv run --project tools/etl biblioteca-etl upload --local
```

## Comandos

| Comando | Qué hace |
| --- | --- |
| `biblioteca-etl export [accdb] [salida]` | Access → CSV, SQLite y `schema.sql`. |
| `biblioteca-etl sql [sqlite] [salida]` | SQLite → SQL con `INSERT ... ON CONFLICT`. |
| `biblioteca-etl upload --remote` | Carga en D1 remoto usando `wrangler`. |
| `biblioteca-etl upload --local` | Carga en la D1 local de Wrangler. |
| `biblioteca-etl upload --remote --method api` | Carga por API HTTP (CI/servidores). |
| `biblioteca-etl upload --dry-run archivo.sql` | Genera el SQL sin subir. |
| `biblioteca-etl all` | `export` + `sql` en un paso. |
| `biblioteca-gui` | Réplica exploratoria del formulario en Tkinter. |
| `biblioteca-web` | Réplica HTML autocontenida del formulario. |

## Subida por API

```sh
export CLOUDFLARE_API_TOKEN=...
export CLOUDFLARE_ACCOUNT_ID=...
export D1_DATABASE_ID=...   # database_id de apps/web/wrangler.jsonc
uv run --project tools/etl biblioteca-etl upload --remote --method api
```

La carga por API envía una sentencia cada vez (lotes de ~100 filas o 90 KB) y
reintenta con backoff en errores 429/5xx.

## Cuándo llegue la base nueva

El contrato es la tabla `Biblioteca` con las mismas columnas. Solo hay que:

1. Reemplazar `data/biblioteca.accdb` (o pasar otra ruta a `export`).
2. Ejecutar `npm run data:extract && npm run data:sql`.
3. Subir con `npm run data:upload -- --remote`.

El `upload` actualiza por `ID`; no duplica filas. Si la base nueva tiene IDs
distintos para los mismos libros, revisa antes el mapeo (o usa `--truncate`
solo si estás seguro de que el catálogo anterior debe reemplazarse por
completo).

Si la base nueva **no es Access** (SQL Server, MySQL, etc.), expórtala a un
SQLite con la misma tabla `Biblioteca` y las mismas columnas y salta el paso
`export`:

```sh
uv run --project tools/etl biblioteca-etl sql /ruta/biblioteca.sqlite
uv run --project tools/etl biblioteca-etl upload /ruta/biblioteca.sqlite --remote
```
