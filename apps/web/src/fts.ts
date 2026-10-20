import { FTS_COLUMNS } from "./db/schema";

// D1 limits LIKE/GLOB patterns to 50 bytes; MATCH has no such limit, but we
// still cap the expression length as a safety measure.
const MAX_SIMPLE_LENGTH = 200;
const MAX_ADVANCED_LENGTH = 500;

/** Escape a literal for FTS5 by wrapping it in quotes (quotes are doubled). */
function quote(text: string): string {
  return `"${text.replace(/"/g, '""')}"`;
}

/**
 * Simple mode: extract unicode letters/numbers and join them with implicit
 * AND. FTS5 operators (AND/OR/NOT, *, -, quotes…) are neutralized so user
 * input can never break the query.
 */
export function buildSimpleMatch(
  query: string,
  fields?: string[],
): string | null {
  const filter = columnFilter(fields);
  const tokens: string[] = [];
  const words = query
    .slice(0, MAX_SIMPLE_LENGTH)
    .toLowerCase()
    .match(/[\p{L}\p{N}]+/gu);
  if (!words || words.length === 0) return null;
  for (const word of words) tokens.push(quote(word));
  return `${filter}${tokens.join(" ")}`.trim() || null;
}

/**
 * Advanced mode: pass the FTS5 expression almost as-is (phrases "...",
 * AND/OR/NOT, `term*` prefixes, `{col} : ...` filters). Only cap length and
 * remove NUL. Invalid syntax makes D1 fail and the API returns 400.
 */
export function buildAdvancedMatch(
  query: string,
  fields?: string[],
): string | null {
  const cleaned = query.replace(/\0/g, "").slice(0, MAX_ADVANCED_LENGTH).trim();
  if (!cleaned) return null;
  const filter = columnFilter(fields);
  return `${filter}${cleaned}`.trim() || null;
}

/**
 * Column filter `{...} : expr`. Only allows the FTS whitelist; names with
 * spaces are quoted as FTS5 requires ({"Tema o Materia"}).
 */
function columnFilter(fields?: string[]): string {
  if (!fields || fields.length === 0) return "";
  const valid = fields.filter((field): field is (typeof FTS_COLUMNS)[number] =>
    (FTS_COLUMNS as readonly string[]).includes(field),
  );
  if (valid.length === 0) return "";
  const list = valid.map((field) => (field.includes(" ") ? `"${field}"` : field)).join(" ");
  return `{${list}} : `;
}
