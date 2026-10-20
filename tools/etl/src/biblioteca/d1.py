"""Carga las filas de SQLite en D1 (local o remoto).

Dos formas de subida:

- `--via wrangler` (por defecto): usa el CLI de Wrangler ya autenticado. Es la
  opción cómoda desde tu máquina.
- `--via api`: usa la API HTTP de D1 con un token. Útil desde CI o servidores
  sin `wrangler login`. Requiere:
    CLOUDFLARE_API_TOKEN
    CLOUDFLARE_ACCOUNT_ID
    D1_DATABASE_ID

La carga es idempotente: `INSERT ... ON CONFLICT("ID") DO UPDATE`. Usa
`--truncate` solo si quieres vaciar la tabla antes de cargar.

Uso:
    uv run --project tools/etl biblioteca-etl upload --remote
    uv run --project tools/etl biblioteca-etl upload --local
    uv run --project tools/etl biblioteca-etl upload --remote --via api
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

from .rutas import APPS_WEB, SQLITE
from .seed import LOTE_FILAS, TABLA, leer_filas, sentencias_inserts

API_URL = (
    "https://api.cloudflare.com/client/v4/accounts/{cuenta}"
    "/d1/database/{base}/query"
)
MAX_REINTENTOS = 5


def _ejecutar_wrangler(sql: str, *, database: str, local: bool) -> None:
    """Ejecuta un archivo SQL temporal con `wrangler d1 execute`."""
    with tempfile.NamedTemporaryFile(
        "w", suffix=".sql", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(sql)
        ruta = Path(fh.name)

    modo = "--local" if local else "--remote"
    cmd = [
        "npx",
        "--no-install",
        "wrangler",
        "d1",
        "execute",
        database,
        modo,
        f"--file={ruta}",
    ]
    try:
        resultado = subprocess.run(
            cmd, cwd=APPS_WEB, capture_output=True, text=True, check=False
        )
        if resultado.returncode != 0:
            if resultado.stdout:
                print(resultado.stdout)
            if resultado.stderr:
                print(resultado.stderr, file=sys.stderr)
            raise SystemExit(
                f"`wrangler d1 execute` falló (código {resultado.returncode})."
            )
    finally:
        ruta.unlink(missing_ok=True)


def _api_config() -> tuple[str, str, str]:
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    cuenta = os.environ.get("CLOUDFLARE_ACCOUNT_ID", "").strip()
    base = os.environ.get("D1_DATABASE_ID", "").strip()
    faltan = [
        nombre
        for nombre, valor in (
            ("CLOUDFLARE_API_TOKEN", token),
            ("CLOUDFLARE_ACCOUNT_ID", cuenta),
            ("D1_DATABASE_ID", base),
        )
        if not valor
    ]
    if faltan:
        raise SystemExit(
            "Faltan variables de entorno para --via api: " + ", ".join(faltan)
        )
    return token, cuenta, base


def _ejecutar_api(sql: str, *, token: str, cuenta: str, base: str) -> None:
    """Ejecuta una sentencia con la API HTTP de D1, con reintentos."""
    url = API_URL.format(cuenta=cuenta, base=base)
    cuerpo = json.dumps({"sql": sql}).encode("utf-8")
    cabeceras = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    for intento in range(1, MAX_REINTENTOS + 1):
        peticion = urllib.request.Request(
            url, data=cuerpo, headers=cabeceras, method="POST"
        )
        try:
            with urllib.request.urlopen(peticion, timeout=90) as respuesta:
                datos = json.load(respuesta)
        except urllib.error.HTTPError as err:
            detalle = err.read().decode("utf-8", errors="replace")
            if err.code in (429, 500, 502, 503, 504) and intento < MAX_REINTENTOS:
                time.sleep(2**intento)
                continue
            raise SystemExit(f"D1 API HTTP {err.code}: {detalle}") from err
        except urllib.error.URLError as err:
            if intento < MAX_REINTENTOS:
                time.sleep(2**intento)
                continue
            raise SystemExit(f"No se pudo conectar con la API de D1: {err}") from err

        if not datos.get("success"):
            raise SystemExit(f"D1 API: {datos.get('errors') or datos}")

        resultados = datos.get("result") or []
        if resultados and not resultados[0].get("success", True):
            raise SystemExit(f"D1 API: {resultados[0].get('error') or resultados[0]}")
        return


def cargar(
    sqlite: Path = SQLITE,
    *,
    local: bool = False,
    via: str = "wrangler",
    database: str = "biblioteca",
    truncate: bool = False,
    dry_run: Path | None = None,
    lote: int = LOTE_FILAS,
    rebuild_fts: bool = False,
) -> int:
    """Carga la tabla `Biblioteca` y devuelve el número de filas leídas."""
    filas = leer_filas(sqlite)
    sentencias: list[str] = []
    if truncate:
        sentencias.append(f'DELETE FROM "{TABLA}";')
    sentencias.extend(sentencias_inserts(filas, lote=lote))
    if rebuild_fts:
        sentencias.append(
            'INSERT INTO "biblioteca_fts"("biblioteca_fts") VALUES (\'rebuild\');'
        )

    if dry_run is not None:
        dry_run.parent.mkdir(parents=True, exist_ok=True)
        dry_run.write_text("\n\n".join(sentencias) + "\n", encoding="utf-8")
        print(f"{len(filas)} filas -> {dry_run} (sin subir)")
        return len(filas)

    if via == "api":
        if local:
            raise SystemExit("--via api solo funciona contra D1 remoto")
        token, cuenta, base = _api_config()
        print(
            f"Subiendo {len(filas)} filas en {len(sentencias)} sentencias "
            f"(API D1, base {base})…"
        )
        for i, sentencia in enumerate(sentencias, 1):
            _ejecutar_api(sentencia, token=token, cuenta=cuenta, base=base)
            if i == len(sentencias) or i % 10 == 0:
                print(f"  {i}/{len(sentencias)} sentencias")
    elif via == "wrangler":
        sql = "\n\n".join(sentencias)
        modo = "local" if local else "remoto"
        print(
            f"Subiendo {len(filas)} filas en {len(sentencias)} sentencias "
            f"(wrangler, D1 {modo})…"
        )
        _ejecutar_wrangler(sql, database=database, local=local)
    else:
        raise SystemExit(f"Modo de subida desconocido: {via}")

    print(f"OK: {len(filas)} filas cargadas en '{TABLA}'.")
    return len(filas)
