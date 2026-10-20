"""ETL CLI for the library.

Subcommands:

- `export`: Access (.accdb) -> CSV + SQLite + SQL schema.
- `sql`: SQLite -> idempotent SQL for D1.
- `upload`: SQLite -> local or remote D1.
- `all`: `export` + `sql`.

Usage:
    uv run --project tools/etl biblioteca-etl --help
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .d1 import upload
from .export import export_all
from .paths import ACCESS_DB, DERIVED_DIR, SEED_SQL, SQLITE_DB
from .seed import BATCH_SIZE, generate_sql


def _cmd_export(args: argparse.Namespace) -> None:
    export_all(Path(args.accdb), Path(args.output))


def _cmd_sql(args: argparse.Namespace) -> None:
    generate_sql(
        Path(args.sqlite), Path(args.output), batch_size=args.batch_size
    )


def _cmd_upload(args: argparse.Namespace) -> None:
    upload(
        Path(args.sqlite),
        local=args.local,
        method=args.method,
        database=args.database,
        truncate=args.truncate,
        dry_run=Path(args.dry_run) if args.dry_run else None,
        batch_size=args.batch_size,
        rebuild_fts=args.rebuild_fts,
    )


def _cmd_all(args: argparse.Namespace) -> None:
    export_all(Path(args.accdb), Path(args.output))
    generate_sql(
        Path(args.output) / "biblioteca.sqlite",
        Path(args.seed),
        batch_size=args.batch_size,
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="biblioteca-etl",
        description="Extract from Access and load into Cloudflare D1.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    export_parser = subparsers.add_parser(
        "export", help="Access -> CSV/SQLite/schema"
    )
    export_parser.add_argument("accdb", nargs="?", default=str(ACCESS_DB))
    export_parser.add_argument("output", nargs="?", default=str(DERIVED_DIR))
    export_parser.set_defaults(func=_cmd_export)

    sql_parser = subparsers.add_parser(
        "sql", help="SQLite -> idempotent SQL for D1"
    )
    sql_parser.add_argument("sqlite", nargs="?", default=str(SQLITE_DB))
    sql_parser.add_argument("output", nargs="?", default=str(SEED_SQL))
    sql_parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    sql_parser.set_defaults(func=_cmd_sql)

    upload_parser = subparsers.add_parser(
        "upload", help="SQLite -> local or remote D1"
    )
    upload_parser.add_argument("sqlite", nargs="?", default=str(SQLITE_DB))
    target = upload_parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--local", action="store_true", help="local Wrangler D1")
    target.add_argument("--remote", action="store_true", help="remote D1")
    upload_parser.add_argument(
        "--method",
        choices=["wrangler", "api"],
        default="wrangler",
        help="wrangler (logged in) or api (token + IDs from the environment)",
    )
    upload_parser.add_argument(
        "--database", default="biblioteca", help="D1 database name"
    )
    upload_parser.add_argument(
        "--truncate",
        action="store_true",
        help="empty the table before loading (destructive!)",
    )
    upload_parser.add_argument(
        "--dry-run",
        metavar="FILE",
        help="write the SQL to FILE without uploading anything",
    )
    upload_parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    upload_parser.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="rebuild the FTS5 index when finished",
    )
    upload_parser.set_defaults(func=_cmd_upload)

    all_parser = subparsers.add_parser("all", help="export + sql")
    all_parser.add_argument("accdb", nargs="?", default=str(ACCESS_DB))
    all_parser.add_argument("output", nargs="?", default=str(DERIVED_DIR))
    all_parser.add_argument("--seed", default=str(SEED_SQL))
    all_parser.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    all_parser.set_defaults(func=_cmd_all)

    return parser


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
