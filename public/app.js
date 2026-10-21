// Shared helpers: form fields (same order as Access), API calls and the edit
// form builder. User-facing labels stay in Spanish; identifiers are English.
export const FIELDS = [
  { key: "id", label: "ID", multiline: false, readOnly: true },
  { key: "callNumber", label: "Cota", multiline: false },
  { key: "title", label: "Titulo", multiline: false },
  { key: "coauthor", label: "Coautor", multiline: false },
  { key: "subject", label: "Tema o Materia", multiline: false },
  { key: "series", label: "Series", multiline: false },
  { key: "pages", label: "Paginas", multiline: false },
  { key: "isbn", label: "ISBN", multiline: false },
  { key: "notes", label: "Notas", multiline: true },
  { key: "cidaCode", label: "Codigo CIDA", multiline: false },
  { key: "copies", label: "Ejemplares", multiline: false },
  { key: "unitPrice", label: "Precio Unidad", multiline: false },
  { key: "totalPrice", label: "Precio Total", multiline: false },
  { key: "donation", label: "Donacion", multiline: false },
  { key: "catalogText", label: "Texto Ficha:", multiline: true },
  { key: "author", label: "Autor:", multiline: false },
  { key: "binding", label: "Lujo/Rústico:", multiline: false },
];

export function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  })[character]);
}

/** Escape an FTS5 snippet, then restore only the server-provided markers. */
export function highlightFragment(fragment) {
  return escapeHtml(fragment)
    .replaceAll("\u0001", "<mark>")
    .replaceAll("\u0002", "</mark>");
}

export async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(body.message || body.error || `HTTP ${response.status}`);
    error.status = response.status;
    error.code = body.error;
    throw error;
  }
  return body;
}

/** Build the edit form; returns a function that collects the current values. */
export function buildForm(container, record = {}) {
  container.innerHTML = "";
  const controls = {};
  for (const field of FIELDS) {
    const row = document.createElement("div");
    row.className = "fila";
    const label = document.createElement("label");
    const fieldId = `field-${field.key}`;
    label.textContent = field.label;
    label.htmlFor = fieldId;
    row.appendChild(label);
    const element = document.createElement(field.multiline ? "textarea" : "input");
    if (field.multiline) element.rows = 3;
    else element.type = "text";
    element.id = fieldId;
    element.name = field.key;
    element.value = record[field.key] ?? "";
    if (field.readOnly) {
      element.readOnly = true;
      element.tabIndex = -1;
    } else {
      element.placeholder = field.label.replace(/:$/, "");
      element.autocomplete = "off";
    }
    row.appendChild(element);
    container.appendChild(row);
    controls[field.key] = element;
  }
  return () => {
    const values = {};
    for (const field of FIELDS) {
      if (field.readOnly) continue;
      values[field.key] = controls[field.key].value;
    }
    return values;
  };
}

/**
 * Render "Entrar" or "email [Salir]" in the header session slot.
 * Returns the signed-in email, or null when there is no active session.
 */
export async function updateSession() {
  const element = document.getElementById("session");
  try {
    const response = await fetch("/api/auth/me");
    if (!response.ok) {
      if (element) {
        element.innerHTML = `<a href="/login?next=${encodeURIComponent(location.pathname + location.search)}">Entrar</a>`;
      }
      return null;
    }
    const { email } = await response.json();
    if (element) {
      element.innerHTML =
        `<span class="usuario">${escapeHtml(email)}</span> <a href="#" id="logout-link">Salir</a>`;
      document.getElementById("logout-link").addEventListener("click", async (event) => {
        event.preventDefault();
        await fetch("/api/auth/logout", { method: "POST" });
        location.reload();
      });
    }
    return email;
  } catch {
    if (element) element.innerHTML = '<a href="/login">Entrar</a>';
    return null;
  }
}

export function showNotice(id, text, isError = false) {
  const element = document.getElementById(id);
  element.hidden = false;
  element.className = isError ? "error" : "aviso";
  element.textContent = text;
}
