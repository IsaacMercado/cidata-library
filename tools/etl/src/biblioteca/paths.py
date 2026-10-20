"""Shared repository paths.

The ETL runs from the repository (it is not intended to be installed as a
global package), so paths are derived from this file:

    tools/etl/src/biblioteca/paths.py -> repository root
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
DATA_DIR = ROOT / "data"
DERIVED_DIR = DATA_DIR / "derived"
ACCESS_DB = DATA_DIR / "biblioteca.accdb"
SQLITE_DB = DERIVED_DIR / "biblioteca.sqlite"
SEED_SQL = DERIVED_DIR / "seed.sql"
WEB_APP = ROOT / "apps" / "web"
