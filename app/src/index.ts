import { count, eq, getTableColumns, sql } from "drizzle-orm";
import { Hono } from "hono";
import { authApp, requireAuth, requireAuthPagina } from "./auth";
import { crearDb, type AppVariables, type Env } from "./db/client";
import { biblioteca, COLUMNAS_FTS } from "./db/schema";
import { matchAvanzado, matchSimple } from "./fts";
import {
  esquemaId,
  esquemaLista,
  esquemaRegistro,
  validar,
} from "./validacion";

// Descriptores del formulario (mismo orden y etiquetas que el form Access).
const CAMPOS = [
  { clave: "id", columna: "ID", etiqueta: "ID", multilinea: false, soloLectura: true },
  { clave: "cota", columna: "Cota", etiqueta: "Cota", multilinea: false, soloLectura: false },
  { clave: "titulo", columna: "Titulo", etiqueta: "Titulo", multilinea: false, soloLectura: false },
  { clave: "coautor", columna: "Coautor", etiqueta: "Coautor", multilinea: false, soloLectura: false },
  { clave: "temaOMateria", columna: "Tema o Materia", etiqueta: "Tema o Materia", multilinea: false, soloLectura: false },
  { clave: "series", columna: "Series", etiqueta: "Series", multilinea: false, soloLectura: false },
  { clave: "paginas", columna: "Paginas", etiqueta: "Paginas", multilinea: false, soloLectura: false },
  { clave: "isbn", columna: "ISBN", etiqueta: "ISBN", multilinea: false, soloLectura: false },
  { clave: "notas", columna: "Notas", etiqueta: "Notas", multilinea: true, soloLectura: false },
  { clave: "codigoCida", columna: "Codigo CIDA", etiqueta: "Codigo CIDA", multilinea: false, soloLectura: false },
  { clave: "ejemplares", columna: "Ejemplares", etiqueta: "Ejemplares", multilinea: false, soloLectura: false },
  { clave: "precioUnidad", columna: "Precio Unidad", etiqueta: "Precio Unidad", multilinea: false, soloLectura: false },
  { clave: "precioTotal", columna: "Precio Total", etiqueta: "Precio Total", multilinea: false, soloLectura: false },
  { clave: "donacion", columna: "Donacion", etiqueta: "Donacion", multilinea: false, soloLectura: false },
  { clave: "textoFicha", columna: "Texto Ficha", etiqueta: "Texto Ficha:", multilinea: true, soloLectura: false },
  { clave: "autor", columna: "Autor", etiqueta: "Autor:", multilinea: false, soloLectura: false },
  { clave: "lujoRustico", columna: "Lujo/Rústico", etiqueta: "Lujo/Rústico:", multilinea: false, soloLectura: false },
] as const;

const app = new Hono<{ Bindings: Env; Variables: AppVariables }>();

app.route("/api/auth", authApp);

app.get("/api/meta", (c) => {
  return c.json({
    titulo: "Biblioteca",
    campos: CAMPOS,
    ftsColumnas: COLUMNAS_FTS,
    limites: { likeBytes: 50, paginaMax: 100 },
  });
});

