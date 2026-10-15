import { sql } from "drizzle-orm";
import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

// Tabla migrada tal cual desde Access (todos los campos TEXT salvo la PK).
// Los nombres de columna con espacios se declaran explicitos; las claves JS
// usan camelCase. El orden reproduce el del formulario original.
export const biblioteca = sqliteTable(
  "Biblioteca",
  {
    id: integer("ID").primaryKey(),
    cota: text("Cota"),
    titulo: text("Titulo"),
    coautor: text("Coautor"),
    temaOMateria: text("Tema o Materia"),
    series: text("Series"),
    paginas: text("Paginas"),
    isbn: text("ISBN"),
    notas: text("Notas"),
    codigoCida: text("Codigo CIDA"),
    ejemplares: text("Ejemplares"),
    precioUnidad: text("Precio Unidad"),
    precioTotal: text("Precio Total"),
    donacion: text("Donacion"),
    textoFicha: text("Texto Ficha"),
    autor: text("Autor"),
    lujoRustico: text("Lujo/Rústico"),
  },
  (t) => [
    // Indices para ordenacion, filtros por prefijo y consultas exactas.
    // (Los LIKE '%...%' no usan indice: para eso esta la tabla FTS5.)
    index("idx_biblioteca_titulo").on(t.titulo),
    index("idx_biblioteca_autor").on(t.autor),
    index("idx_biblioteca_tema").on(t.temaOMateria),
    index("idx_biblioteca_texto_ficha").on(t.textoFicha),
    index("idx_biblioteca_cota").on(t.cota),
    index("idx_biblioteca_isbn").on(t.isbn),
  ],
);

export type Biblioteca = typeof biblioteca.$inferSelect;
export type NuevoRegistro = typeof biblioteca.$inferInsert;

// Autenticacion por sesiones en cookie (ver src/auth.ts). Sin ORM magico:
// dos tablas pequenas, hash PBKDF2 y token aleatorio (solo su sha256 en BD).
export const usuarios = sqliteTable("usuarios", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  email: text("email").notNull().unique(),
  hash: text("hash").notNull(),
  creado: text("creado")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const sesiones = sqliteTable(
  "sesiones",
  {
    token: text("token").primaryKey(), // sha256 hex del token de la cookie
    usuarioId: integer("usuario_id")
      .notNull()
      .references(() => usuarios.id, { onDelete: "cascade" }),
    expira: integer("expira").notNull(), // unix seconds
  },
  (t) => [index("idx_sesiones_usuario").on(t.usuarioId)],
);

// La tabla virtual FTS5 `biblioteca_fts` la crea la migracion 0002 (SQL hecho a
// mano) y la sincronizan triggers; en codigo se consulta con fragmentos `sql`
// de Drizzle, nunca con escrituras del ORM.
// Columnas FTS disponibles para el filtro avanzado {col1 col2} : termino.
export const COLUMNAS_FTS = [
  "Titulo",
  "Autor",
  "Coautor",
  "Tema o Materia",
  "Series",
  "Notas",
  "Texto Ficha",
  "Cota",
  "ISBN",
] as const;
