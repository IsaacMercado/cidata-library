"""Tkinter replica of the Access form `Biblioteca`.

Rebuilds the columnar layout (header, detail with label + field per column,
and navigation footer) and lets you browse, search and edit records.

Usage:
    uv run --project tools/etl biblioteca-gui [data/derived/biblioteca.sqlite]
"""

from __future__ import annotations

import argparse
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from .form_spec import COLUMNS, FIELDS, TABLE, TITLE
from .paths import ACCESS_DB, SQLITE_DB

DEFAULT_SQLITE = SQLITE_DB
DEFAULT_ACCESS = ACCESS_DB


def load_records(path: Path) -> tuple[list[dict], Path | None]:
    """Return rows and the SQLite path so edits can be saved (when possible)."""
    if path.suffix == ".sqlite":
        connection = sqlite3.connect(path)
        connection.row_factory = sqlite3.Row
        columns_sql = ", ".join(f"[{column}]" for column in COLUMNS)
        rows = [
            dict(row)
            for row in connection.execute(f"SELECT {columns_sql} FROM [{TABLE}]")
        ]
        connection.close()
        return rows, path

    from access_parser import AccessParser

    db = AccessParser(str(path))
    data = db.get_table(TABLE).parse()
    count = len(data[COLUMNS[0]])
    rows = [{column: data[column][index] for column in COLUMNS} for index in range(count)]
    return rows, None


class LibraryForm:
    def __init__(self, root: tk.Tk, rows: list[dict], sqlite_path: Path | None) -> None:
        self.root = root
        self.rows = rows
        self.sqlite_path = sqlite_path
        self.filter_text = ""
        self.view = list(range(len(rows)))
        self.position = 0
        self.widgets: dict[str, tk.Widget] = {}

        root.title(TITLE)
        self._build()
        self.show(0)

    def _build(self) -> None:
        root_frame = tk.Frame(self.root, padx=12, pady=8)
        root_frame.pack(fill="both", expand=True)

        header = tk.Frame(root_frame, relief="ridge", bd=1, bg="#d4d0c8")
        header.pack(fill="x", pady=(0, 8))
        tk.Label(
            header,
            text=TITLE,
            font=("TkDefaultFont", 12, "bold"),
            bg="#d4d0c8",
            padx=8,
            pady=4,
        ).pack(side="left")

        detail = tk.Frame(root_frame, relief="sunken", bd=1, bg="white", padx=10, pady=8)
        detail.pack(fill="both", expand=True)

        for index, (column, caption, multiline) in enumerate(FIELDS):
            label = tk.Label(detail, text=f"{caption}", anchor="e", bg="white")
            label.grid(row=index, column=0, sticky="e", padx=(0, 8), pady=2)

            if multiline:
                widget = tk.Text(detail, height=3, width=48, wrap="word")
            else:
                widget = tk.Entry(detail, width=52)
            widget.grid(row=index, column=1, sticky="ew", pady=2)
            if column == "ID":
                widget.configure(state="readonly")
            self.widgets[column] = widget

        detail.columnconfigure(1, weight=1)

        footer = tk.Frame(root_frame, relief="ridge", bd=1, bg="#d4d0c8", padx=6, pady=6)
        footer.pack(fill="x", pady=(8, 0))

        navigation = tk.Frame(footer, bg="#d4d0c8")
        navigation.pack(side="left")
        for text, command in (
            ("|◀", lambda: self.move(0)),
            ("◀", lambda: self.move(self.position - 1)),
            ("▶", lambda: self.move(self.position + 1)),
            ("▶|", lambda: self.move(len(self.view) - 1)),
        ):
            tk.Button(navigation, text=text, width=3, command=command).pack(side="left")

        self.position_label = tk.Label(footer, text="", bg="#d4d0c8")
        self.position_label.pack(side="left", padx=10)

        if self.sqlite_path is not None:
            tk.Button(footer, text="Guardar", command=self.save).pack(side="right")

        search_frame = tk.Frame(footer, bg="#d4d0c8")
        search_frame.pack(side="left", padx=10)
        tk.Label(search_frame, text="Buscar:", bg="#d4d0c8").pack(side="left")
        self.search_entry = tk.Entry(search_frame, width=28)
        self.search_entry.pack(side="left", padx=4)
        self.search_entry.bind("<Return>", lambda _event: self.search())

    def show(self, position: int) -> None:
        if not self.view:
            return
        self.position = max(0, min(position, len(self.view) - 1))
        record = self.rows[self.view[self.position]]
        for column, widget in self.widgets.items():
            value = "" if record.get(column) is None else str(record[column])
            if isinstance(widget, tk.Text):
                widget.delete("1.0", "end")
                widget.insert("1.0", value)
            else:
                was_readonly = str(widget.cget("state")) == "readonly"
                if was_readonly:
                    widget.configure(state="normal")
                widget.delete(0, "end")
                widget.insert(0, value)
                if was_readonly:
                    widget.configure(state="readonly")
        self.position_label.configure(
            text=f"Registro {self.position + 1} de {len(self.view)}"
        )

    def move(self, position: int) -> None:
        self.show(position)

    def search(self) -> None:
        self.filter_text = self.search_entry.get().strip()
        if not self.filter_text:
            self.view = list(range(len(self.rows)))
        else:
            needle = self.filter_text.lower()
            self.view = [
                index
                for index, record in enumerate(self.rows)
                if needle in str(record.get("Texto Ficha") or "").lower()
            ]
        if not self.view:
            messagebox.showinfo(TITLE, f'Sin coincidencias para "{self.filter_text}".')
            self.view = list(range(len(self.rows)))
        self.show(0)

    def save(self) -> None:
        if self.sqlite_path is None or not self.view:
            return
        record = self.rows[self.view[self.position]]
        values = {}
        for column, widget in self.widgets.items():
            if isinstance(widget, tk.Text):
                values[column] = widget.get("1.0", "end-1c")
            else:
                values[column] = widget.get()
        assignments = ", ".join(f"[{column}] = ?" for column in COLUMNS if column != "ID")
        parameters = [values[column] for column in COLUMNS if column != "ID"]
        parameters.append(values["ID"])
        connection = sqlite3.connect(self.sqlite_path)
        connection.execute(
            f"UPDATE [{TABLE}] SET {assignments} WHERE [ID] = ?", parameters
        )
        connection.commit()
        connection.close()
        record.update(values)
        messagebox.showinfo(TITLE, "Registro guardado.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("db", nargs="?", default=None)
    args = parser.parse_args()

    path = (
        Path(args.db)
        if args.db
        else (DEFAULT_SQLITE if DEFAULT_SQLITE.exists() else DEFAULT_ACCESS)
    )
    if not path.exists():
        raise SystemExit(f"{path} not found. Run first: uv run biblioteca-export")

    rows, sqlite_path = load_records(path)
    root = tk.Tk()
    LibraryForm(root, rows, sqlite_path)
    root.mainloop()


if __name__ == "__main__":
    main()
