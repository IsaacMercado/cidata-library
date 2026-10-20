"""Export the Microsoft Access database to portable formats.

Generates, under `data/derived/`:

- `biblioteca.csv`: readable dump of the table.
- `biblioteca.sqlite`: SQLite copy (source for the D1 SQL generator).
- `schema.sql`: reference SQL schema.

Usage:
    uv run --project tools/etl biblioteca-etl export [path.accdb] [output_dir]
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from access_parser import AccessParser

from .paths import ACCESS_DB, DERIVED_DIR

OBJECT_TYPES = {
    1: "table",
    2: "database",
    3: "container",
    4: "delete_query",
    5: "query",
    6: "linked_table",
    -32768: "form",
    -32766: "macro",
    -32764: "report",
    -32761: "module",
    -32758: "module",  # some drivers use this code
    -32757: "properties",
}


def _load(accdb: Path) -> tuple[AccessParser, dict[str, list]]:
    db = AccessParser(str(accdb))
    tables: dict[str, list] = {}
    for name in db.catalog:
        if not name.startswith("MSys") and not name.startswith("f_"):
            tables[name] = db.get_table(name).parse()
    return db, tables


def list_objects(db: AccessParser) -> list[tuple[str, str]]:
    rows = db.parse_table("MSysObjects")
    objects = []
    for name, kind in zip(
        rows.get("Name", []), rows.get("Type", []), strict=False
    ):
        if name in (None, "") or kind is None:
            continue
        name = str(name)
        if name.startswith(("MSys", "f_")):
            continue
        if kind == 3:  # navigation pane containers
            continue
        objects.append((name, OBJECT_TYPES.get(kind, f"other({kind})")))
    return objects


def _row_count(columns: dict[str, list]) -> int:
    return len(next(iter(columns.values()))) if columns else 0


def export_csv(table: str, columns: dict[str, list], destination: Path) -> None:
    column_names = list(columns)
    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(column_names)
        for index in range(_row_count(columns)):
            writer.writerow([columns[column][index] for column in column_names])


def export_sqlite(data: dict[str, list], destination: Path) -> None:
    if destination.exists():
        destination.unlink()
    connection = sqlite3.connect(destination)
    cursor = connection.cursor()
    for table, columns in data.items():
        column_names = list(columns)
        definitions = []
        for column in column_names:
            if column == "ID":
                definitions.append("ID INTEGER PRIMARY KEY")
            else:
                definitions.append(f"[{column}] TEXT")
        cursor.execute(f"CREATE TABLE [{table}] ({', '.join(definitions)})")
        placeholders = ", ".join("?" * len(column_names))
        insert = f"INSERT INTO [{table}] VALUES ({placeholders})"
        cursor.executemany(
            insert,
            (
                [columns[column][index] for column in column_names]
                for index in range(_row_count(columns))
            ),
        )
    connection.commit()
    connection.close()


def export_schema(data: dict[str, list], destination: Path) -> None:
    lines = []
    for table, columns in data.items():
        definitions = []
        for column in list(columns):
            if column == "ID":
                definitions.append("    ID INTEGER PRIMARY KEY")
            else:
                definitions.append(f"    [{column}] TEXT")
        lines.append(f"CREATE TABLE [{table}] (\n" + ",\n".join(definitions) + "\n);")
    destination.write_text("\n\n".join(lines) + "\n", encoding="utf-8")


def export_all(accdb: Path, output_dir: Path) -> dict[str, int]:
    """Export every Access table and return {table: row_count}."""
    if not accdb.exists():
        raise SystemExit(f"Access database not found: {accdb}")

    output_dir.mkdir(parents=True, exist_ok=True)
    db, data = _load(accdb)

    print(f"Database: {accdb}")
    print("Objects found:")
    for name, kind in list_objects(db):
        print(f"  - [{kind}] {name}")

    for table, columns in data.items():
        export_csv(table, columns, output_dir / f"{table.lower()}.csv")
    export_sqlite(data, output_dir / "biblioteca.sqlite")
    export_schema(data, output_dir / "schema.sql")

    counts = {table: _row_count(columns) for table, columns in data.items()}
    for table, row_count in counts.items():
        print(f"Table '{table}': {row_count} rows, {len(data[table])} columns")
    print(f"Files written to: {output_dir.resolve()}")
    return counts


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("accdb", nargs="?", default=str(ACCESS_DB))
    parser.add_argument("output", nargs="?", default=str(DERIVED_DIR))
    args = parser.parse_args(argv)

    export_all(Path(args.accdb), Path(args.output))


if __name__ == "__main__":
    main()
