import { zValidator } from "@hono/zod-validator";
import { z, type ZodType } from "zod";
import type { Context } from "hono";

// GET /api/libros?q=&modo=&campos=&orden=&page=&limit=
export const esquemaLista = z.object({
  q: z.string().max(500).optional().default(""),
  modo: z.enum(["simple", "avanzado"]).optional().default("simple"),
  campos: z.string().max(500).optional().default(""),
  orden: z.enum(["id", "titulo", "autor"]).optional().default("id"),
  page: z.coerce.number().int().min(1).max(100_000).optional().default(1),
  limit: z.coerce.number().int().min(1).max(100).optional().default(25),
});

// /api/libros/:id
export const esquemaId = z.object({
  id: z.coerce.number().int().positive().max(2_147_483_647),
});

// Cuerpo de POST/PUT: solo columnas conocidas, estrictas y no vacio.
// (Los '' se convierten a null en el handler.)
const textoCampo = z.union([z.string().max(200_000), z.number()]).optional();
export const esquemaRegistro = z
  .object({
    cota: textoCampo,
    titulo: textoCampo,
    coautor: textoCampo,
    temaOMateria: textoCampo,
    series: textoCampo,
    paginas: textoCampo,
    isbn: textoCampo,
    notas: textoCampo,
    codigoCida: textoCampo,
    ejemplares: textoCampo,
    precioUnidad: textoCampo,
    precioTotal: textoCampo,
    donacion: textoCampo,
    textoFicha: textoCampo,
    autor: textoCampo,
    lujoRustico: textoCampo,
  })
  .strict()
  .refine((o) => Object.keys(o).length > 0, { message: "Registro vacío" });

// POST /api/auth/login
export const esquemaLogin = z
  .object({
    email: z
      .string()
      .trim()
      .min(3)
      .max(254)
      .regex(/^[^\s@]+@[^\s@]+\.[^\s@]+$/, { message: "Email no válido" }),
    password: z.string().min(1).max(256),
  })
  .strict();

/** zValidator con error 400 en español y formato estable (conserva tipos). */
export function validar<T extends "json" | "query" | "param", S extends ZodType>(
  objetivo: T,
  esquema: S,
) {
  return zValidator(objetivo, esquema, (resultado, c: Context) => {
    if (!resultado.success) {
      return c.json(
        {
          error: "validacion",
          detalles: resultado.error.issues.map((i) => ({
            campo: i.path.join(".") || "(raíz)",
            mensaje: i.message,
          })),
        },
        400,
      );
    }
  });
}
