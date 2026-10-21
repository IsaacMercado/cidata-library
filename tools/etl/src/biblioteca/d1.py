"""Load SQLite rows into D1 (local or remote).

Two upload methods:

- `--method wrangler` (default): uses an already authenticated Wrangler CLI.
  Convenient from your machine.
- `--method api`: uses the D1 HTTP API with a token. Useful from CI or servers
  without `wrangler login`. Requires:
    CLOUDFLARE_API_TOKEN
    CLOUDFLARE_ACCOUNT_ID
    D1_DATABASE_ID

Uploads are idempotent: `INSERT ... ON CONFLICT("ID") DO UPDATE`. Use
`--truncate` only when you intentionally want to empty the table first.

Usage:
    uv run --project tools/etl biblioteca-etl upload --remote
    uv run --project tools/etl biblioteca-etl upload --local
    uv run --project tools/etl biblioteca-etl upload --remote --method api
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from .paths import SQLITE_DB, WORKER_DIR
from .seed import BATCH_SIZE, TABLE, iter_insert_statements, read_rows

API_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{account}"
    "/d1/database/{database}/query"
)
MAX_RETRIES = 5


def _run_wrangler(sql: str, *, database: str, local: bool) -> None:
    """Execute a temporary SQL file with `wrangler d1 execute`."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".sql", delete=False, encoding="utf-8"
    ) as handle:
        handle.write(sql)
        sql_path = Path(handle.name)

    mode = "--local" if local else "--remote"
    command = [
        "npx",
        "--no-install",
        "wrangler",
        "d1",
        "execute",
        database,
        mode,
        f"--file={sql_path}",
    ]
    try:
        result = subprocess.run(
            command, cwd=WORKER_DIR, capture_output=True, text=True, check=False
        )
        if result.returncode != 0:
            if result.stdout:
                print(result.stdout)
            if result.stderr:
                print(result.stderr, file=sys.stderr)
            raise SystemExit(
                f"`wrangler d1 execute` failed (exit code {result.returncode})."
            )
    finally:
        sql_path.unlink(missing_ok=True)


def _api_config() -> tuple[str, str, str]:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    account = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    database = os.environ.get("D1_DATABASE_ID", "").strip()
    missing = [
        name
        for name, value in (
            ("CLOUDFLARE_API_TOKEN", token),
            ("CLOUDFLARE_ACCOUNT_ID", account),
            ("D1_DATABASE_ID", database),
        )
        if not value
    ]
    if missing:
        raise SystemExit(
            "Missing environment variables for --method api: " + ", ".join(missing)
        )
    return token, account, database


def _run_api(sql: str, *, token: str, account: str, database: str) -> None:
    """Execute one statement through the D1 HTTP API, with retries."""
    url = API_URL.format(account=account, database=database)
    body = json.dumps({"sql": sql}).encode("utf-8")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, MAX_RETRIES + 1):
        request = urllib.request.Request(
            url, data=body, headers=headers, method="POST"
        )
        try:
            with urllib.request.urlopen(request, timeout=90) as response:
                data = json.load(response)
        except urllib.error.HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            if error.code in (429, 500, 502, 503, 504) and attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            raise SystemExit(f"D1 API HTTP {error.code}: {detail}") from error
        except urllib.error.URLError as error:
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            raise SystemExit(f"Could not connect to the D1 API: {error}") from error

        if not data.get("success"):
            raise SystemExit(f"D1 API: {data.get('errors') or data}")

        results = data.get("result") or []
        if results and not results[0].get("success", True):
            raise SystemExit(f"D1 API: {results[0].get('error') or results[0]}")
        return


def upload(
    sqlite_path: Path = SQLITE_DB,
    *,
    local: bool = False,
    method: str = "wrangler",
    database: str = "biblioteca",
    truncate: bool = False,
    dry_run: Path | None = None,
    batch_size: int = BATCH_SIZE,
    rebuild_fts: bool = False,
) -> int:
    """Load the `Biblioteca` table and return the number of rows read."""
    rows = read_rows(sqlite_path)
    statements: list[str] = []
    if truncate:
        statements.append(f'DELETE FROM "{TABLE}";')
    statements.extend(iter_insert_statements(rows, batch_size=batch_size))
    if rebuild_fts:
        statements.append(
            'INSERT INTO "biblioteca_fts"("biblioteca_fts") VALUES (\'rebuild\');'
        )

    if dry_run is not None:
        dry_run.parent.mkdir(parents=True, exist_ok=True)
        dry_run.write_text("\n\n".join(statements) + "\n", encoding="utf-8")
        print(f"{len(rows)} rows -> {dry_run} (nothing uploaded)")
        return len(rows)

    if method == "api":
        if local:
            raise SystemExit("--method api only works against remote D1")
        token, account, database_id = _api_config()
        print(
            f"Uploading {len(rows)} rows in {len(statements)} statements "
            f"(D1 API, database {database_id})..."
        )
        for index, statement in enumerate(statements, 1):
            _run_api(
                statement, token=token, account=account, database=database_id
            )
            if index == len(statements) or index % 10 == 0:
                print(f"  {index}/{len(statements)} statements")
    elif method == "wrangler":
        sql = "\n\n".join(statements)
        mode = "local" if local else "remote"
        print(
            f"Uploading {len(rows)} rows in {len(statements)} statements "
            f"(wrangler, D1 {mode})..."
        )
        _run_wrangler(sql, database=database, local=local)
    else:
        raise SystemExit(f"Unknown upload method: {method}")

    print(f"OK: {len(rows)} rows loaded into '{TABLE}'.")
    return len(rows)
