"""Generate a self-contained HTML replica of the Access form `Biblioteca`.

Reads the exported SQLite database and writes `data/derived/form.html` with all
records embedded so it can be opened directly in a browser (no server).

Usage:
    uv run --project tools/etl biblioteca-web [data/derived/biblioteca.sqlite] [data/derived/form.html]
"""

from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path

from .form_spec import FIELDS, FILTER_WORD, SAVED_FILTER, TABLE, TITLE
from .paths import DERIVED_DIR, SQLITE_DB

DEFAULT_SQLITE = SQLITE_DB
DEFAULT_HTML = DERIVED_DIR / "form.html"

TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>__TITLE__</title>
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
    <div class="encabezado">__TITLE__</div>
    <div class="detalle" id="detail"></div>
    <div class="pie">
      <button data-nav="first" title="Primero">|&#9664;</button>
      <button data-nav="prev" title="Anterior">&#9664;</button>
      <button data-nav="next" title="Siguiente">&#9654;</button>
      <button data-nav="last" title="Último">&#9654;|</button>
      <span class="pos" id="position"></span>
      <span class="derecha">
        <label for="search">Buscar (Texto Ficha):</label>
        <input id="search" placeholder="__FILTER_WORD__">
        <span class="aviso" title="Filtro guardado en Access: __SAVED_FILTER__">filtro Access</span>
      </span>
    </div>
  </div>
<script>
const FIELDS = __FIELDS__;
const RECORDS = __RECORDS__;
let view = RECORDS.map((_, index) => index);
let position = 0;
const container = document.getElementById("detail");
const controls = {};
for (const [column, caption, multiline] of FIELDS) {
  const row = document.createElement("div");
  row.className = "fila";
  const label = document.createElement("label");
  label.textContent = caption;
  row.appendChild(label);
  const element = document.createElement(multiline ? "textarea" : "input");
  if (multiline) { element.rows = 3; } else { element.type = "text"; }
  if (column === "ID") { element.readOnly = true; }
  row.appendChild(element);
  container.appendChild(row);
  controls[column] = element;
}
function render() {
  if (!view.length) return;
  position = Math.max(0, Math.min(position, view.length - 1));
  const record = RECORDS[view[position]];
  FIELDS.forEach(([column], index) => { controls[column].value = record[index] ?? ""; });
  document.getElementById("position").textContent = `Registro ${position + 1} de ${view.length}`;
}
document.querySelectorAll("[data-nav]").forEach((button) => button.addEventListener("click", () => {
  const action = button.dataset.nav;
  if (action === "first") position = 0;
  else if (action === "prev") position--;
  else if (action === "next") position++;
  else if (action === "last") position = view.length - 1;
  render();
}));
document.getElementById("search").addEventListener("input", (event) => {
  const query = event.target.value.trim().toLowerCase();
  const catalogIndex = FIELDS.findIndex((field) => field[0] === "Texto Ficha");
  view = RECORDS.map((_, index) => index).filter((index) =>
    !query || String(RECORDS[index][catalogIndex] ?? "").toLowerCase().includes(query)
  );
  if (!view.length) view = RECORDS.map((_, index) => index);
  position = 0;
  render();
});
render();
</script>
</body>
</html>
"""


def generate_document(sqlite_path: Path, destination: Path) -> int:
    connection = sqlite3.connect(sqlite_path)
    columns_sql = ", ".join(f"[{column}]" for column, _, _ in FIELDS)
    rows = [
        list(row)
        for row in connection.execute(f"SELECT {columns_sql} FROM [{TABLE}]")
    ]
    connection.close()

    fields = [[column, caption, multiline] for column, caption, multiline in FIELDS]
    html = (
        TEMPLATE.replace("__TITLE__", TITLE)
        .replace("__FILTER_WORD__", FILTER_WORD)
        .replace("__SAVED_FILTER__", SAVED_FILTER)
        .replace("__FIELDS__", json.dumps(fields, ensure_ascii=False))
        .replace("__RECORDS__", json.dumps(rows, ensure_ascii=False))
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(html, encoding="utf-8")
    return len(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sqlite", nargs="?", default=str(DEFAULT_SQLITE))
    parser.add_argument("output", nargs="?", default=str(DEFAULT_HTML))
    args = parser.parse_args()

    sqlite_path = Path(args.sqlite)
    if not sqlite_path.exists():
        raise SystemExit(
            f"{sqlite_path} not found. Run first: uv run biblioteca-export"
        )
    count = generate_document(sqlite_path, Path(args.output))
    print(f"{count} records -> {Path(args.output).resolve()}")


if __name__ == "__main__":
    main()
