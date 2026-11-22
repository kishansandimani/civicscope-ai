import { api } from "../api.js";
import { toast } from "../ui.js";
import { $, qparams, run, showResult, recent, sourcePicker } from "../module-common.js";

const form = $("#m-form"), box = $("#m-result"), recentBox = $("#m-recent");
const pre = qparams().get("source");
if (qparams().get("url")) $("#as-url").value = qparams().get("url");
const picker = await sourcePicker($("#m-sources"), { multi: false, preselect: pre ? [pre] : [] });
const modes = form.querySelectorAll("input[name=as-mode]");
function syncMode() {
  const mode = form.querySelector("input[name=as-mode]:checked").value;
  $("#as-url-wrap").classList.toggle("hidden", mode !== "url"); $("#as-src-wrap").classList.toggle("hidden", mode !== "source");
}
modes.forEach(m => m.addEventListener("change", syncMode));
if (pre) form.querySelector("input[value=source]").checked = true;
syncMode();
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const mode = form.querySelector("input[name=as-mode]:checked").value; let body;
  if (mode === "url") { const url = $("#as-url").value.trim(); if (!url) { toast("Enter a web address.", "warning"); $("#as-url").focus(); return; } body = { url }; }
  else { const [id] = picker.selected(); if (!id) { toast("Choose a source from your library.", "warning"); return; } body = { source_id: id }; }
  await run(e.submitter, box, "Checking accessibility…", async () => {
    showResult(box, "accessshadow", await api("/accessshadow/analyze", { method: "POST", body })); recent("accessshadow", recentBox, box);
  });
});
recent("accessshadow", recentBox, box);
