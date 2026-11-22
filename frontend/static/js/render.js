// Safe result renderer shared by Reports & Findings and every module page.
// Everything user/website/AI-derived goes through textContent: no innerHTML with data, ever.

export function el(tag, cls = "", text = null, attrs = {}) {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text !== null && text !== undefined) n.textContent = text;
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}
const SEV = {
  critical: "bg-red-600/25 text-red-200 border-red-400/50", high: "bg-rose-500/20 text-rose-200 border-rose-400/40",
  medium: "bg-amber-500/20 text-amber-200 border-amber-400/40", low: "bg-sky-500/20 text-sky-200 border-sky-400/40",
};
const STATUS = {
  on_track: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40", completed: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  delayed: "bg-amber-500/20 text-amber-200 border-amber-400/40", no_update_found: "bg-slate-500/20 text-slate-200 border-slate-400/40",
  unclear: "bg-slate-500/20 text-slate-200 border-slate-400/40", met: "bg-emerald-500/20 text-emerald-200 border-emerald-400/40",
  not_met: "bg-rose-500/20 text-rose-200 border-rose-400/40", unknown: "bg-slate-500/20 text-slate-200 border-slate-400/40",
};
export const pretty = (s) => String(s ?? "").replace(/_/g, " ");
export function chip(text, kind) {
  return el("span", `inline-block text-[11px] uppercase tracking-wide font-bold px-2 py-0.5 rounded-md border ${SEV[kind] || STATUS[kind] || "bg-white/10 text-violet-100 border-white/20"}`, pretty(text));
}
const CARD = "rounded-2xl border border-white/10 bg-white/[0.04] p-4";
const MUTED = "text-sm text-violet-200/70";

