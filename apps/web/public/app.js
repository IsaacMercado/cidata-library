// Utilidades compartidas: campos del formulario (mismo orden que Access),
// llamadas a la API y constructor del formulario de edicion.
export const CAMPOS = [
  { clave: "id", etiqueta: "ID", multilinea: false, soloLectura: true },
  { clave: "cota", etiqueta: "Cota", multilinea: false },
  { clave: "titulo", etiqueta: "Titulo", multilinea: false },
  { clave: "coautor", etiqueta: "Coautor", multilinea: false },
  { clave: "temaOMateria", etiqueta: "Tema o Materia", multilinea: false },
  { clave: "series", etiqueta: "Series", multilinea: false },
  { clave: "paginas", etiqueta: "Paginas", multilinea: false },
  { clave: "isbn", etiqueta: "ISBN", multilinea: false },
  { clave: "notas", etiqueta: "Notas", multilinea: true },
  { clave: "codigoCida", etiqueta: "Codigo CIDA", multilinea: false },
  { clave: "ejemplares", etiqueta: "Ejemplares", multilinea: false },
  { clave: "precioUnidad", etiqueta: "Precio Unidad", multilinea: false },
  { clave: "precioTotal", etiqueta: "Precio Total", multilinea: false },
  { clave: "donacion", etiqueta: "Donacion", multilinea: false },
  { clave: "textoFicha", etiqueta: "Texto Ficha:", multilinea: true },
  { clave: "autor", etiqueta: "Autor:", multilinea: false },
  { clave: "lujoRustico", etiqueta: "Lujo/Rústico:", multilinea: false },
];

export function esc(s) {
  return String(s ?? "").replace(/[&<>"']/g, (m) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[m]);
}

export async function api(path, opciones = {}) {
  const r = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opciones,
  });
  const cuerpo = await r.json().catch(() => ({}));
  if (!r.ok) {
    const e = new Error(cuerpo.mensaje || cuerpo.error || `HTTP ${r.status}`);
    e.status = r.status;
    e.codigo = cuerpo.error;
    throw e;
  }
  return cuerpo;
}

/** Construye el formulario de edicion; devuelve funcion que recoge valores. */
export function construirFormulario(contenedor, registro = {}) {
  contenedor.innerHTML = "";
  const controles = {};
  for (const campo of CAMPOS) {
    const fila = document.createElement("div");
    fila.className = "fila";
    const lab = document.createElement("label");
    const idCampo = `campo-${campo.clave}`;
    lab.textContent = campo.etiqueta;
    lab.htmlFor = idCampo;
    fila.appendChild(lab);
    const el = document.createElement(campo.multilinea ? "textarea" : "input");
    if (campo.multilinea) el.rows = 3;
    else el.type = "text";
    el.id = idCampo;
    el.name = campo.clave;
    el.value = registro[campo.clave] ?? "";
    if (campo.soloLectura) {
      el.readOnly = true;
      el.tabIndex = -1;
    } else {
      el.placeholder = campo.etiqueta.replace(/:$/, "");
      el.autocomplete = "off";
    }
    fila.appendChild(el);
    contenedor.appendChild(fila);
    controles[campo.clave] = el;
  }
  return () => {
    const datos = {};
    for (const campo of CAMPOS) {
      if (campo.soloLectura) continue;
      datos[campo.clave] = controles[campo.clave].value;
    }
    return datos;
  };
}

/** Pinta "Entrar" o "email [Salir]" en el <span id="sesion"> de la cabecera. */
export async function actualizarSesion() {
  const el = document.getElementById("sesion");
  if (!el) return;
  try {
    const r = await fetch("/api/auth/yo");
    if (!r.ok) {
      el.innerHTML = `<a href="/login?next=${encodeURIComponent(location.pathname + location.search)}">Entrar</a>`;
      return;
    }
    const { email } = await r.json();
    el.innerHTML =
      `<span class="usuario">${esc(email)}</span> <a href="#" id="salir">Salir</a>`;
    document.getElementById("salir").addEventListener("click", async (e) => {
      e.preventDefault();
      await fetch("/api/auth/logout", { method: "POST" });
      location.reload();
    });
  } catch {
    el.innerHTML = '<a href="/login">Entrar</a>';
  }
}

export function mostrarAviso(id, texto, esError = false) {
  const el = document.getElementById(id);
  el.hidden = false;
  el.className = esError ? "error" : "aviso";
  el.textContent = texto;
}
