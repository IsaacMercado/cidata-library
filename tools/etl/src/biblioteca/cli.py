"""CLI del ETL de la biblioteca.

Subcomandos:

- `export`: Access (.accdb) -> CSV + SQLite + esquema SQL.
- `sql`: SQLite -> SQL idempotente para D1.
- `upload`: SQLite -> D1 local o remoto.
- `all`: `export` + `sql`.

Uso:
    uv run --project tools/etl biblioteca-etl --help
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .d1 import cargar
from .export import exportar_todo
from .rutas import ACCBD, DERIVADOS, SEED, SQLITE
from .seed import LOTE_FILAS, generar_sql


def _cmd_export(args: argparse.Namespace) -> None:
    exportar_todo(Path(args.accdb), Path(args.salida))


def _cmd_sql(args: argparse.Namespace) -> None:
    generar_sql(Path(args.sqlite), Path(args.salida), lote=args.lote)


def _cmd_upload(args: argparse.Namespace) -> None:
    cargar(
        Path(args.sqlite),
        local=args.local,
        via=args.via,
        database=args.database,
        truncate=args.truncate,
        dry_run=Path(args.dry_run) if args.dry_run else None,
        lote=args.lote,
        rebuild_fts=args.rebuild_fts,
    )


def _cmd_all(args: argparse.Namespace) -> None:
    exportar_todo(Path(args.accdb), Path(args.salida))
    generar_sql(Path(args.salida) / "biblioteca.sqlite", Path(args.seed), lote=args.lote)


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biblioteca-etl",
        description="Extracción desde Access y carga en Cloudflare D1.",
    )
    sub = parser.add_subparsers(dest="comando", required=True)

    p_export = sub.add_parser("export", help="Access -> CSV/SQLite/esquema")
    p_export.add_argument("accdb", nargs="?", default=str(ACCBD))
    p_export.add_argument("salida", nargs="?", default=str(DERIVADOS))
    p_export.set_defaults(func=_cmd_export)

    p_sql = sub.add_parser("sql", help="SQLite -> SQL idempotente para D1")
    p_sql.add_argument("sqlite", nargs="?", default=str(SQLITE))
    p_sql.add_argument("salida", nargs="?", default=str(SEED))
    p_sql.add_argument("--lote", type=int, default=LOTE_FILAS)
    p_sql.set_defaults(func=_cmd_sql)

    p_up = sub.add_parser("upload", help="SQLite -> D1 local o remoto")
    p_up.add_argument("sqlite", nargs="?", default=str(SQLITE))
    destino = p_up.add_mutually_exclusive_group(required=True)
    destino.add_argument("--local", action="store_true", help="D1 local de Wrangler")
    destino.add_argument("--remote", action="store_true", help="D1 remoto")
    p_up.add_argument(
        "--via",
        choices=["wrangler", "api"],
        default="wrangler",
        help="wrangler (sesión iniciada) o api (token + IDs por entorno)",
    )
    p_up.add_argument("--database", default="biblioteca", help="Nombre de la base D1")
    p_up.add_argument(
        "--truncate",
        action="store_true",
        help="Vacía la tabla antes de cargar (¡destructivo!)",
    )
    p_up.add_argument(
        "--dry-run",
        metavar="ARCHIVO",
        help="Escribe el SQL en ARCHIVO sin subir nada",
    )
    p_up.add_argument("--lote", type=int, default=LOTE_FILAS)
    p_up.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="Reconstruye el índice FTS5 al terminar",
    )
    p_up.set_defaults(func=_cmd_upload)

    p_all = sub.add_parser("all", help="export + sql")
    p_all.add_argument("accdb", nargs="?", default=str(ACCBD))
    p_all.add_argument("salida", nargs="?", default=str(DERIVADOS))
    p_all.add_argument("--seed", default=str(SEED))
    p_all.add_argument("--lote", type=int, default=LOTE_FILAS)
    p_all.set_defaults(func=_cmd_all)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = construir_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