app.get("/api/libros", validar("query", esquemaLista), async (c) => {
  const db = crearDb(c.env);
  const { q, modo, campos, orden, page, limit } = c.req.valid("query");
  const offset = (page - 1) * limit;
  const listaCampos = campos
    .split(",")
    .map((s) => s.trim())
    .filter(Boolean);

  // Sin busqueda: listado paginado (usa indices para el ORDER BY).
  if (!q.trim()) {
    const [filas, total] = await Promise.all([
      db
        .select()
        .from(biblioteca)
        .orderBy(biblioteca[orden])
        .limit(limit)
        .offset(offset)
        .all(),
      db.select({ n: count() }).from(biblioteca).all(),
    ]);
    const n = total[0]?.n ?? 0;
    return c.json({ items: filas, total: n, page, pages: Math.ceil(n / limit), limit });
  }

  // Con busqueda: FTS5 con ranking BM25 (insensible a tildes).
  const match =
    modo === "avanzado"
      ? matchAvanzado(q, listaCampos)
      : matchSimple(q, listaCampos);
  if (!match) return c.json({ error: "sin_terminos" }, 400);

  try {
    const rank = sql<number>`bm25("biblioteca_fts")`;
    // Indice 6 = "Texto Ficha" (orden de columnas de la tabla virtual).
    const fragmento = sql<string>`snippet("biblioteca_fts", 6, '<mark>', '</mark>', '…', 12)`;
    const filas = await db
      .select({ ...getTableColumns(biblioteca), rank, fragmento })
      .from(biblioteca)
      // FTS5 exige el NOMBRE de la tabla (no un alias) junto a MATCH.
      .innerJoin(
        sql`"biblioteca_fts"`,
        sql`"Biblioteca"."ID" = "biblioteca_fts"."rowid"`,
      )
      .where(sql`"biblioteca_fts" MATCH ${match}`)
      .orderBy(orden === "id" ? rank : biblioteca[orden])
      .limit(limit)
      .offset(offset)
      .all();
    const total = await db.all<{ n: number }>(
      sql`SELECT COUNT(*) AS "n" FROM "biblioteca_fts" WHERE "biblioteca_fts" MATCH ${match}`,
    );
    const n = total[0]?.n ?? 0;
    return c.json({ items: filas, total: n, page, pages: Math.ceil(n / limit), limit });
  } catch (e) {
    console.error("FTS5:", e);
    return c.json(
      { error: "expresion_invalida", mensaje: "Expresión de búsqueda no válida." },
      400,
    );
  }
});

app.get("/api/libros/:id", validar("param", esquemaId), async (c) => {
  const db = crearDb(c.env);
  const { id } = c.req.valid("param");
  const filas = await db
    .select()
    .from(biblioteca)
    .where(eq(biblioteca.id, id))
    .limit(1)
    .all();
  const fila = filas[0];
  if (!fila) return c.json({ error: "no_encontrado" }, 404);
  return c.json(fila);
});

/** '' -> null; el esquema zod ya garantizo claves y tipos. */
function aRegistro(valido: Record<string, string | number | undefined>) {
  const datos: Record<string, string | null> = {};
  for (const [k, v] of Object.entries(valido)) {
    datos[k] = v === "" || v === undefined ? null : String(v);
  }
  return datos;
}

app.post("/api/libros", requireAuth, validar("json", esquemaRegistro), async (c) => {
  const db = crearDb(c.env);
  const filas = await db
    .insert(biblioteca)
    .values(aRegistro(c.req.valid("json")) as typeof biblioteca.$inferInsert)
    .returning({ id: biblioteca.id })
    .all();
  const creado = filas[0];
  if (!creado) return c.json({ error: "insercion_fallida" }, 500);
  return c.json(creado, 201);
});

app.put(
  "/api/libros/:id",
  requireAuth,
  validar("param", esquemaId),
  validar("json", esquemaRegistro),
  async (c) => {
    const db = crearDb(c.env);
    const { id } = c.req.valid("param");
    const filas = await db
      .update(biblioteca)
      .set(aRegistro(c.req.valid("json")) as Partial<typeof biblioteca.$inferInsert>)
      .where(eq(biblioteca.id, id))
      .returning({ id: biblioteca.id })
      .all();
    const actualizado = filas[0];
    if (!actualizado) return c.json({ error: "no_encontrado" }, 404);
    return c.json(actualizado);
  },
);

app.delete(
  "/api/libros/:id",
  requireAuth,
  validar("param", esquemaId),
  async (c) => {
    const db = crearDb(c.env);
    const { id } = c.req.valid("param");
    const filas = await db
      .delete(biblioteca)
      .where(eq(biblioteca.id, id))
      .returning({ id: biblioteca.id })
      .all();
    if (!filas[0]) return c.json({ error: "no_encontrado" }, 404);
    return c.json({ eliminado: true });
  },
);

// Paginas de escritura: solo con sesion; si no, al login. Se sirven desde el
// binding ASSETS (requiere run_worker_first en wrangler.jsonc).
for (const pagina of ["/editar.html", "/nuevo.html"]) {
  app.get(pagina, requireAuthPagina, async (c) => {
    return c.env.ASSETS.fetch(c.req.raw);
  });
}

app.notFound((c) => c.json({ error: "no_encontrado" }, 404));

export default app;