function section(title, children = []) {
  const s = el("section", "space-y-3");
  s.appendChild(el("h3", "text-lg font-bold text-white", title));
  children.forEach(c => s.appendChild(c));
  return s;
}
function evidenceLine(label, text) {
  const p = el("p", "text-sm text-violet-100/90 break-words");
  p.appendChild(el("span", "text-violet-300/70", label + " "));
  p.appendChild(el("code", "bg-black/30 rounded px-1.5 py-0.5 text-[13px]", text));
  return p;
}
function link(url) {
  if (!/^https?:\/\//i.test(url)) return el("span", "text-violet-200", url);
  return el("a", "text-cyan-300 underline break-all", url, { href: url, target: "_blank", rel: "noopener noreferrer" });
}
function notices(body) {
  const frag = [];
  const ai = body.ai_status;
  if (ai && ai.ran === false && ai.error) frag.push(el("div", "rounded-xl border border-amber-400/40 bg-amber-500/10 text-amber-100 text-sm p-3", `AI review not performed: ${ai.error}`));
  if (ai && ai.ran && ai.dropped_ungrounded) frag.push(el("div", "text-xs text-violet-300/70", `${ai.dropped_ungrounded} AI statement(s) were discarded because their quoted evidence could not be found in the source.`));
  (ai?.injection_warnings || []).forEach(w => frag.push(el("div", "rounded-xl border border-amber-400/40 bg-amber-500/10 text-amber-100 text-sm p-3", `Source text that looks like instructions to AI was detected and ignored: “${typeof w === "string" ? w : w.snippet}”.`)));
  return frag;
}
function limitations(body) {
  if (!body.limitations?.length) return null;
  const ul = el("ul", "list-disc pl-5 space-y-1 " + MUTED);
  body.limitations.forEach(l => ul.appendChild(el("li", "", l)));
  return section("Limitations", [ul]);
}
function stat(label, value) {
  const d = el("div", CARD + " text-center");
  d.appendChild(el("div", "text-2xl font-extrabold text-white", String(value)));
  d.appendChild(el("div", "text-xs uppercase tracking-wider text-violet-300/70", label));
  return d;
}

function renderProbe(b) {
  const root = el("div", "space-y-6");
  const stats = el("div", "grid grid-cols-2 md:grid-cols-4 gap-3");
  [["Health score", `${b.health_score}/100`], ["Pages scanned", b.pages_scanned], ["Links checked", b.links_checked], ["Broken / unreachable", b.broken_links]].forEach(([l, v]) => stats.appendChild(stat(l, v)));
  root.appendChild(stats);
  root.appendChild(el("p", MUTED, b.score_method));
  notices(b).forEach(n => root.appendChild(n));
  const list = el("div", "space-y-3");
  if (!b.findings.length) list.appendChild(el("p", MUTED, "No issues were detected by the checks that were run."));
  b.findings.forEach(f => {
    const c = el("article", CARD);
    const head = el("div", "flex flex-wrap items-center gap-2 mb-1");
    head.append(chip(f.severity, f.severity), el("span", "font-semibold text-white", pretty(f.type)), el("span", "text-xs text-violet-300/70", `${f.origin === "ai" ? "AI-assisted" : "Automated"} · confidence ${f.confidence}`));
    c.append(head, el("p", "text-sm text-violet-100/90", f.description));
    const u = el("p", "text-sm mt-1"); u.append(el("span", "text-violet-300/70", "URL: "), link(f.url)); c.appendChild(u);
    c.appendChild(evidenceLine("Evidence:", f.evidence));
    if (f.found_on?.length) { const p = el("p", "text-sm mt-1"); p.appendChild(el("span", "text-violet-300/70", "Found on: ")); f.found_on.forEach((x, i) => { if (i) p.append(", "); p.appendChild(link(x)); }); c.appendChild(p); }
    list.appendChild(c);
  });
  root.appendChild(section(`Findings (${b.findings.length})`, [list]));
  const lim = limitations(b); if (lim) root.appendChild(lim);
  return root;
}

function renderConflict(b) {
  const root = el("div", "space-y-6");
  notices(b).forEach(n => root.appendChild(n));
  const names = {}; (b.sources || []).forEach(s => (names[s.id] = s.name));
  const conflicts = el("div", "space-y-4");
  if (!b.conflicts.length) conflicts.appendChild(el("p", MUTED, "No conflicts were found among the information that could be extracted and verified."));
  b.conflicts.forEach(c => {
    const card = el("article", CARD);
    const head = el("div", "flex items-center gap-2 mb-2"); head.append(chip(c.severity, c.severity), el("span", "font-semibold text-white capitalize", pretty(c.field)));
    card.append(head, el("p", "text-sm text-violet-100/90 mb-3", c.explanation));
    const grid = el("div", "grid gap-3 md:grid-cols-" + Math.min(c.claims.length, 3));
    c.claims.forEach(x => {
      const col = el("div", "rounded-xl border border-white/10 bg-black/20 p-3");
      col.appendChild(el("div", "text-xs uppercase tracking-wider text-violet-300/70", x.source + (x.page ? ` · page ${x.page}` : "")));
      col.appendChild(el("div", "text-white font-semibold my-1", x.value));
      col.appendChild(evidenceLine("“", x.evidence + "”"));
      grid.appendChild(col);
    });
    card.append(grid, el("p", "text-xs text-amber-200/90 mt-3", c.resolution));
    conflicts.appendChild(card);
  });
  root.appendChild(section(`Conflicts (${b.conflicts.length})`, [conflicts]));
  if (b.agreements?.length) {
    const ul = el("ul", "space-y-1 text-sm text-violet-100/90");
    b.agreements.forEach(a => ul.appendChild(el("li", "", `${pretty(a.field)}: ${a.value} (${a.sources.map(s => s.source + (s.page ? ` p.${s.page}` : "")).join(", ")})`)));
    root.appendChild(section("Information that matches across sources", [ul]));
  }
  const fields = Object.keys(b.comparison || {});
  if (fields.length) {
    const wrap = el("div", "overflow-x-auto"); const t = el("table", "w-full text-sm text-left");
    const hr = el("tr"); hr.appendChild(el("th", "p-2 text-violet-300/70", "Field")); (b.sources || []).forEach(s => hr.appendChild(el("th", "p-2 text-violet-300/70", s.name)));
    t.appendChild(el("thead", "", null)).appendChild(hr);
    const tb = el("tbody");
    fields.forEach(f => { const r = el("tr", "border-t border-white/10"); r.appendChild(el("td", "p-2 capitalize text-white", pretty(f)));
      (b.sources || []).forEach(s => r.appendChild(el("td", "p-2 text-violet-100/90", (b.comparison[f][s.id] || []).map(x => x.value).join("; ") || "—"))); tb.appendChild(r); });
    t.appendChild(tb); wrap.appendChild(t); root.appendChild(section("Side-by-side comparison", [wrap]));
  }
  const lim = limitations(b); if (lim) root.appendChild(lim);
  return root;
}

function renderAccess(b) {
  const root = el("div", "space-y-6");
  const c = b.counts || {};
  const stats = el("div", "grid grid-cols-2 md:grid-cols-4 gap-3");
  [["High", c.high ?? 0], ["Medium", c.medium ?? 0], ["Low", c.low ?? 0], ["Needs manual test", c.manual_items ?? 0]].forEach(([l, v]) => stats.appendChild(stat(l, v)));
  root.append(stats, el("p", MUTED, b.summary));
  const auto = el("div", "space-y-3");
  [...b.automated_findings, ...(b.language_findings || [])].forEach(f => {
    const card = el("article", CARD); const head = el("div", "flex flex-wrap items-center gap-2 mb-1");
    head.append(chip(f.severity, f.severity), el("span", "font-semibold text-white", pretty(f.rule)), el("span", "text-xs text-violet-300/70", `${f.count > 1 ? `×${f.count} · ` : ""}${f.wcag || ""} · automated`));
    card.append(head, el("p", "text-sm text-violet-100/90", f.description), evidenceLine("Evidence:", f.evidence));
    auto.appendChild(card);
  });
  if (!auto.children.length) auto.appendChild(el("p", MUTED, "The automated checks found no issues. This does not mean the content is fully accessible."));
  root.appendChild(section("Automated findings", [auto]));
  const manual = el("div", "space-y-3");
  b.manual_review_items.forEach(m => { const card = el("article", CARD + " border-dashed"); card.appendChild(el("div", "font-semibold text-white", m.check));
    card.appendChild(el("p", "text-sm text-violet-100/90", `Why a person must check: ${m.why_manual}`)); card.appendChild(el("p", "text-sm text-violet-100/90", `How to test: ${m.how_to_test}`));
    if (m.prompted_by) card.appendChild(el("p", "text-xs text-violet-300/70", `Prompted by: ${m.prompted_by}`)); manual.appendChild(card); });
  root.appendChild(section("Requires manual testing (not automated results)", [manual]));
  const lim = limitations(b); if (lim) root.appendChild(lim);
  return root;
}

function renderRule(b) {
  const root = el("div", "space-y-5");
  notices(b).forEach(n => root.appendChild(n));
  const top = el("div", CARD); const head = el("div", "flex items-center gap-2 mb-2");
  head.append(chip(b.verdict, b.verdict === "applies" ? "met" : b.verdict === "does_not_apply" ? "not_met" : "unknown"), el("span", "text-xs text-violet-300/70", `confidence ${b.confidence}`));
  top.append(head, el("p", "text-white leading-relaxed", b.answer)); root.appendChild(top);
  if (b.conditions?.length) {
    const ul = el("div", "space-y-2");
    b.conditions.forEach(c => { const r = el("div", CARD); const h = el("div", "flex items-center gap-2 mb-1"); h.append(chip(c.status, c.status), el("span", "text-white font-semibold", c.condition));
      r.append(h, evidenceLine(`“ (page ${c.page ?? "n/a"})`, c.evidence + "”")); ul.appendChild(r); });
    root.appendChild(section("Rules checked against the situation", [ul]));
  }
  if (b.ambiguities?.length) { const ul = el("div", "space-y-2"); b.ambiguities.forEach(a => { const r = el("div", CARD); r.append(el("p", "text-white", a.issue), evidenceLine("“", a.evidence + "”")); ul.appendChild(r); }); root.appendChild(section("Unclear or ambiguous wording", [ul])); }
  if (b.missing_information?.length) { const ul = el("ul", "list-disc pl-5 text-sm text-violet-100/90"); b.missing_information.forEach(m => ul.appendChild(el("li", "", m))); root.appendChild(section("Information needed but not provided", [ul])); }
  const lim = limitations(b); if (lim) root.appendChild(lim);
  return root;
}

function renderTrace(b) {
  const root = el("div", "space-y-5");
  notices(b).forEach(n => root.appendChild(n));
  root.appendChild(el("p", MUTED, b.summary));
  if (!b.projects.length) root.appendChild(el("p", MUTED, "No verifiable public commitments were found in the provided sources."));
  b.projects.forEach(p => {
    const card = el("article", CARD); const head = el("div", "flex flex-wrap items-center gap-2 mb-1");
    head.append(chip(p.status, p.status), el("span", "text-lg font-bold text-white", p.title), p.department ? el("span", "text-xs text-violet-300/70", p.department) : "");
    card.appendChild(head);
    card.appendChild(evidenceLine(`Commitment (${p.commitment.source}, page ${p.commitment.page ?? "n/a"}):`, p.commitment.quote));
    if (p.target_date) card.appendChild(el("p", "text-sm text-violet-100/90 mt-1", `Target date: ${p.target_date}`));
    if (p.status_note) card.appendChild(el("p", "text-sm text-amber-200/90 mt-1", p.status_note));
    if (p.timeline?.length) { const ol = el("ol", "mt-3 border-l border-white/15 pl-4 space-y-2");
      p.timeline.forEach(e => { const li = el("li", "text-sm text-violet-100/90"); li.append(el("span", "text-violet-300/70", `${e.date} · ${pretty(e.type)}: `), e.label); ol.appendChild(li); }); card.appendChild(ol); }
    (p.progress_updates || []).forEach(u => card.appendChild(evidenceLine(`Update${u.date ? " " + u.date : ""} (page ${u.page ?? "n/a"}):`, u.evidence)));
    root.appendChild(card);
  });
  const lim = limitations(b); if (lim) root.appendChild(lim);
  return root;
}

export function renderResult(module, body) {
  const f = { civicprobe: renderProbe, infoconflict: renderConflict, accessshadow: renderAccess, rulestress: renderRule, promisetrace: renderTrace }[module];
  return f ? f(body) : el("p", MUTED, "This report type cannot be displayed.");
}
export function emptyState(title, hint) {
  const d = el("div", "rounded-2xl border border-dashed border-white/15 p-8 text-center");
  d.append(el("div", "text-white font-semibold", title), el("p", MUTED + " mt-1", hint)); return d;
}
export function errorState(message) { return el("div", "rounded-xl border border-rose-400/50 bg-rose-500/10 text-rose-100 p-4 text-sm", message); }
export function spinner(label = "Working…") {
  const d = el("div", "flex items-center gap-3 text-violet-200 p-4", null, { role: "status" });
  d.append(el("span", "h-4 w-4 rounded-full border-2 border-violet-300 border-t-transparent animate-spin"), el("span", "", label)); return d;
}
