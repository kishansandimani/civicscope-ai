// Shared behaviour for CivicProbe / InfoConflict / AccessShadow / RuleStress / PromiseTrace pages.
import { api, apiDownload } from "./api.js";
import { toast } from "./ui.js";
import { el, renderResult, emptyState, errorState, spinner } from "./render.js";
import { resultToCsv } from "./csv.js";

export const $ = (s, root = document) => root.querySelector(s);
const BTN2 = "px-4 py-2 rounded-xl bg-white/10 hover:bg-white/20 border border-white/15 text-white text-sm focus:outline-none focus:ring-2 focus:ring-purple-300/60 disabled:opacity-40";

(function injectPrintCss() {
  if (document.getElementById("civic-print-css")) return;
  const s = document.createElement("style"); s.id = "civic-print-css";
  s.textContent = `@media print { aside, header, #civic-dock, #m-form, #m-recent, #m-toolbar, nav { display: none !important; }
    body, main { background: #fff !important; color: #000 !important; } main * { color: #000 !important; background: transparent !important; border-color: #999 !important; } main { padding: 0 !important; margin: 0 !important; } }`;
  document.head.appendChild(s);
})();

export function qparams() { return new URLSearchParams(location.search); }

// ---------------------------------------------------------------- source picker
export async function sourcePicker(container, { multi = true, max = 5, preselect = [] } = {}) {
  container.replaceChildren(spinner("Loading your sources…"));
  let items;
  try { ({ items } = await api("/sources")); } catch (e) { container.replaceChildren(errorState(e.message)); return { selected: () => [] }; }
  items = items.filter(s => s.status === "ready");
  container.replaceChildren();
  if (!items.length) {
    const d = emptyState("No sources yet", "Add documents or web pages in the Source Library first.");
    d.appendChild(el("a", "inline-block mt-3 px-4 py-2 rounded-xl bg-white/10 border border-white/15 text-white text-sm", "Open Source Library", { href: "/source-library" }));
    container.appendChild(d); return { selected: () => [] };
  }
  const group = el("div", "grid gap-2 sm:grid-cols-2", null, { role: multi ? "group" : "radiogroup" });
  const name = "src-" + Math.random().toString(36).slice(2);
  items.forEach(s => {
    const lab = el("label", "flex items-start gap-3 rounded-xl border border-white/10 bg-white/[0.04] p-3 cursor-pointer hover:border-purple-400/50");
    const inp = el("input", "mt-1 h-5 w-5 accent-purple-400", null, { type: multi ? "checkbox" : "radio", name, value: s.id });
    inp.checked = preselect.includes(s.id);
    const t = el("span", "min-w-0"); t.append(el("span", "block text-white font-semibold break-words", s.name),
      el("span", "block text-xs text-violet-300/70", [s.kind === "url" ? "Web page" : s.kind === "pdf" ? "PDF" : "Document", s.page_count ? s.page_count + " pages" : ""].filter(Boolean).join(" · ")));
    lab.append(inp, t); group.appendChild(lab);
  });
  container.appendChild(group);
  if (multi) container.appendChild(el("p", "text-xs text-violet-300/70 mt-2", `Choose up to ${max}.`));
  return { selected: () => [...container.querySelectorAll("input:checked")].map(i => i.value) };
}

// ---------------------------------------------------------------- results
export function showResult(box, module, resp) {
  const { result, report_id } = resp;
  box.replaceChildren();
  const bar = el("div", "flex flex-wrap gap-2 mb-4", null, { id: "m-toolbar", role: "toolbar", "aria-label": "Report actions" });
  const add = (label, fn) => { const b = el("button", BTN2, label, { type: "button" }); b.addEventListener("click", () => fn(b)); bar.appendChild(b); };
  const stamp = new Date().toISOString().slice(0, 10);
  const save = (name, text, type) => { const url = URL.createObjectURL(new Blob([text], { type })); const a = Object.assign(document.createElement("a"), { href: url, download: name }); document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url); };
  add("Read aloud", async () => { try { const { text } = await api(`/reports/${report_id}/speakable`); window.civicVoice ? window.civicVoice.speak(text) : toast("Voice is still loading.", "warning"); } catch (e) { toast(e.message, "error"); } });
  add("Download Markdown", async () => { try { await apiDownload(`/reports/${report_id}/markdown`, "report.md"); } catch (e) { toast(e.message, "error"); } });
  add("Download JSON", () => save(`${module}-${stamp}.json`, JSON.stringify(result, null, 2), "application/json"));
  add("Download CSV", () => save(`${module}-${stamp}.csv`, resultToCsv(module, result), "text/csv;charset=utf-8"));
  add("Print / Save as PDF", () => window.print());
  box.append(bar, renderResult(module, result));
  box.tabIndex = -1; box.scrollIntoView({ behavior: "smooth", block: "start" }); box.focus({ preventScroll: true });
  const v = window.civicVoice;
  if (v?.state.blind) { api(`/reports/${report_id}/speakable`).then(r => v.speak(r.text)).catch(() => {}); } else if (v) v.say?.("Analysis complete. Results are shown below.");
}

// ---------------------------------------------------------------- run an analysis with status + errors
export async function run(btn, box, label, fn) {
  if (btn.disabled) return;
  btn.disabled = true; btn.setAttribute("aria-busy", "true");
  box.replaceChildren(spinner(label));
  try { return await fn(); }
  catch (e) { box.replaceChildren(errorState(e.message)); toast(e.message, "error"); window.civicVoice?.say?.(e.message); }
  finally { btn.disabled = false; btn.removeAttribute("aria-busy"); }
}

// ---------------------------------------------------------------- recent reports for a module
export async function recent(module, container, box) {
  container.replaceChildren();
  container.appendChild(el("h2", "font-headline-sm text-headline-sm text-white font-bold mb-3", "Recent reports"));
  try {
    const { items } = await api(`/reports?module=${module}`);
    if (!items.length) { container.appendChild(el("p", "text-sm text-violet-300/70", "Nothing here yet. Your finished analyses will be listed so you can reopen them.")); return; }
    const ul = el("ul", "space-y-2");
    items.slice(0, 8).forEach(r => {
      const li = el("li", "flex flex-wrap items-center justify-between gap-2 rounded-xl border border-white/10 bg-white/[0.04] p-3");
      const t = el("div", "min-w-0"); t.append(el("div", "text-white font-semibold break-words", r.title), el("div", "text-xs text-violet-300/70", new Date(r.created_at).toLocaleString()));
      const open = el("button", BTN2, "Open", { type: "button", "aria-label": `Open ${r.title}` });
      open.addEventListener("click", async () => { try { const full = await api(`/reports/${r.id}`); showResult(box, module, { result: full.body, report_id: full.id }); } catch (e) { toast(e.message, "error"); } });
      li.append(t, open); ul.appendChild(li);
    });
    container.appendChild(ul);
  } catch (e) { container.appendChild(errorState(e.message)); }
}
