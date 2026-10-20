"""Specification of the Access form `Biblioteca`, rebuilt from its design blob
(`MSysAccessStorage`).

The original form is *columnar* (one record at a time): form header / detail /
form footer sections, with 17 label + text-box pairs in the detail section.

Database table and column names stay in Spanish because they are the data
contract. Python identifiers are English.
"""

from __future__ import annotations

TABLE = "Biblioteca"
TITLE = "Biblioteca"

# (column_name, label_caption, multiline)
# The order matches the form (not the table).
FIELDS: list[tuple[str, str, bool]] = [
    ("ID", "ID", False),
    ("Cota", "Cota", False),
    ("Titulo", "Titulo", False),
    ("Coautor", "Coautor", False),
    ("Tema o Materia", "Tema o Materia", False),
    ("Series", "Series", False),
    ("Paginas", "Paginas", False),
    ("ISBN", "ISBN", False),
    ("Notas", "Notas", True),
    ("Codigo CIDA", "Codigo CIDA", False),
    ("Ejemplares", "Ejemplares", False),
    ("Precio Unidad", "Precio Unidad", False),
    ("Precio Total", "Precio Total", False),
    ("Donacion", "Donacion", False),
    ("Texto Ficha", "Texto Ficha:", True),
    ("Autor", "Autor:", False),
    ("Lujo/Rústico", "Lujo/Rústico:", False),
]

# The only "formula" in the form: its saved Filter property.
SAVED_FILTER = '([Biblioteca].[Texto Ficha] Like "* titulo*")'
FILTER_WORD = "titulo"

COLUMNS = [column for column, _, _ in FIELDS]
