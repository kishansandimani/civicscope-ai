import { api } from "../api.js";
import { toast } from "../ui.js";
import { $, qparams, run, showResult, recent, sourcePicker } from "../module-common.js";
import { el, chip, emptyState, errorState, pretty } from "../render.js";

const form = $("#m-form"), box = $("#m-result"), recentBox = $("#m-recent"), projBox = $("#pt-projects");
const pre = (qparams().get("sources") || "").split(",").filter(Boolean);
const picker = await sourcePicker($("#m-sources"), { multi: true, max: 5, preselect: pre });

async function loadProjects() {
  projBox.replaceChildren(el("h2", "font-headline-sm text-headline-sm text-white font-bold mb-3", "Tracked commitments"));
  try {
    const { items } = await api("/promisetrace/projects");
    if (!items.length) { projBox.appendChild(emptyState("No commitments tracked yet", "Run an analysis on announcements or progress reports and verified commitments will be saved here.")); return; }
    items.forEach(p => {
      const c = el("article", "rounded-2xl frosted-glass border border-white/10 p-space-md mb-3");
      const h = el("div", "flex flex-wrap items-center gap-2 mb-1"); h.append(chip(p.status, p.status), el("span", "text-lg font-bold text-white", p.title), p.department ? el("span", "text-xs text-violet-300/70", p.department) : "");
      c.appendChild(h);
      if (p.commitment_text) c.appendChild(el("p", "text-sm text-violet-100/90", `“${p.commitment_text}”`));
      if (p.target_date) c.appendChild(el("p", "text-sm text-violet-100/90 mt-1", `Target date: ${p.target_date}`));
      if (p.evidence_summary) c.appendChild(el("p", "text-sm text-amber-200/90 mt-1", p.evidence_summary));
      if (p.milestones?.length) { const ol = el("ul", "mt-2 border-l border-white/15 pl-4 space-y-1"); p.milestones.forEach(m => ol.appendChild(el("li", "text-sm text-violet-100/90", `${m.due_date || "undated"} · ${pretty(m.status)} · ${m.title}`))); c.appendChild(ol); }
      projBox.appendChild(c);
    });
  } catch (e) { projBox.appendChild(errorState(e.message)); }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const ids = picker.selected();
  if (!ids.length || ids.length > 5) { toast("Choose between 1 and 5 sources.", "warning"); return; }
  await run(e.submitter, box, "Extracting commitments and progress evidence…", async () => {
    showResult(box, "promisetrace", await api("/promisetrace/analyze", { method: "POST", body: { source_ids: ids } }));
    recent("promisetrace", recentBox, box); loadProjects();
  });
});
recent("promisetrace", recentBox, box); loadProjects();
