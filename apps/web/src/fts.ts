import { COLUMNAS_FTS } from "./db/schema";

// Longitud maxima de la expresion MATCH (D1 limita los patrones LIKE/GLOB a
// 50 bytes; para MATCH no hay ese limite, pero acotamos por seguridad).
const MAX_SIMPLE = 200;
const MAX_AVANZADO = 500;

/** Escapa un literal FTS5 entrecomillado (las comillas se duplican). */
function citar(texto: string): string {
  return `"${texto.replace(/"/g, '""')}"`;
}

/**
 * Modo simple: extrae palabras (letras/numeros unicode) y las une con AND
 * implicito. Neutraliza operadores FTS5 (AND/OR/NOT, *, -, comillas...),
 * asi la entrada del usuario nunca rompe la consulta.
 */
export function matchSimple(q: string, campos?: string[]): string | null {
  const filtro = filtroColumnas(campos);
  const tokens: string[] = [];
  const palabras = q
    .slice(0, MAX_SIMPLE)
    .toLowerCase()
    .match(/[\p{L}\p{N}]+/gu);
  if (!palabras || palabras.length === 0) return null;
  for (const p of palabras) tokens.push(citar(p));
  return `${filtro}${tokens.join(" ")}`.trim() || null;
}

/**
 * Modo avanzado: pasa la expresion FTS5 casi tal cual (frases "...", AND/OR/
 * NOT, prefijos `term*`, filtros `{col} : ...`). Solo acota longitud y quita
 * NUL. Si la sintaxis es invalida, D1 devuelve error y la API responde 400.
 */
export function matchAvanzado(q: string, campos?: string[]): string | null {
  const limpio = q.replace(/\0/g, "").slice(0, MAX_AVANZADO).trim();
  if (!limpio) return null;
  const filtro = filtroColumnas(campos);
  return `${filtro}${limpio}`.trim() || null;
}

/**
 * Filtro por columnas `{...} : expr`. Solo acepta columnas de la lista blanca;
 * los nombres con espacios se citan como exige FTS5 ({"Tema o Materia"}).
 */
function filtroColumnas(campos?: string[]): string {
  if (!campos || campos.length === 0) return "";
  const validas = campos.filter((c): c is (typeof COLUMNAS_FTS)[number] =>
    (COLUMNAS_FTS as readonly string[]).includes(c),
  );
  if (validas.length === 0) return "";
  const lista = validas.map((c) => (c.includes(" ") ? `"${c}"` : c)).join(" ");
  return `{${lista}} : `;
}
