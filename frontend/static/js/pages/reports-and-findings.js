import { api, apiDownload } from "../api.js";
import { toast } from "../ui.js";
import { el, chip, renderResult, emptyState, errorState, spinner, pretty } from "../render.js";

const MODS = { civicprobe: "CivicProbe", infoconflict: "InfoConflict", accessshadow: "AccessShadow", rulestress: "RuleStress AI", promisetrace: "PromiseTrace" };
const $ = (s) => document.querySelector(s);
const list = $("#rf-list"), detail = $("#rf-detail"), moduleSel = $("#rf-module"), qInput = $("#rf-q");
let items = [];

const params = new URLSearchParams(location.search);
if (params.get("q")) qInput.value = params.get("q");
if (MODS[params.get("module")]) moduleSel.value = params.get("module");

async function load() {
  list.replaceChildren(spinner("Loading reports…"));
  try {
    const m = moduleSel.value;
    ({ items } = await api("/reports" + (m ? `?module=${m}` : "")));
    paint();
    if (params.get("id")) { const id = params.get("id"); params.delete("id"); view(id); }
  } catch (e) { list.replaceChildren(errorState(e.message)); }
}

function paint() {
  const q = qInput.value.trim().toLowerCase();
  const shown = items.filter(r => !q || `${r.title} ${r.summary || ""}`.toLowerCase().includes(q));
  list.replaceChildren();
  if (!shown.length) {
    list.appendChild(items.length ? emptyState("No reports match your search", "Try different words or clear the filter.")
      : emptyState("No reports yet", "Run CivicProbe, InfoConflict, AccessShadow, RuleStress or PromiseTrace and the saved report will appear here."));
    return;
  }
  shown.forEach(r => {
    const card = el("article", "rounded-2xl frosted-glass border border-white/10 p-space-md");
    const top = el("div", "flex flex-wrap items-center gap-2 mb-1");
    top.append(chip(MODS[r.module] || r.module, "info"), el("span", "text-xs text-violet-300/70", new Date(r.created_at).toLocaleString()));
    const counts = el("div", "flex flex-wrap gap-1 my-2");
    Object.entries(r.severity_counts || {}).filter(([, n]) => n > 0).forEach(([k, n]) => counts.appendChild(chip(`${n} ${pretty(k)}`, k)));
    const actions = el("div", "flex flex-wrap gap-2 mt-3");
    const btn = (label, fn) => { const b = el("button", "px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 border border-white/15 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-300/60", label, { type: "button" }); b.addEventListener("click", () => fn(b)); actions.appendChild(b); };
    btn("View report", () => view(r.id));
    btn("Read aloud", async () => { try { const { text } = await api(`/reports/${r.id}/speakable`); window.civicVoice ? window.civicVoice.speak(text) : toast("Voice is still loading, try again in a moment.", "warning"); } catch (e) { toast(e.message, "error"); } });
    btn("Download (.md)", async () => { try { await apiDownload(`/reports/${r.id}/markdown`, "report.md"); } catch (e) { toast(e.message, "error"); } });
    btn("Delete", async () => { if (!confirm(`Delete “${r.title}”? This cannot be undone.`)) return; try { await api(`/reports/${r.id}`, { method: "DELETE" }); toast("Report deleted.", "success"); if (detail.dataset.id === r.id) detail.classList.add("hidden"); load(); } catch (e) { toast(e.message, "error"); } });
    card.append(top, el("h2", "text-lg font-bold text-white", r.title), el("p", "text-sm text-violet-100/80", r.summary || ""), counts, actions);
    list.appendChild(card);
  });
}

async function view(id) {
  detail.classList.remove("hidden"); detail.dataset.id = id; detail.replaceChildren(spinner("Opening report…"));
  detail.scrollIntoView({ behavior: "smooth", block: "start" });
  try {
    const r = await api(`/reports/${id}`);
    const head = el("div", "flex flex-wrap items-center justify-between gap-2 mb-4");
    head.appendChild(el("h2", "text-2xl font-extrabold text-white", r.title));
    const close = el("button", "px-4 py-2 rounded-xl bg-white/10 border border-white/15 text-white text-sm", "Close", { type: "button" });
    close.addEventListener("click", () => detail.classList.add("hidden")); head.appendChild(close);
    detail.replaceChildren(head, renderResult(r.module, r.body)); detail.focus();
    if (window.civicVoice?.state.blind) { const { text } = await api(`/reports/${id}/speakable`); window.civicVoice.speak(text); }
  } catch (e) { detail.replaceChildren(errorState(e.message)); }
}

moduleSel.addEventListener("change", load);
qInput.addEventListener("input", paint);
$("#rf-refresh").addEventListener("click", load);
$("#rf-filters").addEventListener("submit", e => e.preventDefault());
load();
