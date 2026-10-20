"""Generate idempotent SQL to load the `Biblioteca` table into D1.

The SQL uses `INSERT ... ON CONFLICT("ID") DO UPDATE`, so it can be run again
when a new database arrives: existing rows are updated by ID and missing rows
are created. FTS5 triggers keep the index in sync.

Usage:
    uv run --project tools/etl biblioteca-etl sql [sqlite] [seed.sql]
"""

from __future__ import annotations

import argparse
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from .paths import SEED_SQL, SQLITE_DB

TABLE = "Biblioteca"
COLUMNS = [
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
BATCH_SIZE = 100
# D1 limits each statement to ~100 KB. Leave room for the rest of the INSERT.
MAX_BYTES = 90_000

_SQL_COLUMNS = ", ".join(f'"{column}"' for column in COLUMNS)
_UPDATES = ", ".join(
    f'"{column}" = excluded."{column}"' for column in COLUMNS if column != "ID"
)


def sql_literal(value: object) -> str:
    if value is None:
        return "NULL"
    return "'" + str(value).replace("'", "''") + "'"


def read_rows(sqlite_path: Path) -> list[tuple]:
    """Read rows, validating that the expected table and columns exist."""
    if not sqlite_path.exists():
        raise SystemExit(
            f"{sqlite_path} not found. Run first:\n"
            "  npm run data:extract"
        )

    connection = sqlite3.connect(sqlite_path)
    try:
        info = connection.execute(f'PRAGMA table_info("{TABLE}")').fetchall()
        if not info:
            raise SystemExit(f"Table '{TABLE}' does not exist in {sqlite_path}.")
        existing = {row[1] for row in info}
        missing = [column for column in COLUMNS if column not in existing]
        if missing:
            raise SystemExit(
                f"Missing columns in table '{TABLE}': {', '.join(missing)}"
            )
        rows = connection.execute(
            f'SELECT {_SQL_COLUMNS} FROM "{TABLE}" ORDER BY "ID"'
        ).fetchall()
    finally:
        connection.close()
    return rows


def _insert(rows: list[tuple]) -> str:
    values = ",\n".join(
        "(" + ", ".join(sql_literal(value) for value in row) + ")" for row in rows
    )
    return (
        f'INSERT INTO "{TABLE}" ({_SQL_COLUMNS}) VALUES\n'
        f"{values}\n"
        f'ON CONFLICT("ID") DO UPDATE SET {_UPDATES};'
    )


def _emit(rows: list[tuple], max_bytes: int) -> str:
    statement = _insert(rows)
    if len(rows) == 1 and len(statement.encode("utf-8")) > max_bytes:
        print(
            "  warning: one row exceeds the D1 statement limit "
            f"(ID={rows[0][0]}); it may fail when uploaded."
        )
    return statement


def iter_insert_statements(
    rows: list[tuple],
    *,
    batch_size: int = BATCH_SIZE,
    max_bytes: int = MAX_BYTES,
) -> Iterator[str]:
    """Group rows into INSERTs that stay within the D1 size limit."""
    if batch_size < 1:
        raise ValueError("Batch size must be >= 1")

    pending: list[tuple] = []
    for row in rows:
        if pending:
            candidate = _insert([*pending, row])
            if (
                len(pending) >= batch_size
                or len(candidate.encode("utf-8")) > max_bytes
            ):
                yield _emit(pending, max_bytes)
                pending = []
        pending.append(row)

    if pending:
        yield _emit(pending, max_bytes)


def generate_sql(
    sqlite_path: Path = SQLITE_DB,
    destination: Path = SEED_SQL,
    *,
    batch_size: int = BATCH_SIZE,
) -> tuple[int, int]:
    """Write the SQL file and return (rows, statements)."""
    rows = read_rows(sqlite_path)
    statements = list(iter_insert_statements(rows, batch_size=batch_size))

    destination.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "-- Seed generated from data/derived/biblioteca.sqlite.",
        "-- Do not edit by hand. It is idempotent by ID (INSERT ... ON CONFLICT).",
        "",
    ]
    for index, statement in enumerate(statements, 1):
        lines.append(f"-- Batch {index}/{len(statements)}")
        lines.append(statement)
        lines.append("")
    destination.write_text("\n".join(lines), encoding="utf-8")

    print(f"{len(rows)} rows in {len(statements)} INSERTs -> {destination}")
    return len(rows), len(statements)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite", nargs="?", default=str(SQLITE_DB))
    parser.add_argument("output", nargs="?", default=str(SEED_SQL))
    parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    args = parser.parse_args(argv)

    generate_sql(
        Path(args.sqlite), Path(args.output), batch_size=args.batch_size
    )


if __name__ == "__main__":
    main()
