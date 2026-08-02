// health.js — behavior for the /health page: check status table, run
// triggers, and live output streaming.

const STYLE_ID = "jx-health-style";
const POLL_INTERVAL_MS = 800;

let polling = false;
let logLength = 0;

function injectStyle() {
  if (document.getElementById(STYLE_ID)) return;
  const style = document.createElement("style");
  style.id = STYLE_ID;
  style.textContent = `
    .h-status.ok { color: var(--ok, #2ecc71); font-weight: 600; }
    .h-status.bad { color: var(--bad, #e74c3c); font-weight: 600; }
    .h-status.warn { color: var(--warn, #e6a23c); font-weight: 600; }
    .jx-health-line { margin: 8px 0; font-size: 13px; }
    .jx-health-line.ok { color: var(--ok, #2ecc71); }
    .jx-health-line.bad { color: var(--bad, #e74c3c); }
    .jx-health-line.warn { color: var(--warn, #e6a23c); }
  `;
  document.head.appendChild(style);
}

function unwrap(json) {
  if (json && typeof json === "object" && "data" in json) return json.data;
  return json;
}

function cssEscape(s) {
  if (window.CSS && typeof CSS.escape === "function") return CSS.escape(s);
  return String(s).replace(/[^a-zA-Z0-9_-]/g, "\\$&");
}

// ---------- rendering ----------

function statusInfo(last, stale) {
  if (!last) return { text: "—", cls: "" };
  const status = (last.status || "").toUpperCase();
  if (status === "RUNNING") return { text: "RUNNING", cls: "warn" };
  if (status === "PASS" && stale) return { text: "STALE", cls: "warn" };
  if (status === "PASS") return { text: "PASS", cls: "ok" };
  if (status === "FAIL") return { text: "FAIL", cls: "bad" };
  return { text: status || "—", cls: "" };
}

function formatSeconds(s) {
  if (s === null || s === undefined || isNaN(Number(s))) return "—";
  return Number(s).toFixed(1) + " s";
}

function formatEnded(ended) {
  if (!ended) return "—";
  const d = new Date(ended);
  if (isNaN(d.getTime())) return String(ended);
  return d.toLocaleTimeString([], { hour12: false });
}

function renderRow(check) {
  if (!check || !check.name) return;
  const tr = document.querySelector('tr[data-check="' + cssEscape(check.name) + '"]');
  if (!tr) return;

  const last = check.last || null;
  const info = statusInfo(last, check.stale);

  const statusCell = tr.querySelector(".h-status");
  if (statusCell) {
    statusCell.textContent = info.text;
    statusCell.className = "h-status" + (info.cls ? " " + info.cls : "");
  }

  const commitCell = tr.querySelector(".h-commit");
  if (commitCell) {
    let text = last && last.commit ? last.commit : "—";
    if (last && last.dirty) text += " (dirty)";
    commitCell.textContent = text;
  }

  const secondsCell = tr.querySelector(".h-seconds");
  if (secondsCell) secondsCell.textContent = last ? formatSeconds(last.seconds) : "—";

  const endedCell = tr.querySelector(".h-ended");
  if (endedCell) endedCell.textContent = last ? formatEnded(last.ended) : "—";
}

function renderChecks(checks) {
  (Array.isArray(checks) ? checks : []).forEach(renderRow);
}

function renderParity(parity) {
  if (!parity) return;
  let container = document.getElementById("health-parity");
  if (!container) {
    container = document.createElement("div");
    container.id = "health-parity";
    const log = document.getElementById("health-log");
    if (log && log.parentNode) {
      log.parentNode.insertBefore(container, log);
    } else {
      document.body.appendChild(container);
    }
  }
  container.innerHTML = "";

  let text;
  let cls;
  if (parity.passed === true) {
    text = "PASS";
    cls = "ok";
  } else if (parity.passed === false) {
    text = "FAIL";
    cls = "bad";
  } else {
    text = "UNKNOWN";
    cls = "warn";
  }

  const line = document.createElement("div");
  line.className = "jx-health-line " + cls;
  line.textContent = "Fixed receiver results: " + text;
  line.title = parity.digest ? "digest: " + parity.digest : "not run";
  container.appendChild(line);
}

// ---------- log ----------

function appendLog(text) {
  const pre = document.getElementById("health-log");
  if (!pre || !text) return;
  pre.textContent += text;
  pre.scrollTop = pre.scrollHeight;
}

function noteLog(text) {
  const pre = document.getElementById("health-log");
  if (!pre) return;
  pre.textContent += (pre.textContent ? "\n" : "") + "[" + text + "]\n";
  pre.scrollTop = pre.scrollHeight;
}

function clearLog() {
  logLength = 0;
  const pre = document.getElementById("health-log");
  if (pre) pre.textContent = "";
}

// ---------- health fetch / poll ----------

function refreshHealth() {
  return fetch("/api/health")
    .then((res) => {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then((json) => {
      const data = unwrap(json) || {};
      renderChecks(data.checks);
      renderParity(data.parity);
    })
    .catch((err) => {
      noteLog("Could not load health status: " + err.message);
    });
}

function pollOnce() {
  fetch("/api/health/output?from=" + logLength)
    .then((res) => {
      if (!res.ok) throw new Error("HTTP " + res.status);
      return res.json();
    })
    .then((json) => {
      const data = unwrap(json) || {};
      if (typeof data.text === "string" && data.text.length > 0) {
        appendLog(data.text);
        logLength += data.text.length;
      }
      if (data.status === "running") {
        setTimeout(pollOnce, POLL_INTERVAL_MS);
      } else {
        polling = false;
        refreshHealth();
      }
    })
    .catch((err) => {
      polling = false;
      noteLog("Poll error: " + err.message);
    });
}

function startPolling() {
  if (polling) return;
  polling = true;
  pollOnce();
}

function runCheck(name) {
  const body = name ? JSON.stringify({ check: name }) : "{}";
  fetch("/api/health/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body,
  })
    .then((res) => {
      if (res.status === 409) {
        noteLog("Another check is running");
        startPolling();
        return;
      }
      if (!res.ok) throw new Error("HTTP " + res.status);
      clearLog();
      startPolling();
    })
    .catch((err) => {
      noteLog("Run error: " + err.message);
    });
}

// ---------- init ----------

function onDocumentClick(ev) {
  const target = ev.target;
  if (!target || !target.closest) return;

  if (target.closest("#health-run-all")) {
    ev.preventDefault();
    runCheck(null);
    return;
  }

  const rowBtn = target.closest(".h-run");
  if (rowBtn) {
    ev.preventDefault();
    const name = rowBtn.dataset.check;
    if (name) runCheck(name);
  }
}

function init() {
  injectStyle();
  document.addEventListener("click", onDocumentClick);
  refreshHealth();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
