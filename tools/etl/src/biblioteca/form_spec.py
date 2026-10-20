"""Especificación del formulario Access `Biblioteca`, reconstruida desde el
blob de diseño (`MSysAccessStorage`).

El formulario original es de tipo *columnar* (un registro a la vez): secciones
EncabezadoDelFormulario / Detalle / PieDelFormulario, con 17 pares
etiqueta + cuadro de texto en el Detalle.
"""

from __future__ import annotations

TABLA = "Biblioteca"
TITULO = "Biblioteca"

# (nombre_columna, caption_etiqueta, multilinea)
# El orden reproduce el del formulario (no el de la tabla).
CAMPOS: list[tuple[str, str, bool]] = [
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

# Única "fórmula" del formulario: su propiedad Filter guardada.
FILTRO_GUARDADO = '([Biblioteca].[Texto Ficha] Like "* titulo*")'
PALABRA_FILTRO = "titulo"

COLUMNAS = [c for c, _, _ in CAMPOS]
