// palette.js — global command palette, loaded on every page.
//
// Ctrl-K / Cmd-K (or a click on #palette-open, if present) opens a centered
// overlay that fuzzy-filters entries fetched once from /api/palette.
// Entries: {label, kind, href, hint} where kind is one of
// "page" | "suite" | "stage" | "symbol" | "module".

const STYLE_ID = "jx-palette-style";

const KIND_COLORS = {
  page: "var(--accent, #4a9eff)",
  suite: "var(--ok, #2ecc71)",
  stage: "var(--warn, #e6a23c)",
  symbol: "var(--bad, #e74c3c)",
  module: "var(--muted, #888888)",
};
const KIND_LABELS = {
  symbol: "code name",
};

let items = null; // fetched lazily, cached after first successful fetch
let fetching = null; // in-flight fetch promise
let overlay = null;
let input = null;
let list = null;
let filtered = [];
let selectedIndex = -1;

function injectStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .jx-palette-backdrop {
      position: fixed; inset: 0; background: rgba(0, 0, 0, 0.5);
      display: flex; align-items: flex-start; justify-content: center;
      padding-top: 10vh; z-index: 9999;
    }
    .jx-palette-card {
      width: min(560px, 92vw); max-height: 70vh; display: flex; flex-direction: column;
      background: var(--card, #1e1e1e); color: var(--fg, #eeeeee);
      border: 1px solid var(--line, #333333); border-radius: 8px;
      box-shadow: 0 12px 40px rgba(0, 0, 0, 0.4); overflow: hidden;
    }
    .jx-palette-input {
      width: 100%; box-sizing: border-box; border: none; outline: none;
      padding: 12px 14px; font-size: 15px; background: transparent; color: inherit;
      border-bottom: 1px solid var(--line, #333333);
    }
    .jx-palette-list { overflow-y: auto; margin: 0; padding: 4px; list-style: none; }
    .jx-palette-row {
      display: flex; align-items: center; gap: 8px; padding: 7px 10px;
      border-radius: 6px; cursor: pointer;
    }
    .jx-palette-row.jx-selected { background: var(--line, #333333); }
    .jx-palette-label { flex: 0 0 auto; font-weight: 500; }
    .jx-palette-hint {
      flex: 1 1 auto; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;
      color: var(--muted, #888888); font-size: 12px; text-align: right;
    }
    .jx-palette-badge {
      flex: 0 0 auto; font-size: 10px; text-transform: uppercase; letter-spacing: 0.04em;
      padding: 1px 6px; border-radius: 999px; border: 1px solid currentColor; opacity: 0.85;
    }
    .jx-palette-empty { padding: 16px; color: var(--muted, #888888); text-align: center; font-size: 13px; }
  `;
  document.head.appendChild(style);
}

function unwrap(json) {
  if (json && typeof json === "object" && "data" in json) return json.data;
  return json;
}

function loadItems() {
  if (items) return Promise.resolve(items);
  if (fetching) return fetching;
  fetching = fetch("/api/palette")
    .then((res) => {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then((json) => {
      const data = unwrap(json);
      items = Array.isArray(data) ? data : [];
      return items;
    })
    .catch((err) => {
      items = [];
      renderErrorRow("Could not load palette: " + err.message);
      return items;
    })
    .finally(() => {
      fetching = null;
    });
  return fetching;
}

function renderErrorRow(msg) {
  if (!list) return;
  list.innerHTML = "";
  const li = document.createElement("li");
  li.className = "jx-palette-empty";
  li.textContent = msg;
  list.appendChild(li);
}

function buildOverlay() {
  if (overlay) return overlay;
  injectStyle();

  overlay = document.createElement("div");
  overlay.className = "jx-palette-backdrop";
  overlay.style.display = "none";

  const card = document.createElement("div");
  card.className = "jx-palette-card";
  card.setAttribute("role", "dialog");
  card.setAttribute("aria-modal", "true");

  input = document.createElement("input");
  input.className = "jx-palette-input";
  input.type = "text";
  input.setAttribute("aria-label", "Command palette search");
  input.placeholder = "Jump to page, suite, stage, code name, module…";

  list = document.createElement("ul");
  list.className = "jx-palette-list";

  card.appendChild(input);
  card.appendChild(list);
  overlay.appendChild(card);
  document.body.appendChild(overlay);

  overlay.addEventListener("mousedown", (ev) => {
    if (ev.target === overlay) close();
  });
  input.addEventListener("keydown", onKeydown);
  input.addEventListener("input", () => renderList(input.value));
  input.addEventListener("blur", () => {
    // Keep focus trapped in the input while the palette is open.
    setTimeout(() => {
      if (isOpen()) input.focus();
    }, 0);
  });

  return overlay;
}

function matchesQuery(q, item) {
  if (!q) return true;
  const label = (item.label || "").toLowerCase();
  const hint = (item.hint || "").toLowerCase();
  return label.indexOf(q) !== -1 || hint.indexOf(q) !== -1;
}

function rankOf(q, item) {
  if (!q) return 0;
  const label = (item.label || "").toLowerCase();
  return label.indexOf(q) === 0 ? 0 : 1;
}

function renderList(query) {
  const q = (query || "").trim().toLowerCase();
  const source = items || [];

  filtered = source
    .map((item, idx) => ({ item, idx }))
    .filter(({ item }) => matchesQuery(q, item))
    .sort((a, b) => {
      const ra = rankOf(q, a.item);
      const rb = rankOf(q, b.item);
      if (ra !== rb) return ra - rb;
      return a.idx - b.idx;
    })
    .slice(0, 20)
    .map(({ item }) => item);

  list.innerHTML = "";

  if (filtered.length === 0) {
    const li = document.createElement("li");
    li.className = "jx-palette-empty";
    li.textContent = items === null ? "Loading…" : "No matches";
    list.appendChild(li);
    selectedIndex = -1;
    return;
  }

  filtered.forEach((item, i) => {
    const li = document.createElement("li");
    li.className = "jx-palette-row" + (i === 0 ? " jx-selected" : "");

    const badge = document.createElement("span");
    badge.className = "jx-palette-badge";
    badge.style.color = KIND_COLORS[item.kind] || KIND_COLORS.module;
    badge.textContent = KIND_LABELS[item.kind] || item.kind || "";

    const label = document.createElement("span");
    label.className = "jx-palette-label";
    label.textContent = item.label || "";

    const hint = document.createElement("span");
    hint.className = "jx-palette-hint";
    hint.textContent = item.hint || "";

    li.appendChild(badge);
    li.appendChild(label);
    li.appendChild(hint);

    li.addEventListener("mousedown", (ev) => {
      // Prevent the input from blurring before we navigate.
      ev.preventDefault();
      selectedIndex = i;
      navigateSelected();
    });

    list.appendChild(li);
  });

  selectedIndex = 0;
}

function updateSelectionClasses() {
  const rows = list.querySelectorAll(".jx-palette-row");
  rows.forEach((row, i) => {
    row.classList.toggle("jx-selected", i === selectedIndex);
  });
  const active = rows[selectedIndex];
  if (active && active.scrollIntoView) active.scrollIntoView({ block: "nearest" });
}

function moveSelection(delta) {
  if (filtered.length === 0) return;
  selectedIndex = (selectedIndex + delta + filtered.length) % filtered.length;
  updateSelectionClasses();
}

function navigateSelected() {
  const item = filtered[selectedIndex];
  if (!item || !item.href) return;
  location.href = item.href;
}

function onKeydown(ev) {
  switch (ev.key) {
    case "ArrowDown":
      ev.preventDefault();
      moveSelection(1);
      break;
    case "ArrowUp":
      ev.preventDefault();
      moveSelection(-1);
      break;
    case "Enter":
      ev.preventDefault();
      navigateSelected();
      break;
    case "Escape":
      ev.preventDefault();
      close();
      break;
    case "Tab":
      // Only the input is focusable inside the palette; keep focus there.
      ev.preventDefault();
      break;
    default:
      break;
  }
}

function isOpen() {
  return !!overlay && overlay.style.display !== "none" && overlay.style.display !== "";
}

function open() {
  buildOverlay();
  overlay.style.display = "flex";
  input.value = "";
  input.focus();
  loadItems().then(() => renderList(""));
}

function close() {
  if (!overlay) return;
  overlay.style.display = "none";
}

function toggle() {
  if (isOpen()) {
    close();
  } else {
    open();
  }
}

document.addEventListener("keydown", (ev) => {
  const key = ev.key ? ev.key.toLowerCase() : "";
  if ((ev.ctrlKey || ev.metaKey) && key === "k") {
    ev.preventDefault();
    toggle();
  }
});

document.addEventListener("click", (ev) => {
  const target = ev.target && ev.target.closest ? ev.target.closest("#palette-open") : null;
  if (target) {
    ev.preventDefault();
    open();
  }
});
