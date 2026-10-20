"""Exporta la base de datos Microsoft Access a formatos portables.

Genera, en `data/derived/`:

- `biblioteca.csv`: volcado legible de la tabla.
- `biblioteca.sqlite`: copia SQLite (fuente del generador de SQL para D1).
- `schema.sql`: esquema SQL de referencia.

Uso:
    uv run --project tools/etl biblioteca-etl export [ruta.accdb] [directorio_salida]
"""

from __future__ import annotations

import argparse
import csv
import sqlite3
from pathlib import Path

from access_parser import AccessParser

from .rutas import ACCBD, DERIVADOS

OBJECT_TYPES = {
    1: "tabla",
    2: "base",
    3: "contenedor",
    4: "consulta_eliminacion",
    5: "consulta",
    6: "tabla_vinculada",
    -32768: "formulario",
    -32766: "macro",
    -32764: "informe",
    -32761: "modulo",
    -32758: "modulo",  # algunos drivers usan este codigo
    -32757: "propiedades",
}


def _cargar(accdb: Path) -> tuple[AccessParser, dict[str, list]]:
    db = AccessParser(str(accdb))
    tablas: dict[str, list] = {}
    for nombre in db.catalog:
        if not nombre.startswith("MSys") and not nombre.startswith("f_"):
            tablas[nombre] = db.get_table(nombre).parse()
    return db, tablas


def inventario_objetos(db: AccessParser) -> list[tuple[str, str]]:
    filas = db.parse_table("MSysObjects")
    objetos = []
    for nombre, tipo in zip(
        filas.get("Name", []), filas.get("Type", []), strict=False
    ):
        if nombre in (None, "") or tipo is None:
            continue
        nombre = str(nombre)
        if nombre.startswith(("MSys", "f_")):
            continue
        if tipo == 3:  # contenedores de la barra de navegacion
            continue
        objetos.append((nombre, OBJECT_TYPES.get(tipo, f"otro({tipo})")))
    return objetos


def _n_filas(columnas: dict[str, list]) -> int:
    return len(next(iter(columnas.values()))) if columnas else 0


def exportar_csv(tabla: str, columnas: dict[str, list], destino: Path) -> None:
    columnas_nombres = list(columnas)
    with destino.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(columnas_nombres)
        for i in range(_n_filas(columnas)):
            writer.writerow([columnas[c][i] for c in columnas_nombres])


def exportar_sqlite(datos: dict[str, list], destino: Path) -> None:
    if destino.exists():
        destino.unlink()
    con = sqlite3.connect(destino)
    cur = con.cursor()
    for tabla, columnas in datos.items():
        columnas_nombres = list(columnas)
        defs = []
        for c in columnas_nombres:
            if c == "ID":
                defs.append("ID INTEGER PRIMARY KEY")
            else:
                defs.append(f"[{c}] TEXT")
        cur.execute(f"CREATE TABLE [{tabla}] ({', '.join(defs)})")
        marcadores = ", ".join("?" * len(columnas_nombres))
        insert = f"INSERT INTO [{tabla}] VALUES ({marcadores})"
        cur.executemany(
            insert,
            ([columnas[c][i] for c in columnas_nombres] for i in range(_n_filas(columnas))),
        )
    con.commit()
    con.close()


def exportar_esquema(datos: dict[str, list], destino: Path) -> None:
    lineas = []
    for tabla, columnas in datos.items():
        defs = []
        for c in list(columnas):
            if c == "ID":
                defs.append("    ID INTEGER PRIMARY KEY")
            else:
                defs.append(f"    [{c}] TEXT")
        lineas.append(f"CREATE TABLE [{tabla}] (\n" + ",\n".join(defs) + "\n);")
    destino.write_text("\n\n".join(lineas) + "\n", encoding="utf-8")


def exportar_todo(accdb: Path, salida: Path) -> dict[str, int]:
    """Exporta todas las tablas de Access y devuelve {tabla: filas}."""
    if not accdb.exists():
        raise SystemExit(f"No se encontró la base Access: {accdb}")

    salida.mkdir(parents=True, exist_ok=True)
    db, datos = _cargar(accdb)

    print(f"Base de datos: {accdb}")
    print("Objetos encontrados:")
    for nombre, tipo in inventario_objetos(db):
        print(f"  - [{tipo}] {nombre}")

    for tabla, columnas in datos.items():
        exportar_csv(tabla, columnas, salida / f"{tabla.lower()}.csv")
    exportar_sqlite(datos, salida / "biblioteca.sqlite")
    exportar_esquema(datos, salida / "schema.sql")

    conteos = {tabla: _n_filas(columnas) for tabla, columnas in datos.items()}
    for tabla, n in conteos.items():
        print(f"Tabla '{tabla}': {n} filas, {len(datos[tabla])} columnas")
    print(f"Archivos generados en: {salida.resolve()}")
    return conteos


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("accdb", nargs="?", default=str(ACCBD))
    ap.add_argument("salida", nargs="?", default=str(DERIVADOS))
    args = ap.parse_args(argv)

    exportar_todo(Path(args.accdb), Path(args.salida))


if __name__ == "__main__":
    main()
