"""Genera una réplica HTML autocontenida del formulario Access `Biblioteca`.

Lee el SQLite exportado y escribe `data/derived/form.html` con todos los
registros embebidos para poder abrirlo directamente en el navegador (sin
servidor).

Uso:
    uv run --project tools/etl biblioteca-web [data/derived/biblioteca.sqlite] [data/derived/form.html]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .form_spec import CAMPOS, FILTRO_GUARDADO, PALABRA_FILTRO, TABLA, TITULO
from .rutas import DERIVADOS, SQLITE

SQLITE_DEFECTO = SQLITE
HTML_DEFECTO = DERIVADOS / "form.html"

PLANTILLA = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITULO__</title>
<style>
  :root { --gris: #d4d0c8; --borde: #808080; }
  * { box-sizing: border-box; }
  body { margin: 0; background: #7a7a7a; font-family: "Segoe UI", Tahoma, Arial, sans-serif; font-size: 13px; }
  .ventana { max-width: 640px; margin: 24px auto; background: var(--gris); border: 2px ridge #fff; padding: 6px; }
  .encabezado { background: var(--gris); border: 1px solid var(--borde); padding: 4px 8px; font-weight: bold; }
  .detalle { background: #fff; border: 1px solid var(--borde); padding: 10px; }
  .fila { display: grid; grid-template-columns: 150px 1fr; gap: 8px; align-items: start; margin-bottom: 4px; }
  .fila label { text-align: right; padding-top: 3px; color: #000; }
  .fila input, .fila textarea { width: 100%; font: inherit; padding: 2px 4px; border: 1px solid #7f9db9; background: #fff; }
  .fila input[readonly] { background: var(--gris); color: #444; }
  .pie { margin-top: 8px; border: 1px solid var(--borde); padding: 6px; display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
  button { font: inherit; padding: 2px 8px; background: var(--gris); border: 1px outset #fff; cursor: pointer; }
  button:active { border-style: inset; }
  .pos { min-width: 130px; }
  .derecha { margin-left: auto; display: flex; gap: 6px; align-items: center; }
  .aviso { background: #ffffcc; color: #333; padding: 2px 8px; font-style: italic; }
</style>
</head>
<body>
  <div class="ventana">
    <div class="encabezado">__TITULO__</div>
    <div class="detalle" id="detalle"></div>
    <div class="pie">
      <button data-nav="first" title="Primero">|&#9664;</button>
      <button data-nav="prev" title="Anterior">&#9664;</button>
      <button data-nav="next" title="Siguiente">&#9654;</button>
      <button data-nav="last" title="Último">&#9654;|</button>
      <span class="pos" id="pos"></span>
      <span class="derecha">
        <label for="buscar">Buscar (Texto Ficha):</label>
        <input id="buscar" placeholder="__PALABRA__">
        <span class="aviso" title="Filtro guardado en Access: __FILTRO__">filtro Access</span>
      </span>
    </div>
  </div>
<script>
const CAMPOS = __CAMPOS__;
const REGISTROS = __DATOS__;
let vista = REGISTROS.map((_, i) => i);
let pos = 0;
const cont = document.getElementById("detalle");
const controles = {};
for (const [col, caption, multilinea] of CAMPOS) {
  const fila = document.createElement("div");
  fila.className = "fila";
  const lab = document.createElement("label");
  lab.textContent = caption;
  fila.appendChild(lab);
  const el = document.createElement(multilinea ? "textarea" : "input");
  if (multilinea) { el.rows = 3; } else { el.type = "text"; }
  if (col === "ID") { el.readOnly = true; }
  fila.appendChild(el);
  cont.appendChild(fila);
  controles[col] = el;
}
function mostrar() {
  if (!vista.length) return;
  pos = Math.max(0, Math.min(pos, vista.length - 1));
  const fila = REGISTROS[vista[pos]];
  CAMPOS.forEach(([col], i) => { controles[col].value = fila[i] ?? ""; });
  document.getElementById("pos").textContent = `Registro ${pos + 1} de ${vista.length}`;
}
document.querySelectorAll("[data-nav]").forEach(b => b.addEventListener("click", () => {
  const a = b.dataset.nav;
  if (a === "first") pos = 0;
  else if (a === "prev") pos--;
  else if (a === "next") pos++;
  else if (a === "last") pos = vista.length - 1;
  mostrar();
}));
document.getElementById("buscar").addEventListener("input", (e) => {
  const q = e.target.value.trim().toLowerCase();
  vista = REGISTROS.map((_, i) => i).filter(i => !q || String(REGISTROS[i][CAMPOS.findIndex(c => c[0] === "Texto Ficha")] ?? "").toLowerCase().includes(q));
  if (!vista.length) vista = REGISTROS.map((_, i) => i);
  pos = 0;
  mostrar();
});
mostrar();
</script>
</body>
</html>
"""


def generar(sqlite: Path, destino: Path) -> int:
    con = sqlite3.connect(sqlite)
    cols = ", ".join(f"[{c}]" for c, _, _ in CAMPOS)
    filas = [list(r) for r in con.execute(f"SELECT {cols} FROM [{TABLA}]")]
    con.close()

    campos = [[c, cap, multi] for c, cap, multi in CAMPOS]
    html = (
        PLANTILLA.replace("__TITULO__", TITULO)
        .replace("__PALABRA__", PALABRA_FILTRO)
        .replace("__FILTRO__", FILTRO_GUARDADO)
        .replace("__CAMPOS__", json.dumps(campos, ensure_ascii=False))
        .replace("__DATOS__", json.dumps(filas, ensure_ascii=False))
    )
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(html, encoding="utf-8")
    return len(filas)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("sqlite", nargs="?", default=str(SQLITE_DEFECTO))
    ap.add_argument("salida", nargs="?", default=str(HTML_DEFECTO))
    args = ap.parse_args()

    ruta = Path(args.sqlite)
    if not ruta.exists():
        raise SystemExit(
            f"No se encontró {ruta}. Ejecuta antes: uv run biblioteca-export"
        )
    n = generar(ruta, Path(args.salida))
    print(f"{n} registros -> {Path(args.salida).resolve()}")


if __name__ == "__main__":
    main()
