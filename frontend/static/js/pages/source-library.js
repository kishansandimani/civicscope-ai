import { api } from "../api.js";
import { toast, withBusy } from "../ui.js";
import { el, chip, emptyState, errorState, spinner } from "../render.js";

const $ = (s) => document.querySelector(s);
const list = $("#sl-list"), progress = $("#sl-progress");
let sources = [];
const selected = new Set();
const RULES = { infoconflict: [2, 5], promisetrace: [1, 5], "rulestress-ai": [1, 1], accessshadow: [1, 1] };
const fmtSize = (n) => !n ? "" : n > 1048576 ? (n / 1048576).toFixed(1) + " MB" : Math.max(1, Math.round(n / 1024)) + " KB";

async function load() {
  list.replaceChildren(spinner("Loading sources…"));
  try { ({ items: sources } = await api("/sources")); [...selected].forEach(id => { if (!sources.some(s => s.id === id)) selected.delete(id); }); paint(); }
  catch (e) { list.replaceChildren(errorState(e.message)); }
}

function updateActions() {
  const n = selected.size;
  document.querySelectorAll("[data-use]").forEach(b => { const [lo, hi] = RULES[b.dataset.use]; b.disabled = n < lo || n > hi; b.title = `Needs ${lo === hi ? lo : lo + "–" + hi} selected source(s)`; });
  $("#sl-hint").textContent = n ? `${n} selected.` : "Select sources with the checkboxes, then choose what to do with them.";
}

function paint() {
  const q = $("#sl-q").value.trim().toLowerCase();
  const rows = sources.filter(s => !q || `${s.name} ${s.url || ""}`.toLowerCase().includes(q));
  list.replaceChildren();
  if (!rows.length) { list.appendChild(sources.length ? emptyState("No sources match", "Clear the filter to see all sources.") : emptyState("Your library is empty", "Upload a PDF, TXT or HTML file, or add a public web address above.")); updateActions(); return; }
  const wrap = el("div", "overflow-x-auto"); const t = el("table", "w-full text-sm text-left");
  t.appendChild(el("caption", "sr-only", "Your sources"));
  const hr = el("tr", "text-violet-300/70"); ["Select", "Name", "Type", "Status", "Size / pages", "Added", "Actions"].forEach(h => hr.appendChild(el("th", "p-2 font-semibold", h, { scope: "col" })));
  t.appendChild(el("thead")).appendChild(hr);
  const tb = el("tbody");
  rows.forEach(s => {
    const tr = el("tr", "border-t border-white/10 align-top");
    const cb = el("input", "h-5 w-5 accent-purple-400", null, { type: "checkbox", "aria-label": `Select ${s.name}` }); cb.checked = selected.has(s.id);
    cb.disabled = s.status !== "ready"; cb.addEventListener("change", () => { cb.checked ? selected.add(s.id) : selected.delete(s.id); updateActions(); });
    tr.appendChild(el("td", "p-2")).appendChild(cb);
    const name = el("td", "p-2 text-white break-words max-w-xs"); name.appendChild(el("div", "font-semibold", s.name));
    if (s.url) name.appendChild(el("div", "text-xs text-violet-300/70 break-all", s.url)); if (s.error_message) name.appendChild(el("div", "text-xs text-rose-300", s.error_message)); tr.appendChild(name);
    tr.appendChild(el("td", "p-2 text-violet-100/90", s.kind === "url" ? "Web page" : s.kind === "pdf" ? "PDF" : "Document"));
    tr.appendChild(el("td", "p-2")).appendChild(chip(s.status, s.status === "ready" ? "met" : s.status === "failed" ? "not_met" : "unknown"));
    tr.appendChild(el("td", "p-2 text-violet-100/90", [fmtSize(s.size_bytes), s.page_count ? `${s.page_count} pp` : ""].filter(Boolean).join(" · ") || "—"));
    tr.appendChild(el("td", "p-2 text-violet-100/90", new Date(s.created_at).toLocaleDateString()));
    const del = el("button", "px-3 py-1.5 rounded-lg bg-white/10 hover:bg-rose-500/30 border border-white/15 text-white text-xs", "Delete", { type: "button", "aria-label": `Delete ${s.name}` });
    del.addEventListener("click", async () => { if (!confirm(`Delete “${s.name}” and its extracted text? Reports already made from it are kept.`)) return;
      try { await api(`/sources/${s.id}`, { method: "DELETE" }); selected.delete(s.id); toast("Source deleted.", "success"); load(); } catch (e) { toast(e.message, "error"); } });
    tr.appendChild(el("td", "p-2")).appendChild(del); tb.appendChild(tr);
  });
  t.appendChild(tb); wrap.appendChild(t); list.appendChild(wrap); updateActions();
}

async function uploadFiles(files) {
  for (const f of files) {
    const li = el("li", "text-violet-100/90", `${f.name} — uploading…`); progress.appendChild(li);
    const form = new FormData(); form.append("file", f);
    try { const r = await api("/sources/upload", { method: "POST", form }); li.textContent = `${f.name} — added (${r.chunks} text sections${r.page_count ? ", " + r.page_count + " pages" : ""}).`; li.className = "text-emerald-300"; }
    catch (e) { li.textContent = `${f.name} — not added: ${e.message}`; li.className = "text-rose-300"; }
  }
  await load();
}

const fileInput = $("#sl-file");
fileInput.addEventListener("change", () => { const fs = [...fileInput.files]; fileInput.value = ""; if (fs.length) uploadFiles(fs); });
const drop = $("#sl-drop");
["dragenter", "dragover"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.add("border-purple-400/60"); }));
["dragleave", "drop"].forEach(ev => drop.addEventListener(ev, e => { e.preventDefault(); drop.classList.remove("border-purple-400/60"); }));
drop.addEventListener("drop", e => { const fs = [...(e.dataTransfer?.files || [])]; if (fs.length) uploadFiles(fs); });

$("#sl-url-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const input = $("#sl-url"); const url = input.value.trim();
  if (!url) { toast("Enter a web address first.", "warning"); input.focus(); return; }
  await withBusy(e.submitter, async () => {
    try { const r = await api("/sources/url", { method: "POST", body: { url } }); toast(`Added “${r.name}”.`, "success"); input.value = ""; await load(); }
    catch (err) { toast(err.message, "error"); }
  });
});
$("#sl-q").addEventListener("input", paint);
document.querySelectorAll("[data-use]").forEach(b => b.addEventListener("click", () => {
  const ids = [...selected], tool = b.dataset.use;
  const qs = tool === "infoconflict" || tool === "promisetrace" ? `sources=${ids.join(",")}` : `source=${ids[0]}`;
  location.href = `/${tool}?${qs}`;
}));
load();
