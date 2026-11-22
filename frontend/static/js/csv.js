// Pure CSV export of module results. Cells that start with = + - @ (or tab/CR) are prefixed with ' so spreadsheet
// apps never execute text that came from scraped websites or documents (CSV/formula injection).
export function cell(v) {
  let s = v === null || v === undefined ? "" : Array.isArray(v) ? v.join("; ") : String(v);
  if (/^[=+\-@\t\r]/.test(s)) s = "'" + s;
  return /[",\n\r]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}
const toCsv = (header, rows) => [header, ...rows].map(r => r.map(cell).join(",")).join("\r\n") + "\r\n";

export function resultToCsv(module, b) {
  switch (module) {
    case "civicprobe":
      return toCsv(["severity", "type", "origin", "confidence", "url", "description", "evidence", "found_on"],
        b.findings.map(f => [f.severity, f.type, f.origin, f.confidence, f.url, f.description, f.evidence, f.found_on]));
    case "accessshadow":
      return toCsv(["kind", "severity", "rule", "occurrences", "wcag", "description", "evidence"],
        [...b.automated_findings.map(f => ["automated", f.severity, f.rule, f.count, f.wcag, f.description, f.evidence]),
         ...(b.language_findings || []).map(f => ["language", f.severity, f.rule, 1, f.wcag, f.description, f.evidence]),
         ...b.manual_review_items.map(m => ["manual", "", m.check, "", "", m.why_manual + " | " + m.how_to_test, m.prompted_by || ""])]);
    case "infoconflict":
      return toCsv(["field", "severity", "source", "page", "value", "evidence", "explanation"],
        b.conflicts.flatMap(c => c.claims.map(x => [c.field, c.severity, x.source, x.page, x.value, x.evidence, c.explanation])));
    case "rulestress":
      return toCsv(["verdict", "condition", "status", "page", "evidence"],
        (b.conditions.length ? b.conditions : [{}]).map(c => [b.verdict, c.condition, c.status, c.page, c.evidence]));
    case "promisetrace":
      return toCsv(["commitment", "department", "status", "target_date", "commitment_quote", "source", "page", "note"],
        b.projects.map(p => [p.title, p.department, p.status, p.target_date, p.commitment.quote, p.commitment.source, p.commitment.page, p.status_note]));
    default: return toCsv(["error"], [["unsupported module"]]);
  }
}
