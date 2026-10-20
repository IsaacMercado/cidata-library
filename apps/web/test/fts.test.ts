import { describe, expect, it } from "vitest";
import { matchAvanzado, matchSimple } from "../src/fts";

describe("matchSimple", () => {
  it("convierte palabras en términos citados con AND implícito", () => {
    expect(matchSimple("Rústico")).toBe('"rústico"');
    expect(matchSimple("cambio climático")).toBe('"cambio" "climático"');
  });

  it("neutraliza operadores y signos de FTS5", () => {
    expect(matchSimple('AND OR NOT * - "x"')).toBe('"and" "or" "not" "x"');
  });

  it("devuelve null si no hay términos", () => {
    expect(matchSimple("   ")).toBeNull();
    expect(matchSimple("***")).toBeNull();
  });

  it("añade el filtro de columnas de la lista blanca", () => {
    expect(matchSimple("geofísica", ["Titulo", "Autor"])).toBe(
      '{Titulo Autor} : "geofísica"',
    );
  });

  it("ignora columnas desconocidas", () => {
    expect(matchSimple("mar", ["Titulo", "NoExiste"])).toBe('{Titulo} : "mar"');
    expect(matchSimple("mar", ["NoExiste"])).toBe('"mar"');
  });
});

describe("matchAvanzado", () => {
  it("respeta la sintaxis FTS5", () => {
    expect(matchAvanzado('"cambio climático" AND Titulo: geofísica*')).toBe(
      '"cambio climático" AND Titulo: geofísica*',
    );
  });

  it("acota la longitud y elimina NUL", () => {
    expect(matchAvanzado("a\0b")).toBe("ab");
    expect(matchAvanzado("x".repeat(1_000))?.length).toBe(500);
  });

  it("devuelve null si la expresión está vacía", () => {
    expect(matchAvanzado("   ")).toBeNull();
  });

  it("combina el filtro de columnas con la expresión", () => {
    expect(matchAvanzado("mar*", ["Tema o Materia"])).toBe(
      '{"Tema o Materia"} : mar*',
    );
  });
});
