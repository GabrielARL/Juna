// source.js — behavior for the /source page: symbol list filter, hash-based
// routing into a persistent inspector panel, and a vis-network ego graph.

const STYLE_ID = "jx-source-style";

let currentData = null;
let network = null; // active vis.Network instance, if any
const PAGE_ROOT = document.querySelector("[data-source-mode]");
const PAGE_MODE =
  (PAGE_ROOT && PAGE_ROOT.dataset && PAGE_ROOT.dataset.sourceMode) ||
  "inspector";

function injectStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .jx-src-section { margin: 0 0 16px; }
    .jx-src-heading {
      font-variant: small-caps; letter-spacing: 0.04em; font-size: 12px;
      color: var(--muted, #888888); margin-bottom: 4px;
    }
    .jx-src-name { font-weight: 700; font-family: monospace; font-size: 16px; }
    .jx-src-sub { color: var(--muted, #888888); font-size: 12px; margin-top: 2px; }
    .jx-src-pre {
      background: var(--bg, #161616); border: 1px solid var(--line, #333333);
      border-radius: 6px; padding: 8px 10px; overflow-x: auto; font-size: 12.5px;
      white-space: pre; margin: 0;
    }
    .jx-src-mono { font-family: monospace; font-size: 13px; }
    .jx-src-muted { color: var(--muted, #888888); }
    .jx-src-italic { font-style: italic; }
    .jx-src-footnote { font-size: 11px; margin-top: 6px; }
    .jx-src-chip {
      display: inline-block; font-family: monospace; font-size: 12px;
      border: 1px solid var(--line, #333333); border-radius: 999px; padding: 2px 9px;
      margin: 2px 6px 2px 0; text-decoration: none; color: var(--fg, #eeeeee);
    }
    .jx-src-clickable-line {
      display: block; font-family: monospace; font-size: 12.5px; padding: 3px 0;
      text-decoration: none; color: var(--fg, #eeeeee); border-bottom: 1px dashed transparent;
    }
    .jx-src-chip:hover, .jx-src-clickable-line:hover {
      color: var(--accent, #4a9eff); border-color: var(--accent, #4a9eff);
    }
    .jx-src-actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 18px; }
    .jx-src-action-btn {
      font-size: 12px; padding: 5px 12px; border-radius: 6px; border: 1px solid var(--line, #333333);
      background: var(--card, #1e1e1e); color: var(--fg, #eeeeee); cursor: pointer;
      text-decoration: none; font: inherit;
    }
    .jx-src-action-btn:hover { border-color: var(--accent, #4a9eff); color: var(--accent, #4a9eff); }
    .jx-src-error { color: var(--bad, #e74c3c); padding: 12px 0; }
    .jx-src-details summary { cursor: pointer; color: var(--muted, #888888); font-size: 12px; margin-bottom: 4px; }
    .jx-src-field-search {
      width: 100%; padding: 5px 8px; margin-bottom: 7px;
      border: 1px solid var(--line, #333333); border-radius: 6px;
      background: var(--bg, #161616); color: var(--fg, #eeeeee);
    }
    .jx-src-field {
      padding: 5px 0; border-bottom: 1px solid var(--line, #333333);
      font-size: 12px;
    }
  `;
  document.head.appendChild(style);
}

function unwrap(json) {
  if (json && typeof json === "object" && "data" in json) return json.data;
  return json;
}

// ---------- symbol list filter ----------

function filterSymbols(query) {
  const symlist = document.getElementById("symlist");
  if (!symlist) return;
  const q = query.trim().toLowerCase();

  symlist.querySelectorAll("a.symlink").forEach((link) => {
    const name = (link.dataset.name || "").toLowerCase();
    link.style.display = !q || name.indexOf(q) !== -1 ? "" : "none";
  });
  symlist.querySelectorAll("details.symgroup").forEach((group) => {
    const visible = Array.prototype.some.call(
      group.querySelectorAll("a.symlink"),
      (link) => link.style.display !== "none"
    );
    group.style.display = visible ? "" : "none";
  });
}

// ---------- hash routing ----------

function parseHash() {
  const m = (location.hash || "").match(/^#(?:sym|type)=(.+)$/);
  if (!m) return null;
  try {
    return decodeURIComponent(m[1]);
  } catch (e) {
    return m[1];
  }
}

function onHashChange() {
  const token = parseHash();
  if (token) loadSymbol(token);
}

function loadSymbol(token) {
  fetch("/api/symbol/" + encodeURIComponent(token))
    .then((res) => {
      if (res.status === 404) {
        renderNotFound();
        return null;
      }
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then((json) => {
      if (json !== null) renderInspector(unwrap(json));
    })
    .catch((err) => {
      setInspectorMessage("Could not load source definition: " + err.message);
    });
}

// ---------- inspector building blocks ----------

function section(title, contentNode) {
  const wrap = document.createElement("div");
  wrap.className = "jx-src-section";
  const h = document.createElement("div");
  h.className = "jx-src-heading";
  h.textContent = title;
  wrap.appendChild(h);
  wrap.appendChild(contentNode);
  return wrap;
}

function textDiv(text) {
  const d = document.createElement("div");
  d.textContent = text;
  return d;
}

function firstDefined(...vals) {
  for (const v of vals) {
    if (v !== undefined && v !== null) return v;
  }
  return undefined;
}

// Renders a section made of <a> links (chips or clickable lines), with an
// optional muted fallback line when the source array is empty.
function buildLinkListSection(title, items, className, mapItem, emptyText) {
  const arr = Array.isArray(items) ? items : [];
  const content = document.createElement("div");
  if (arr.length === 0) {
    if (!emptyText) return null;
    content.className = "jx-src-muted";
    content.textContent = emptyText;
    return section(title, content);
  }
  arr.forEach((item) => {
    const info = mapItem(item);
    const a = document.createElement("a");
    a.className = className;
    a.href = info.href;
    a.textContent = info.text;
    if (info.title) a.title = info.title;
    content.appendChild(a);
  });
  return section(title, content);
}

function buildHeaderSection(data) {
  const wrap = document.createElement("div");
  wrap.className = "jx-src-section";
  const label = textDiv("Code name");
  label.className = "jx-src-heading";
  const name = textDiv(data.name || "(unnamed)");
  name.className = "jx-src-name";
  const sub = textDiv([data.kind, data.module].filter(Boolean).join(" · "));
  sub.className = "jx-src-sub";
  wrap.appendChild(label);
  wrap.appendChild(name);
  wrap.appendChild(sub);
  return wrap;
}

function buildPreSection(title, text) {
  if (!text) return null;
  const pre = document.createElement("pre");
  pre.className = "jx-src-pre";
  pre.textContent = text;
  return section(title, pre);
}

function buildPurposeSection(data) {
  const content = document.createElement("div");
  if (data.doc) {
    content.textContent = data.doc;
  } else {
    content.className = "jx-src-muted jx-src-italic";
    content.textContent = "No source docstring";
  }
  return section("Purpose", content);
}

function buildDefinedAtSection(data) {
  if (!data.file) return null;
  const content = document.createElement("div");
  const loc = textDiv(data.file + (data.line ? ":" + data.line : ""));
  loc.className = "jx-src-mono";
  content.appendChild(loc);

  if (data.src) {
    const details = document.createElement("details");
    details.className = "jx-src-details";
    const summary = document.createElement("summary");
    summary.textContent = "source excerpt";
    const pre = document.createElement("pre");
    pre.className = "jx-src-pre";
    pre.textContent = data.src;
    details.appendChild(summary);
    details.appendChild(pre);
    content.appendChild(details);
  }
  return section("Defined at", content);
}

function buildFieldsSection(data) {
  const fields = Array.isArray(data.fields) ? data.fields : [];
  if (!fields.length) return null;
  const content = document.createElement("div");
  const search = document.createElement("input");
  search.className = "jx-src-field-search";
  search.placeholder = "filter " + fields.length + " fields…";
  const list = document.createElement("div");
  fields.forEach((field) => {
    const row = document.createElement("div");
    row.className = "jx-src-field";
    row.dataset.search = [
      field.name, field.type, field.default, field.comment,
    ].filter(Boolean).join(" ").toLowerCase();
    const declaration = document.createElement("code");
    declaration.textContent =
      field.name + "::" + field.type +
      (field.default ? " = " + field.default : "");
    row.appendChild(declaration);
    if (field.comment) {
      const comment = document.createElement("div");
      comment.className = "jx-src-muted";
      comment.textContent = field.comment;
      row.appendChild(comment);
    }
    list.appendChild(row);
  });
  search.addEventListener("input", () => {
    const query = search.value.trim().toLowerCase();
    list.querySelectorAll(".jx-src-field").forEach((row) => {
      row.hidden = Boolean(query) && !row.dataset.search.includes(query);
    });
  });
  content.appendChild(search);
  content.appendChild(list);
  return section("Fields (" + fields.length + ")", content);
}

function buildChainSection(data) {
  return buildLinkListSection(
    "Chain role",
    data.chain_stages,
    "jx-src-chip",
    (s) => ({ href: "/chain#" + s.id, text: s.title || String(s.id) }),
    "Not part of a declared chain stage"
  );
}

function buildDispatchSection(data) {
  return buildLinkListSection("Dispatch", data.overloads, "jx-src-clickable-line", (o) => ({
    href: "#sym=" + encodeURIComponent(o.id),
    text: o.sig || "",
    title: o.file ? o.file + (o.line ? ":" + o.line : "") : undefined,
  }));
}

function buildRefsSection(title, refs) {
  return buildLinkListSection(title, refs, "jx-src-chip", (r) => ({
    href: "#sym=" + encodeURIComponent(r.id),
    text: r.name || String(r.id),
    title: r.kind,
  }));
}

function buildFacadesSection(data) {
  return buildLinkListSection(
    "Public constructor facades",
    data.facades,
    "jx-src-chip",
    (facade) => ({
      href: "/source/graph?receiver=" +
        encodeURIComponent(
          {
            JunaOFDMFEC: "ofdm_fec",
            // Backward-compatible facade; canonical links use JunaOFDMFEC.
            JunaStandard: "ofdm_fec",
            JunaPartialFFT: "partial-fft",
            JunaLite: "lite",
            JunaProfiledCzFrame: "profiled_cz",
            JunaCrcProfiledCzFrame: "profiled_cz",
            JunaCrcConditionedJointCwzFrame: "profiled_cz",
          }[facade.name] || ""
        ) + "#sym=" + encodeURIComponent(facade.id),
      text: facade.name,
    })
  );
}

function buildEvidenceSection(evidence) {
  if (!evidence || typeof evidence !== "object") return null;
  const content = document.createElement("div");
  let any = false;

  const edges = evidence.static_call_edges;
  if (edges) {
    const out = firstDefined(edges.out, edges.outbound, edges.n_out, 0);
    const inn = firstDefined(edges.in, edges.inbound, edges.n_in, 0);
    content.appendChild(textDiv("Static call edges: " + out + " out · " + inn + " in"));
    any = true;
  }
  if (evidence.interface_implementation) {
    content.appendChild(textDiv("Interface implementation: " + evidence.interface_implementation));
    any = true;
  }
  (Array.isArray(evidence.direct_test_references) ? evidence.direct_test_references : []).forEach((ref) => {
    const lineNums = Array.isArray(ref.lines) ? ref.lines.join(", ") : ref.lines != null ? String(ref.lines) : "";
    const row = document.createElement("div");
    const a = document.createElement("a");
    a.href = "/tests#" + ref.suite;
    a.textContent = "Direct test reference: " + ref.suite + " (lines " + lineNums + ")";
    row.appendChild(a);
    content.appendChild(row);
    any = true;
  });
  (Array.isArray(evidence.suite_wide_associations) ? evidence.suite_wide_associations : []).forEach((suite) => {
    content.appendChild(textDiv("Suite-wide association: " + suite));
    any = true;
  });
  (Array.isArray(evidence.runtime_results) ? evidence.runtime_results : []).forEach((r) => {
    content.appendChild(textDiv("Runtime result (browser-recorded): " + r.suite + " " + r.status));
    any = true;
  });

  if (!any) return null;
  const footnote = textDiv("Static edges and references never imply the code executed.");
  footnote.className = "jx-src-muted jx-src-footnote";
  content.appendChild(footnote);
  return section("Evidence", content);
}

function actionLink(text, href) {
  const a = document.createElement("a");
  a.className = "jx-src-action-btn";
  a.href = href;
  a.textContent = text;
  return a;
}

function buildActionsSection(data) {
  const wrap = document.createElement("div");
  wrap.className = "jx-src-actions";

  const focusBtn = document.createElement("button");
  focusBtn.type = "button";
  focusBtn.className = "jx-src-action-btn";
  focusBtn.textContent = "Focus call graph";
  focusBtn.addEventListener("click", () => focusGraph(data));

  const stages = Array.isArray(data.chain_stages) ? data.chain_stages : [];
  const chainHref = stages.length > 0 ? "/chain#" + stages[0].id : "/chain";

  wrap.appendChild(actionLink(
    "Open in Source definitions",
    "/source#sym=" + encodeURIComponent(data.name || "") +
      (data.module ? "&module=" + encodeURIComponent(data.module) : "") +
      (data.file ? "&file=" + encodeURIComponent(data.file) : "") +
      (data.line ? "&line=" + encodeURIComponent(data.line) : "")
  ));
  wrap.appendChild(focusBtn);
  const evidence = data.evidence || {};
  const direct = evidence.direct_test_references || [];
  const suites = evidence.suite_wide_associations || [];
  const suite = (direct[0] && direct[0].suite) || suites[0];
  wrap.appendChild(actionLink(
    "Show evidence",
    "/coverage" + (suite ? "?suite=" + encodeURIComponent(suite) : "")
  ));
  wrap.appendChild(actionLink("Show chain", chainHref));
  wrap.appendChild(actionLink(
    "Open graph context",
    "/source/graph?symbol_id=" + encodeURIComponent(data.id) +
      "#sym=" + encodeURIComponent(data.id)
  ));
  return wrap;
}

function renderInspector(data) {
  currentData = data;
  const inspector = document.getElementById("inspector");
  if (!inspector) return;
  inspector.innerHTML = "";

  [
    buildHeaderSection(data),
    buildPreSection("Signature", data.sig),
    buildPurposeSection(data),
    buildDefinedAtSection(data),
    buildFieldsSection(data),
    buildChainSection(data),
    buildFacadesSection(data),
    buildRefsSection("Interface implementations", data.interface_methods),
    buildDispatchSection(data),
    buildRefsSection("Calls (static)", data.calls),
    buildRefsSection("Called by (static)", data.callers),
    buildEvidenceSection(data.evidence),
    buildActionsSection(data),
  ].forEach((node) => {
    if (node) inspector.appendChild(node);
  });

  if (PAGE_MODE !== "graph") focusGraph(data);
}

function setInspectorMessage(text) {
  const inspector = document.getElementById("inspector");
  if (!inspector) return;
  inspector.innerHTML = "";
  const div = textDiv(text);
  div.className = "jx-src-error";
  inspector.appendChild(div);
}

function renderNotFound() {
  currentData = null;
  setInspectorMessage("Source definition not found");
  clearEgograph();
}

// ---------- ego graph ----------

const KIND_SHAPES = { function: "dot", const: "square", struct: "diamond", type: "diamond", module: "hexagon", stage: "box" };
const KIND_COLOR_VARS = { function: "--ok", const: "--warn", struct: "--bad", type: "--bad", module: "--muted", stage: "--accent" };
const KIND_COLOR_FALLBACKS = { function: "#2ecc71", const: "#e6a23c", struct: "#e74c3c", type: "#e74c3c", module: "#888888", stage: "#4a9eff" };
const SELF_NODE_ID = "__jx_self__";

function cssVar(name, fallback) {
  const val = getComputedStyle(document.documentElement).getPropertyValue(name);
  return val && val.trim() ? val.trim() : fallback;
}

function shapeForKind(kind) {
  return KIND_SHAPES[kind] || "ellipse";
}

function colorForKind(kind) {
  return cssVar(KIND_COLOR_VARS[kind] || "--line", KIND_COLOR_FALLBACKS[kind] || "#666666");
}

function nodeFor(item, fontColor) {
  const color = colorForKind(item.kind || "");
  let label = item.name || String(item.id);
  if (item.overload_count > 1) label += " ×" + item.overload_count;
  if (item.kind === "stage" && item.symbol_count !== undefined) {
    label += "\n" + item.symbol_count + " implementation source definition" +
      (item.symbol_count === 1 ? "" : "s");
  }
  return {
    id: item.id,
    label: label,
    shape: shapeForKind(item.kind || ""),
    color: { background: color, border: color },
    font: { color: fontColor },
    title: [item.name, item.kind, item.module, item.detail]
      .filter(Boolean).join(" · "),
  };
}

function clearEgograph() {
  const container = document.getElementById("egograph");
  if (network) {
    try {
      network.destroy();
    } catch (e) {
      // ignore
    }
    network = null;
  }
  if (container) container.innerHTML = "";
}

function markCanvasPaint(container) {
  const canvas = container && container.querySelector("canvas");
  if (!canvas || !canvas.width || !canvas.height) return false;
  try {
    const pixels = canvas.getContext("2d").getImageData(
      0, 0, canvas.width, canvas.height
    ).data;
    let painted = 0;
    // Sample every fourth physical pixel. Nodes, labels, or edges are enough
    // to prove that this is not the blank-canvas regression.
    for (let i = 3; i < pixels.length; i += 16) {
      if (pixels[i] !== 0) {
        painted += 1;
        if (painted >= 8) break;
      }
    }
    container.dataset.graphPaint = painted >= 8 ? "painted" : "blank";
    container.dataset.paintedSamples = String(painted);
    return painted >= 8;
  } catch (e) {
    container.dataset.graphPaint = "unreadable";
    return false;
  }
}

function activateNetwork(container, activeNetwork) {
  container.dataset.graphPaint = "pending";
  const draw = () => {
    if (network !== activeNetwork) return;
    try {
      activeNetwork.fit({ animation: false });
      activeNetwork.redraw();
    } catch (e) {
      container.dataset.graphPaint = "error";
      return;
    }
    markCanvasPaint(container);
  };
  requestAnimationFrame(() => requestAnimationFrame(draw));
  setTimeout(draw, 250);
  setTimeout(() => {
    if (network !== activeNetwork || markCanvasPaint(container)) return;
    activeNetwork.setOptions({ physics: false });
    draw();
  }, 1200);
}

function focusGraph(data) {
  const container = document.getElementById("egograph");
  if (!container) return;

  if (typeof vis === "undefined") {
    clearEgograph();
    const note = textDiv("diagram library unavailable");
    note.className = "jx-src-muted";
    container.appendChild(note);
    return;
  }
  clearEgograph();

  const fontColor = getComputedStyle(document.body).color;
  const accent = cssVar("--accent", "#4a9eff");
  const nodes = [
    {
      id: SELF_NODE_ID,
      label: data.name || "",
      shape: "dot",
      size: 26,
      color: { background: accent, border: accent },
      font: { color: fontColor },
      title: [data.name, data.kind, data.module].filter(Boolean).join(" · "),
    },
  ];
  const edges = [];
  const seen = new Set([SELF_NODE_ID]);

  (Array.isArray(data.callers) ? data.callers : []).forEach((c) => {
    if (!seen.has(c.id)) {
      seen.add(c.id);
      nodes.push(nodeFor(c, fontColor));
    }
    edges.push({ from: c.id, to: SELF_NODE_ID, arrows: "to" });
  });
  (Array.isArray(data.calls) ? data.calls : []).forEach((c) => {
    if (!seen.has(c.id)) {
      seen.add(c.id);
      nodes.push(nodeFor(c, fontColor));
    }
    edges.push({ from: SELF_NODE_ID, to: c.id, arrows: "to" });
  });

  network = new vis.Network(
    container,
    { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) },
    {
      layout: { randomSeed: 42 },
      physics: { stabilization: false },
      edges: { arrows: { to: { enabled: true } }, color: { color: cssVar("--line", "#666666") } },
      interaction: { hover: true },
    }
  );
  activateNetwork(container, network);

  const onSelect = (params) => {
    const nid = params.nodes && params.nodes[0];
    if (nid && nid !== SELF_NODE_ID) location.hash = "#sym=" + nid;
  };
  network.on("click", onSelect);
  network.on("doubleClick", onSelect);
}

function renderContextGraph(data) {
  const container = document.getElementById("egograph");
  const contextBox = document.getElementById("source-context");
  if (!container) return;
  clearEgograph();
  if (contextBox) {
    contextBox.innerHTML = "";
    const prefix = document.createElement("b");
    prefix.textContent = "Graph context: ";
    contextBox.appendChild(prefix);
    const contexts = Array.isArray(data.context) ? data.context : [];
    if (!contexts.length) {
      contextBox.appendChild(document.createTextNode(
        "all code names · narrow from Home, Tests, Map, Chain, or Coverage"
      ));
    }
    contexts.forEach((ctx) => {
      const chip = document.createElement("span");
      chip.className = "jx-src-chip";
      chip.textContent = ctx.label;
      contextBox.appendChild(chip);
    });
    const noun = data.view === "stages" ? "stages" : "grouped code names";
    const edgeNoun = data.view === "stages" ? "declared transitions" : "static calls";
    contextBox.appendChild(document.createTextNode(
      " · " + data.nodes.length + " " + noun + " · " + data.edges.length +
      " " + edgeNoun
    ));
  }
  const showAll = document.getElementById("graph-show-all");
  if (showAll) {
    showAll.textContent = data.view === "all"
      ? "Hide disconnected code names"
      : "Show all code names";
  }
  if (typeof vis === "undefined") {
    container.textContent = "diagram library unavailable";
    return;
  }
  const fontColor = getComputedStyle(document.body).color;
  const nodes = data.nodes.map((item) => nodeFor(item, fontColor));
  const nodeIndex = new Map(data.nodes.map((node) => [node.id, node]));
  const edges = data.edges.map((edge, index) => ({
    id: "edge-" + index, from: edge.from, to: edge.to, arrows: "to",
    dashes: Boolean(edge.condition),
    title: edge.condition
      ? edge.condition
      : (data.view === "stages"
        ? "Declared receiver-stage flow"
        : "Static call edge — not runtime execution"),
  }));
  const edgeIndex = new Map(edges.map((edge) => [edge.id, edge]));
  network = new vis.Network(
    container,
    { nodes: new vis.DataSet(nodes), edges: new vis.DataSet(edges) },
    {
      layout: { randomSeed: 42 },
      physics: { stabilization: false },
      edges: { color: { color: cssVar("--line", "#666666") } },
      interaction: { hover: true, navigationButtons: true },
    }
  );
  activateNetwork(container, network);
  network.on("click", (params) => {
    const id = params.nodes && params.nodes[0];
    if (id !== undefined) {
      const selected = nodeIndex.get(id);
      if (selected && selected.kind === "stage") {
        openStage(selected.stage_id);
        return;
      }
      location.hash = "#sym=" + encodeURIComponent(id);
      return;
    }
    const edgeId = params.edges && params.edges[0];
    if (edgeId !== undefined) {
      const edge = edgeIndex.get(edgeId);
      const from = nodeIndex.get(edge.from);
      const to = nodeIndex.get(edge.to);
      const inspector = document.getElementById("inspector");
      inspector.innerHTML =
        '<div class="jx-src-section"><div class="jx-src-name">' +
        'Static call edge</div><div class="jx-src-sub">lexical evidence</div>' +
        '</div><div class="jx-src-section"><div class="jx-src-heading">' +
        'Relationship</div><a class="jx-src-chip" href="#sym=' +
        encodeURIComponent(from.id) + '">' + from.name + '</a> → ' +
        '<a class="jx-src-chip" href="#sym=' +
        encodeURIComponent(to.id) + '">' + to.name + '</a></div>' +
        '<div class="note">The analyzer found a lexical call. This does not ' +
        'establish that the call executed at runtime.</div>';
    }
  });
  network.on("doubleClick", (params) => {
    const id = params.nodes && params.nodes[0];
    if (id !== undefined) {
      const selected = nodeIndex.get(id);
      if (selected && selected.kind === "stage") {
        openStage(selected.stage_id);
        return;
      }
      fetch("/api/symbol/" + encodeURIComponent(id))
        .then((res) => res.json())
        .then((json) => focusGraph(unwrap(json)));
    }
  });
}

function replaceGraphQuery(updates) {
  const url = new URL(location.href);
  Object.keys(updates).forEach((key) => {
    const value = updates[key];
    if (value === null || value === undefined || value === "") {
      url.searchParams.delete(key);
    } else {
      url.searchParams.set(key, value);
    }
  });
  history.pushState(null, "", url.pathname + url.search + url.hash);
  loadContextGraph();
}

function openStage(stageId) {
  replaceGraphQuery({ stage: stageId, view: "symbols" });
}

function showReceiverStages() {
  replaceGraphQuery({
    stage: null, suite: null, file: null, symbol: null, symbol_id: null,
    view: "stages",
  });
}

function toggleShowAll() {
  const params = new URLSearchParams(location.search);
  replaceGraphQuery({ view: params.get("view") === "all" ? "symbols" : "all" });
}

function loadContextGraph() {
  const params = new URLSearchParams(location.search);
  if (params.get("receiver") === "standard") {
    params.set("receiver", "ofdm_fec");
    const canonical = "?" + params.toString();
    history.replaceState(null, "", location.pathname + canonical + location.hash);
  }
  let query = location.search || "";
  if (!query) {
    query = "?receiver=lite";
    history.replaceState(null, "", location.pathname + query + location.hash);
  }
  fetch("/api/graph" + query)
    .then((res) => {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then((json) => renderContextGraph(unwrap(json)))
    .catch((err) => setInspectorMessage(
      "Could not load graph context: " + err.message
    ));
}

// ---------- init ----------

function init() {
  injectStyle();
  const search = document.getElementById("symsearch");
  if (search) search.addEventListener("input", () => filterSymbols(search.value));
  window.addEventListener("hashchange", onHashChange);
  if (PAGE_MODE === "graph") {
    const back = document.getElementById("graph-back-stages");
    const showAll = document.getElementById("graph-show-all");
    if (back) back.addEventListener("click", showReceiverStages);
    if (showAll) showAll.addEventListener("click", toggleShowAll);
    window.addEventListener("popstate", loadContextGraph);
    loadContextGraph();
  }
  onHashChange();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
