import { sql } from "drizzle-orm";
import { index, integer, sqliteTable, text } from "drizzle-orm/sqlite-core";

// Table migrated from Access exactly as-is. Database table and column names
// stay in Spanish because they are part of the external data contract; the
// TypeScript property names are English for code readability.
export const books = sqliteTable(
  "Biblioteca",
  {
    id: integer("ID").primaryKey(),
    callNumber: text("Cota"),
    title: text("Titulo"),
    coauthor: text("Coautor"),
    subject: text("Tema o Materia"),
    series: text("Series"),
    pages: text("Paginas"),
    isbn: text("ISBN"),
    notes: text("Notas"),
    cidaCode: text("Codigo CIDA"),
    copies: text("Ejemplares"),
    unitPrice: text("Precio Unidad"),
    totalPrice: text("Precio Total"),
    donation: text("Donacion"),
    catalogText: text("Texto Ficha"),
    author: text("Autor"),
    binding: text("Lujo/Rústico"),
  },
  (t) => [
    // Indexes for sorting, prefix filters and exact lookups. `LIKE '%...%'`
    // cannot use them: FTS5 covers full-text search instead.
    index("idx_biblioteca_titulo").on(t.title),
    index("idx_biblioteca_autor").on(t.author),
    index("idx_biblioteca_tema").on(t.subject),
    index("idx_biblioteca_texto_ficha").on(t.catalogText),
    index("idx_biblioteca_cota").on(t.callNumber),
    index("idx_biblioteca_isbn").on(t.isbn),
  ],
);

export type Book = typeof books.$inferSelect;
export type NewBook = typeof books.$inferInsert;

// Cookie-based sessions (see src/auth.ts). Two small tables, PBKDF2 hashes and
// a random token whose SHA-256 is the only value stored in the database.
export const users = sqliteTable("usuarios", {
  id: integer("id").primaryKey({ autoIncrement: true }),
  email: text("email").notNull().unique(),
  passwordHash: text("hash").notNull(),
  createdAt: text("creado")
    .notNull()
    .default(sql`(datetime('now'))`),
});

export const sessions = sqliteTable(
  "sesiones",
  {
    token: text("token").primaryKey(), // SHA-256 hex of the session cookie
    userId: integer("usuario_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    expiresAt: integer("expira").notNull(), // Unix seconds
  },
  (t) => [index("idx_sesiones_usuario").on(t.userId)],
);

// The FTS5 virtual table `biblioteca_fts` is created by migration 0002 and
// kept in sync by triggers. It is queried with Drizzle `sql` fragments, never
// through ORM writes.
// Columns available for the advanced `{col1 col2} : term` filter.
export const FTS_COLUMNS = [
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
