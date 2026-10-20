"""Rutas compartidas del repositorio.

El ETL se ejecuta desde el repositorio (no está pensado para instalarse como
paquete global), así que las rutas se calculan a partir de este archivo:

    tools/etl/src/biblioteca/rutas.py -> raíz del repositorio
"""

from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[4]
DATOS = RAIZ / "data"
DERIVADOS = DATOS / "derived"
ACCBD = DATOS / "biblioteca.accdb"
SQLITE = DERIVADOS / "biblioteca.sqlite"
SEED = DERIVADOS / "seed.sql"
APPS_WEB = RAIZ / "apps" / "web"
