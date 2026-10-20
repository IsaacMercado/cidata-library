"""Genera SQL idempotente para cargar la tabla `Biblioteca` en D1.

El SQL usa `INSERT ... ON CONFLICT("ID") DO UPDATE`, así que se puede volver a
ejecutar cuando llegue una base de datos nueva: actualiza las filas existentes
(por ID) y crea las que falten. Los triggers de FTS5 mantienen el índice.

Uso:
    uv run --project tools/etl biblioteca-etl sql [sqlite] [seed.sql]
"""

from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from .rutas import SEED, SQLITE

TABLA = "Biblioteca"
COLUMNAS = [
    "ID",
    "Cota",
    "Autor",
    "Titulo",
    "Texto Ficha",
    "Coautor",
    "Tema o Materia",
    "Series",
    "Paginas",
    "ISBN",
    "Notas",
    "Codigo CIDA",
    "Ejemplares",
    "Precio Unidad",
    "Precio Total",
    "Lujo/Rústico",
    "Donacion",
]
LOTE_FILAS = 100
# D1 limita cada sentencia a ~100 KB. Dejamos margen para el resto del INSERT.
MAX_BYTES = 90_000

_COLUMNAS_SQL = ", ".join(f'"{c}"' for c in COLUMNAS)
_ACTUALIZACIONES = ", ".join(
    f'"{c}" = excluded."{c}"' for c in COLUMNAS if c != "ID"
)


def literal(v: object) -> str:
    if v is None:
        return "NULL"
    return "'" + str(v).replace("'", "''") + "'"


def leer_filas(sqlite: Path) -> list[tuple]:
    """Lee las filas validando que la tabla y las columnas esperadas existan."""
    if not sqlite.exists():
        raise SystemExit(
            f"No se encontró {sqlite}. Ejecuta antes:\n"
            "  npm run data:extract"
        )

    con = sqlite3.connect(sqlite)
    try:
        info = con.execute(f'PRAGMA table_info("{TABLA}")').fetchall()
        if not info:
            raise SystemExit(f"La tabla '{TABLA}' no existe en {sqlite}.")
        existentes = {fila[1] for fila in info}
        faltantes = [c for c in COLUMNAS if c not in existentes]
        if faltantes:
            raise SystemExit(
                "Faltan columnas en la tabla "
                f"'{TABLA}': {', '.join(faltantes)}"
            )
        filas = con.execute(
            f'SELECT {_COLUMNAS_SQL} FROM "{TABLA}" ORDER BY "ID"'
        ).fetchall()
    finally:
        con.close()
    return filas


def _insert(filas: list[tuple]) -> str:
    valores = ",\n".join(
        "(" + ", ".join(literal(v) for v in fila) + ")" for fila in filas
    )
    return (
        f'INSERT INTO "{TABLA}" ({_COLUMNAS_SQL}) VALUES\n'
        f"{valores}\n"
        f'ON CONFLICT("ID") DO UPDATE SET {_ACTUALIZACIONES};'
    )


def _emitir(filas: list[tuple], max_bytes: int) -> str:
    sentencia = _insert(filas)
    if len(filas) == 1 and len(sentencia.encode("utf-8")) > max_bytes:
        print(
            "  aviso: una fila supera el límite de una sentencia D1 "
            f"(ID={filas[0][0]}); podría fallar al subirla."
        )
    return sentencia


def sentencias_inserts(
    filas: list[tuple],
    *,
    lote: int = LOTE_FILAS,
    max_bytes: int = MAX_BYTES,
) -> Iterator[str]:
    """Agrupa filas en INSERTs que respetan el límite de tamaño de D1."""
    if lote < 1:
        raise ValueError("El tamaño de lote debe ser >= 1")

    pendientes: list[tuple] = []
    for fila in filas:
        if pendientes:
            candidata = _insert([*pendientes, fila])
            if len(pendientes) >= lote or len(candidata.encode("utf-8")) > max_bytes:
                yield _emitir(pendientes, max_bytes)
                pendientes = []
        pendientes.append(fila)

    if pendientes:
        yield _emitir(pendientes, max_bytes)


def generar_sql(
    sqlite: Path = SQLITE,
    destino: Path = SEED,
    *,
    lote: int = LOTE_FILAS,
) -> tuple[int, int]:
    """Escribe el archivo SQL y devuelve (filas, sentencias)."""
    filas = leer_filas(sqlite)
    sentencias = list(sentencias_inserts(filas, lote=lote))

    destino.parent.mkdir(parents=True, exist_ok=True)
    lineas = [
        "-- Seed generado desde data/derived/biblioteca.sqlite.",
        "-- No editar a mano. Es idempotente por ID (INSERT ... ON CONFLICT).",
        "",
    ]
    for i, sentencia in enumerate(sentencias, 1):
        lineas.append(f"-- Lote {i}/{len(sentencias)}")
        lineas.append(sentencia)
        lineas.append("")
    destino.write_text("\n".join(lineas), encoding="utf-8")

    print(f"{len(filas)} filas en {len(sentencias)} INSERTs -> {destino}")
    return len(filas), len(sentencias)


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sqlite", nargs="?", default=str(SQLITE))
    ap.add_argument("salida", nargs="?", default=str(SEED))
    ap.add_argument("--lote", type=int, default=LOTE_FILAS)
    args = ap.parse_args(argv)

    generar_sql(Path(args.sqlite), Path(args.salida), lote=args.lote)


if __name__ == "__main__":
    main()
