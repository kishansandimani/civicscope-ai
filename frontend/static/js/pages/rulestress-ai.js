import { api } from "../api.js";
import { toast } from "../ui.js";
import { $, qparams, run, showResult, recent, sourcePicker } from "../module-common.js";

const form = $("#m-form"), box = $("#m-result"), recentBox = $("#m-recent"), ta = $("#rs-scenario"), count = $("#rs-count");
const pre = qparams().get("source");
const picker = await sourcePicker($("#m-sources"), { multi: false, preselect: pre ? [pre] : [] });
ta.addEventListener("input", () => { count.textContent = `${ta.value.length} / 1500`; });
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const [source_id] = picker.selected(); const scenario = ta.value.trim();
  if (!source_id) { toast("Choose the policy document to test against.", "warning"); return; }
  if (scenario.length < 10) { toast("Describe the citizen's situation in a sentence or two.", "warning"); ta.focus(); return; }
  await run(e.submitter, box, "Testing the scenario against the policy…", async () => {
    showResult(box, "rulestress", await api("/rulestress/test", { method: "POST", body: { source_id, scenario } })); recent("rulestress", recentBox, box);
  });
});
recent("rulestress", recentBox, box);
