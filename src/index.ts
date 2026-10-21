import { count, eq, getTableColumns, sql } from "drizzle-orm";
import { Hono } from "hono";
import { authRoutes, requireAuth, requireAuthPage } from "./auth";
import { createDb, type AppVariables, type Env } from "./db/client";
import { books, FTS_COLUMNS } from "./db/schema";
import { buildAdvancedMatch, buildSimpleMatch } from "./fts";
import {
  bookInputSchema,
  idParamSchema,
  listQuerySchema,
  validate,
} from "./validation";

// Form descriptors (same order and labels as the original Access form).
const FIELDS = [
  { key: "id", column: "ID", label: "ID", multiline: false, readOnly: true },
  { key: "callNumber", column: "Cota", label: "Cota", multiline: false, readOnly: false },
  { key: "title", column: "Titulo", label: "Titulo", multiline: false, readOnly: false },
  { key: "coauthor", column: "Coautor", label: "Coautor", multiline: false, readOnly: false },
  { key: "subject", column: "Tema o Materia", label: "Tema o Materia", multiline: false, readOnly: false },
  { key: "series", column: "Series", label: "Series", multiline: false, readOnly: false },
  { key: "pages", column: "Paginas", label: "Paginas", multiline: false, readOnly: false },
  { key: "isbn", column: "ISBN", label: "ISBN", multiline: false, readOnly: false },
  { key: "notes", column: "Notas", label: "Notas", multiline: true, readOnly: false },
  { key: "cidaCode", column: "Codigo CIDA", label: "Codigo CIDA", multiline: false, readOnly: false },
  { key: "copies", column: "Ejemplares", label: "Ejemplares", multiline: false, readOnly: false },
  { key: "unitPrice", column: "Precio Unidad", label: "Precio Unidad", multiline: false, readOnly: false },
  { key: "totalPrice", column: "Precio Total", label: "Precio Total", multiline: false, readOnly: false },
  { key: "donation", column: "Donacion", label: "Donacion", multiline: false, readOnly: false },
  { key: "catalogText", column: "Texto Ficha", label: "Texto Ficha:", multiline: true, readOnly: false },
  { key: "author", column: "Autor", label: "Autor:", multiline: false, readOnly: false },
  { key: "binding", column: "Lujo/Rústico", label: "Lujo/Rústico:", multiline: false, readOnly: false },
] as const;

const app = new Hono<{ Bindings: Env; Variables: AppVariables }>();

// Basic CSRF defense for state-changing requests. Browsers send Origin on
// cross-site POST/PUT/DELETE; JSON bodies also force a CORS preflight that this
// Worker never approves. Non-browser clients without Origin keep working.
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

app.use("*", async (c, next) => {
  if (!SAFE_METHODS.has(c.req.method)) {
    const origin = c.req.header("Origin");
    const requestOrigin = new URL(c.req.url).origin;
    if (origin && origin !== requestOrigin) {
      return c.json(
        { error: "invalid_origin", message: "Origen no permitido." },
        403,
      );
    }
    const fetchSite = c.req.header("Sec-Fetch-Site");
    if (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none") {
      return c.json(
        { error: "invalid_origin", message: "Origen no permitido." },
        403,
      );
    }
  }
  await next();
});

app.route("/api/auth", authRoutes);

app.get("/api/meta", (c) => {
  // The descriptors are static for a given deployment; let the browser reuse
  // them instead of paying a Worker round trip on every page load.
  c.header("Cache-Control", "public, max-age=3600");
  return c.json({
    title: "Biblioteca CIDATA",
    organization: "CIDATA",
    fields: FIELDS,
    ftsColumns: FTS_COLUMNS,
    limits: { likeBytes: 50, maxPageSize: 100 },
  });
});

