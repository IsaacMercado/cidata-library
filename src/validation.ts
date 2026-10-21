import { zValidator } from "@hono/zod-validator";
import { z, type ZodType } from "zod";
import type { Context } from "hono";

// GET /api/libros?q=&mode=&fields=&order=&page=&limit=
export const listQuerySchema = z.object({
  q: z.string().max(500).optional().default(""),
  mode: z.enum(["simple", "advanced"]).optional().default("simple"),
  fields: z.string().max(500).optional().default(""),
  order: z.enum(["id", "title", "author"]).optional().default("id"),
  page: z.coerce.number().int().min(1).max(100_000).optional().default(1),
  limit: z.coerce.number().int().min(1).max(100).optional().default(25),
});

// /api/libros/:id
export const idParamSchema = z.object({
  id: z.coerce.number().int().positive().max(2_147_483_647),
});

// POST/PUT body: known columns only, strict and non-empty. Empty strings are
// converted to null in the handler.
const textField = z.union([z.string().max(200_000), z.number()]).optional();
export const bookInputSchema = z
  .object({
    callNumber: textField,
    title: textField,
    coauthor: textField,
    subject: textField,
    series: textField,
    pages: textField,
    isbn: textField,
    notes: textField,
    cidaCode: textField,
    copies: textField,
    unitPrice: textField,
    totalPrice: textField,
    donation: textField,
    catalogText: textField,
    author: textField,
    binding: textField,
  })
  .strict()
  .refine((value) => Object.keys(value).length > 0, {
    message: "Registro vacío",
  });

// POST /api/auth/login
export const loginSchema = z
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

/** zValidator with a stable 400 shape. User-facing messages stay in Spanish. */
export function validate<T extends "json" | "query" | "param", S extends ZodType>(
  target: T,
  schema: S,
) {
  return zValidator(target, schema, (result, c: Context) => {
    if (!result.success) {
      return c.json(
        {
          error: "validation_error",
          details: result.error.issues.map((issue) => ({
            field: issue.path.join(".") || "(root)",
            message: issue.message,
          })),
        },
        400,
      );
    }
  });
}
