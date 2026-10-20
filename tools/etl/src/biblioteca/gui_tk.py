"""Réplica en tkinter del formulario Access `Biblioteca`.

Reconstruye el aspecto columnar del formulario (encabezado, detalle con
etiqueta + campo por columna y pie de navegación) y permite recorrer, buscar y
editar los registros.

Uso:
    uv run --project tools/etl biblioteca-gui [data/derived/biblioteca.sqlite]
"""

from __future__ import annotations

import argparse
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .form_spec import CAMPOS, COLUMNAS, TABLA, TITULO
from .rutas import ACCBD, SQLITE

SQLITE_DEFECTO = SQLITE
ACCDB_DEFECTO = ACCBD


def cargar_registros(ruta: Path) -> tuple[list[dict], Path | None]:
    """Devuelve las filas y la ruta de SQLite para poder guardar (si aplica)."""
    if ruta.suffix == ".sqlite":
        con = sqlite3.connect(ruta)
        con.row_factory = sqlite3.Row
        cols = ", ".join(f"[{c}]" for c in COLUMNAS)
        filas = [dict(r) for r in con.execute(f"SELECT {cols} FROM [{TABLA}]")]
        con.close()
        return filas, ruta

    from access_parser import AccessParser

    db = AccessParser(str(ruta))
    datos = db.get_table(TABLA).parse()
    n = len(datos[COLUMNAS[0]])
    filas = [{c: datos[c][i] for c in COLUMNAS} for i in range(n)]
    return filas, None


class FormularioBiblioteca:
    def __init__(self, root: tk.Tk, filas: list[dict], sqlite: Path | None) -> None:
        self.root = root
        self.filas = filas
        self.sqlite = sqlite
        self.filtro = ""
        self.vista = list(range(len(filas)))
        self.pos = 0
        self.widgets: dict[str, tk.Widget] = {}

        root.title(TITULO)
        self._construir()
        self.mostrar(0)

    def _construir(self) -> None:
        raiz = tk.Frame(self.root, padx=12, pady=8)
        raiz.pack(fill="both", expand=True)

        encabezado = tk.Frame(raiz, relief="ridge", bd=1, bg="#d4d0c8")
        encabezado.pack(fill="x", pady=(0, 8))
        tk.Label(
            encabezado,
            text=TITULO,
            font=("TkDefaultFont", 12, "bold"),
            bg="#d4d0c8",
            padx=8,
            pady=4,
        ).pack(side="left")

        detalle = tk.Frame(raiz, relief="sunken", bd=1, bg="white", padx=10, pady=8)
        detalle.pack(fill="both", expand=True)

        for i, (col, caption, multilinea) in enumerate(CAMPOS):
            etiqueta = tk.Label(detalle, text=f"{caption}", anchor="e", bg="white")
            etiqueta.grid(row=i, column=0, sticky="e", padx=(0, 8), pady=2)

            if multilinea:
                widget = tk.Text(detalle, height=3, width=48, wrap="word")
            else:
                widget = tk.Entry(detalle, width=52)
            widget.grid(row=i, column=1, sticky="ew", pady=2)
            if col == "ID":
                widget.configure(state="readonly")
            self.widgets[col] = widget

        detalle.columnconfigure(1, weight=1)

        pie = tk.Frame(raiz, relief="ridge", bd=1, bg="#d4d0c8", padx=6, pady=6)
        pie.pack(fill="x", pady=(8, 0))

        nav = tk.Frame(pie, bg="#d4d0c8")
        nav.pack(side="left")
        for texto, comando in (
            ("|◀", lambda: self.mover(0)),
            ("◀", lambda: self.mover(self.pos - 1)),
            ("▶", lambda: self.mover(self.pos + 1)),
            ("▶|", lambda: self.mover(len(self.vista) - 1)),
        ):
            tk.Button(nav, text=texto, width=3, command=comando).pack(side="left")

        self.lbl_pos = tk.Label(pie, text="", bg="#d4d0c8")
        self.lbl_pos.pack(side="left", padx=10)

        if self.sqlite is not None:
            tk.Button(pie, text="Guardar", command=self.guardar).pack(side="right")

        busqueda = tk.Frame(pie, bg="#d4d0c8")
        busqueda.pack(side="left", padx=10)
        tk.Label(busqueda, text="Buscar:", bg="#d4d0c8").pack(side="left")
        self.entry_busqueda = tk.Entry(busqueda, width=28)
        self.entry_busqueda.pack(side="left", padx=4)
        self.entry_busqueda.bind("<Return>", lambda _e: self.buscar())

    def mostrar(self, pos: int) -> None:
        if not self.vista:
            return
        self.pos = max(0, min(pos, len(self.vista) - 1))
        fila = self.filas[self.vista[self.pos]]
        for col, widget in self.widgets.items():
            valor = "" if fila.get(col) is None else str(fila[col])
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
                widget.insert("1.0", valor)
            else:
                estaba_readonly = str(widget.cget("state")) == "readonly"
                if estaba_readonly:
                    widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, valor)
                if estaba_readonly:
                    widget.configure(state="readonly")
        self.lbl_pos.configure(text=f"Registro {self.pos + 1} de {len(self.vista)}")

    def mover(self, pos: int) -> None:
        self.mostrar(pos)

    def buscar(self) -> None:
        self.filtro = self.entry_busqueda.get().strip()
        if not self.filtro:
            self.vista = list(range(len(self.filas)))
        else:
            aguja = self.filtro.lower()
            self.vista = [
                i
                for i, fila in enumerate(self.filas)
                if aguja in str(fila.get("Texto Ficha") or "").lower()
            ]
        if not self.vista:
            messagebox.showinfo(TITULO, f'Sin coincidencias para "{self.filtro}".')
            self.vista = list(range(len(self.filas)))
        self.mostrar(0)

    def guardar(self) -> None:
        if self.sqlite is None or not self.vista:
            return
        fila = self.filas[self.vista[self.pos]]
        valores = {}
        for col, widget in self.widgets.items():
            if isinstance(widget, tk.Text):
                valores[col] = widget.get("1.0", "end-1c")
            else:
                valores[col] = widget.get()
        asignaciones = ", ".join(f"[{c}] = ?" for c in COLUMNAS if c != "ID")
        parametros = [valores[c] for c in COLUMNAS if c != "ID"]
        parametros.append(valores["ID"])
        con = sqlite3.connect(self.sqlite)
        con.execute(f"UPDATE [{TABLA}] SET {asignaciones} WHERE [ID] = ?", parametros)
        con.commit()
        con.close()
        fila.update(valores)
        messagebox.showinfo(TITULO, "Registro guardado.")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("db", nargs="?", default=None)
    args = ap.parse_args()

    ruta = (
        Path(args.db)
        if args.db
        else (SQLITE_DEFECTO if SQLITE_DEFECTO.exists() else ACCDB_DEFECTO)
    )
    if not ruta.exists():
        raise SystemExit(
            f"No se encontró {ruta}. Ejecuta antes: uv run biblioteca-export"
        )

    filas, sqlite = cargar_registros(ruta)
    root = tk.Tk()
    FormularioBiblioteca(root, filas, sqlite)
    root.mainloop()


if __name__ == "__main__":
    main()