app.get("/api/libros", validate("query", listQuerySchema), async (c) => {
  const db = createDb(c.env);
  const { q, mode, fields, order, page, limit } = c.req.valid("query");
  const offset = (page - 1) * limit;
  const selectedFields = fields
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);

  // No search: paginated listing (ORDER BY can use the indexes).
  if (!q.trim()) {
    const [rows, totalRows] = await Promise.all([
      db
        .select()
        .from(books)
        .orderBy(books[order])
        .limit(limit)
        .offset(offset)
        .all(),
      db.select({ n: count() }).from(books).all(),
    ]);
    const total = totalRows[0]?.n ?? 0;
    return c.json({
      items: rows,
      total,
      page,
      pages: Math.ceil(total / limit),
      limit,
    });
  }

  // With search: FTS5 with BM25 ranking (accent-insensitive).
  const simpleMatch = buildSimpleMatch(q, selectedFields);
  const match =
    mode === "advanced"
      ? buildAdvancedMatch(q, selectedFields)
      : simpleMatch;
  if (!match) return c.json({ error: "no_terms" }, 400);

  const runSearch = async (expression: string) => {
    const rank = sql<number>`bm25("biblioteca_fts")`;
    // Index 6 = "Texto Ficha" (virtual table column order). Control characters
    // mark the highlighted span; the client escapes the snippet and then turns
    // them into <mark> tags, so catalog text can never inject HTML.
    const fragment = sql<string>`snippet("biblioteca_fts", 6, '\u0001', '\u0002', '…', 12)`;
    // FTS5 forbids bm25()/snippet() in queries that also use window functions,
    // so the count stays a separate query. Running both in parallel keeps the
    // extra D1 round trip from adding to the response time.
    const [rows, totalRows] = await Promise.all([
      db
        .select({ ...getTableColumns(books), rank, fragment })
        .from(books)
        // FTS5 requires the actual table name (not an alias) next to MATCH.
        .innerJoin(
          sql`"biblioteca_fts"`,
          sql`"Biblioteca"."ID" = "biblioteca_fts"."rowid"`,
        )
        .where(sql`"biblioteca_fts" MATCH ${expression}`)
        .orderBy(order === "id" ? rank : books[order])
        .limit(limit)
        .offset(offset)
        .all(),
      db.all<{ n: number }>(
        sql`SELECT COUNT(*) AS "n" FROM "biblioteca_fts" WHERE "biblioteca_fts" MATCH ${expression}`,
      ),
    ]);
    return { rows, total: totalRows[0]?.n ?? 0 };
  };

  try {
    const result = await runSearch(match).catch(async (error) => {
      // Advanced syntax can be temporarily invalid while the user is still
      // typing (an open quote, a trailing AND, parentheses…). Retry with the
      // safe word-based expression so the search box never dead-ends.
      if (mode === "advanced" && simpleMatch && simpleMatch !== match) {
        return runSearch(simpleMatch);
      }
      throw error;
    });
    return c.json({
      items: result.rows,
      total: result.total,
      page,
      pages: Math.ceil(result.total / limit),
      limit,
    });
  } catch (error) {
    console.error("FTS5:", error);
    return c.json(
      {
        error: "invalid_expression",
        message: "Expresión de búsqueda no válida.",
      },
      400,
    );
  }
});

app.get("/api/libros/:id", validate("param", idParamSchema), async (c) => {
  const db = createDb(c.env);
  const { id } = c.req.valid("param");
  const rows = await db
    .select()
    .from(books)
    .where(eq(books.id, id))
    .limit(1)
    .all();
  const book = rows[0];
  if (!book) return c.json({ error: "not_found" }, 404);
  return c.json(book);
});

/** '' -> null; the zod schema already guarantees known keys and types. */
function toRecord(
  values: Record<string, string | number | undefined>,
): Record<string, string | null> {
  const record: Record<string, string | null> = {};
  for (const [key, value] of Object.entries(values)) {
    record[key] =
      value === "" || value === undefined ? null : String(value);
  }
  return record;
}

app.post(
  "/api/libros",
  requireAuth,
  validate("json", bookInputSchema),
  async (c) => {
    const db = createDb(c.env);
    const rows = await db
      .insert(books)
      .values(toRecord(c.req.valid("json")) as typeof books.$inferInsert)
      .returning({ id: books.id })
      .all();
    const created = rows[0];
    if (!created) return c.json({ error: "insert_failed" }, 500);
    return c.json(created, 201);
  },
);

app.put(
  "/api/libros/:id",
  requireAuth,
  validate("param", idParamSchema),
  validate("json", bookInputSchema),
  async (c) => {
    const db = createDb(c.env);
    const { id } = c.req.valid("param");
    const rows = await db
      .update(books)
      .set(toRecord(c.req.valid("json")) as Partial<typeof books.$inferInsert>)
      .where(eq(books.id, id))
      .returning({ id: books.id })
      .all();
    const updated = rows[0];
    if (!updated) return c.json({ error: "not_found" }, 404);
    return c.json(updated);
  },
);

app.delete(
  "/api/libros/:id",
  requireAuth,
  validate("param", idParamSchema),
  async (c) => {
    const db = createDb(c.env);
    const { id } = c.req.valid("param");
    const rows = await db
      .delete(books)
      .where(eq(books.id, id))
      .returning({ id: books.id })
      .all();
    if (!rows[0]) return c.json({ error: "not_found" }, 404);
    return c.json({ deleted: true });
  },
);

// Write pages: session required, otherwise redirect to login. Served from the
// ASSETS binding, which requires run_worker_first in wrangler.jsonc. Both the
// clean route (/editar) and the legacy .html route are accepted.
for (const page of ["/editar", "/editar.html", "/nuevo", "/nuevo.html"]) {
  app.get(page, requireAuthPage, async (c) => {
    return c.env.ASSETS.fetch(c.req.raw);
  });
}

app.notFound((c) => c.json({ error: "not_found" }, 404));

export default app;
