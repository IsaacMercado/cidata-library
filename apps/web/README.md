# Worker de la biblioteca

Worker de Cloudflare con Hono + Drizzle + D1. La documentación general
(instalación, ETL, despliegue automático) está en el
[README raíz](../../README.md).

## Comandos

```sh
npm run dev             # wrangler dev (D1 local)
npm run check           # tsc + wrangler deploy --dry-run
npm test                # Vitest
npm run deploy          # wrangler deploy
npm run cf-typegen      # genera worker-configuration.d.ts
```

## Estructura

- `src/index.ts`: rutas de la API y páginas protegidas.
- `src/auth.ts`: login/logout, sesiones en D1 y middleware.
- `src/db/schema.ts`: tablas Drizzle (`Biblioteca`, `usuarios`, `sesiones`).
- `src/fts.ts`: traducción de la búsqueda simple/avanzada a FTS5.
- `src/validacion.ts`: esquemas zod y errores 400 en español.
- `public/`: HTML/CSS/JS sin build.
- `migrations/`: migraciones D1. `0002_fts.sql` es custom (tabla virtual y
  triggers); el resto las genera Drizzle.

## Notas

- `wrangler.jsonc` incluye `run_worker_first` para `/api/*`, `/editar*` y
  `/nuevo*`; sin eso las páginas de escritura se servirían como assets
  públicos.
- Los enlaces usan rutas limpias (`/libro?id=…`, `/editar`, `/login`). Los
  `.html` antiguos siguen funcionando: el Worker los protege y Cloudflare los
  redirige a la ruta limpia.
- `worker-configuration.d.ts` se genera con `wrangler types`; vuelve a
  ejecutarlo después de cambiar bindings en `wrangler.jsonc`.
