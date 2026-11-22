// Frontend tests: voice-command parser (EN/HI/KN), result renderer, CSV exporter. Run: npm test (Node 18+)
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
const here = path.dirname(fileURLToPath(import.meta.url));
let failures = 0, total = 0;
const check = (ok, msg) => { total++; if (!ok) { failures++; console.log("FAIL", msg); } };

// ---------- tiny DOM stand-in so render.js can build trees without a browser
class N { constructor(t) { this.tag = t; this.children = []; this.attrs = {}; this.className = ""; this._t = ""; }
  appendChild(c) { if (typeof c === "string") c = Object.assign(new N("#text"), { _t: c }); this.children.push(c); return c; }
  append(...cs) { cs.forEach(c => { if (c !== "" && c != null) this.appendChild(c); }); }
  setAttribute(k, v) { this.attrs[k] = v; } set textContent(v) { this._t = String(v); }
  get textContent() { return this._t + this.children.map(c => c.textContent).join(""); } }
globalThis.document = { createElement: t => new N(t) };

const { parseCommand, extractDomain } = await import("../static/js/voice-commands.js");
const { renderResult } = await import("../static/js/render.js");
const { cell, resultToCsv } = await import("../static/js/csv.js");

// ---------- voice commands
const cases = [
  ["pause", { type: "control", action: "pause" }], ["Stop.", { type: "control", action: "stop" }],
  ["say that again", { type: "control", action: "repeat" }], ["faster", { type: "control", action: "faster" }],
  ["go to reports", { type: "nav", path: "reports-and-findings" }], ["open accessibility settings", { type: "nav", path: "accessibility-settings" }],
  ["open civic probe", { type: "nav", path: "civicprobe" }], ["take me to the dashboard", { type: "nav", path: "overview" }],
  ["open CivicProbe and audit transport dot gov dot in", { type: "probe", url: "transport.gov.in" }],
  ["compare circular 104 with circular 108", { type: "compare", a: "circular 104", b: "circular 108" }],
  ["read aloud the latest discrepancy report", { type: "read", target: "report", module: "infoconflict" }],
  ["read this page", { type: "read", target: "page" }],
  ["enable blind friendly high contrast mode", { type: "mode", blind: true, contrast: true }],
  ["switch to kannada", { type: "lang", code: "kn" }], ["हिंदी", { type: "lang", code: "hi" }],
  ["रिपोर्ट खोलो", { type: "nav", path: "reports-and-findings" }], ["ವರದಿ ತೆರೆಯಿರಿ", { type: "nav", path: "reports-and-findings" }],
  ["ರಿಪೋರ್ಟ್ ತೆರೆಯಿರಿ", { type: "nav", path: "reports-and-findings" }], ["रुको", { type: "control", action: "pause" }],
  ["ನಿಲ್ಲಿಸಿ", { type: "control", action: "stop" }],
  ["Explain the pension eligibility rule in plain Kannada", { type: "ask", language: "kn" }],
  ["what is the deadline for the scholarship", { type: "ask", language: null }], ["", { type: "empty" }],
];
for (const [input, want] of cases) { const got = parseCommand(input); check(Object.entries(want).every(([k, v]) => got[k] === v), `parse ${JSON.stringify(input)} -> ${JSON.stringify(got)}`); }
check(extractDomain("audit www.transport.gov.in/page now") === "www.transport.gov.in/page", "extractDomain");

// ---------- CSV safety
check(cell('=HYPERLINK("http://evil")') === `"'=HYPERLINK(""http://evil"")"`, "csv formula escaped");
check(cell("+1") === "'+1" && cell("@SUM(A1)") === "'@SUM(A1)" && cell("-5") === "'-5", "csv + @ - escaped");
check(cell('say "hi", ok') === '"say ""hi"", ok"' && cell(null) === "" && cell(["a", "b"]) === "a; b", "csv quoting");

// ---------- renderer + CSV on real backend outputs
const samplesPath = path.join(here, "samples.json");
if (!fs.existsSync(samplesPath)) { console.log("NOTE: samples.json missing. Run `python tests/make_samples.py` in backend/ first."); }
else {
  const samples = JSON.parse(fs.readFileSync(samplesPath, "utf8"));
  for (const [mod, body] of Object.entries(samples)) {
    let text = "", csv = "";
    try { text = renderResult(mod, body).textContent; csv = resultToCsv(mod, body); } catch (e) { check(false, `${mod} threw ${e.message}`); continue; }
    check(text.length > 200 && !/undefined|\[object|NaN/.test(text), `${mod} render has no undefined/NaN`);
    check(csv.split("\r\n").length >= 2 && !/undefined|NaN/.test(csv), `${mod} csv ok`);
  }
}
console.log(failures ? `${failures} of ${total} checks FAILED` : `all ${total} frontend checks passed`);
process.exit(failures ? 1 : 0);
