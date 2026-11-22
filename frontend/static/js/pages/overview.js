import { api } from "../api.js";
import { toast } from "../ui.js";
import { el, chip, emptyState, errorState, spinner, pretty } from "../render.js";

const $ = (s) => document.querySelector(s);
const MODULES = [
  ["civicprobe", "CivicProbe", "travel_explore", "Government website auditor", "Crawls a site and checks links, stale dates and missing information, with evidence."],
  ["infoconflict", "InfoConflict", "rule", "Conflict detector", "Compares notices and documents and shows where they disagree, side by side."],
  ["accessshadow", "AccessShadow", "accessibility_new", "Accessibility analyzer", "Checks pages and PDFs for accessibility problems and lists what needs manual testing."],
  ["rulestress-ai", "RuleStress AI", "troubleshoot", "Policy scenario tester", "Tests a citizen's situation against a policy document, with quoted evidence."],
  ["promisetrace", "PromiseTrace", "verified", "Commitment tracker", "Extracts public commitments, deadlines and progress updates from your sources."],
];
const KEY = { "rulestress-ai": "rulestress" };

function statCard(label, value, hint) {
  const c = el("div", "rounded-2xl frosted-glass border border-white/10 p-space-md");
  c.append(el("div", "text-xs uppercase tracking-wider text-violet-300/70", label), el("div", "text-4xl font-extrabold text-white my-1", String(value)), el("div", "text-sm text-violet-200/70", hint));
  return c;
}

async function loadStats() {
  const stats = $("#ov-stats"), mods = $("#ov-modules"), recent = $("#ov-recent");
  stats.replaceChildren(spinner("Loading your activity…"));
  let d;
  try { d = await api("/dashboard/stats"); } catch (e) { stats.replaceChildren(errorState(e.message)); recent.replaceChildren(); return; }
  stats.replaceChildren(
    statCard("Analyses run", d.totals.analyses, "across all five modules"),
    statCard("Sources in library", d.totals.sources, "documents and web pages"),
    statCard("Reports saved", d.totals.reports, "ready to open or read aloud"),
    statCard("Most used module", (() => { const top = Object.entries(d.by_module).sort((a, b) => b[1] - a[1])[0]; return top && top[1] ? top[0] : "—"; })(), "based on your analyses"));
  mods.replaceChildren();
  MODULES.forEach(([path, name, icon, sub, desc]) => {
    const n = d.by_module[KEY[path] || path] || 0;
    const a = el("a", "block rounded-2xl frosted-glass border border-white/10 p-space-md hover:border-purple-400/50 focus:outline-none focus:ring-2 focus:ring-purple-300/60", null, { href: "/" + path });
    const top = el("div", "flex items-center gap-2 mb-1"); top.append(el("span", "material-symbols-outlined text-violet-300", icon, { "aria-hidden": "true" }), el("span", "text-lg font-bold text-white", name));
    a.append(top, el("div", "text-sm text-violet-200/80", sub), el("p", "text-sm text-violet-100/80 mt-2", desc), el("p", "text-xs text-violet-300/70 mt-3", n ? `${n} analysis run${n === 1 ? "" : "s"}` : "Not used yet"));
    mods.appendChild(a);
  });
  recent.replaceChildren();
  if (d.is_empty) { recent.appendChild(emptyState("Nothing here yet", "Run your first analysis above. Your results, sources and reports will show up on this page.")); return; }
  const ul = el("ul", "space-y-2");
  d.recent.forEach(r => {
    const li = el("li", "flex flex-wrap items-center gap-2 rounded-xl border border-white/10 bg-white/[0.04] p-3");
    li.append(chip(pretty(r.module), "info"), el("span", "text-white font-semibold flex-1 min-w-[160px] break-words", r.title), chip(r.status, r.status === "completed" ? "met" : r.status === "failed" ? "not_met" : "unknown"), el("span", "text-xs text-violet-300/70", new Date(r.created_at).toLocaleString()));
    ul.appendChild(li);
  });
  recent.appendChild(ul);
}

const form = $("#ov-form");
function syncMode() { const m = form.querySelector("input[name=ov-mode]:checked").value; $("#ov-url-wrap").classList.toggle("hidden", !(m === "civicprobe" || m === "accessshadow")); }
form.querySelectorAll("input[name=ov-mode]").forEach(r => r.addEventListener("change", syncMode)); syncMode();
form.addEventListener("submit", (e) => {
  e.preventDefault();
  const m = form.querySelector("input[name=ov-mode]:checked").value;
  if (m === "civicprobe" || m === "accessshadow") {
    const url = $("#ov-url").value.trim();
    if (!url) { toast("Enter a website address first.", "warning"); $("#ov-url").focus(); return; }
    location.href = `/${m}?url=${encodeURIComponent(url)}`;
  } else location.href = "/" + m;
});

$("#ov-voice").addEventListener("submit", (e) => { e.preventDefault(); const i = $("#ov-voice-in"); const v = i.value.trim(); i.value = ""; if (v) window.civicVoice ? window.civicVoice.handleTranscript(v) : toast("Voice is still loading, try again in a moment.", "warning"); });
$("#ov-mic").addEventListener("click", () => window.civicVoice?.toggleListening());
loadStats();
