import { describe, expect, it } from "vitest";
import { buildAdvancedMatch, buildSimpleMatch } from "../src/fts";

describe("buildSimpleMatch", () => {
  it("turns words into quoted terms with implicit AND", () => {
    expect(buildSimpleMatch("Rústico")).toBe('"rústico"');
    expect(buildSimpleMatch("cambio climático")).toBe('"cambio" "climático"');
  });

  it("neutralizes FTS5 operators and punctuation", () => {
    expect(buildSimpleMatch('AND OR NOT * - "x"')).toBe('"and" "or" "not" "x"');
  });

  it("returns null when there are no terms", () => {
    expect(buildSimpleMatch("   ")).toBeNull();
    expect(buildSimpleMatch("***")).toBeNull();
  });

  it("adds the whitelisted column filter", () => {
    expect(buildSimpleMatch("geofísica", ["Titulo", "Autor"])).toBe(
      '{Titulo Autor} : "geofísica"',
    );
  });

  it("ignores unknown columns", () => {
    expect(buildSimpleMatch("mar", ["Titulo", "NoExiste"])).toBe('{Titulo} : "mar"');
    expect(buildSimpleMatch("mar", ["NoExiste"])).toBe('"mar"');
  });
});

describe("buildAdvancedMatch", () => {
  it("preserves FTS5 syntax", () => {
    expect(buildAdvancedMatch('"cambio climático" AND Titulo: geofísica*')).toBe(
      '"cambio climático" AND Titulo: geofísica*',
    );
  });

  it("caps length and removes NUL bytes", () => {
    expect(buildAdvancedMatch("a\0b")).toBe("ab");
    expect(buildAdvancedMatch("x".repeat(1_000))?.length).toBe(500);
  });

  it("returns null when the expression is empty", () => {
    expect(buildAdvancedMatch("   ")).toBeNull();
  });

  it("combines the column filter with the expression", () => {
    expect(buildAdvancedMatch("mar*", ["Tema o Materia"])).toBe(
      '{"Tema o Materia"} : mar*',
    );
  });
});
