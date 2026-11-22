import { api } from "../api.js";
import { toast } from "../ui.js";
import { $, qparams, run, showResult, recent, sourcePicker } from "../module-common.js";

const form = $("#m-form"), box = $("#m-result"), recentBox = $("#m-recent");
const pre = (qparams().get("sources") || "").split(",").filter(Boolean);
const picker = await sourcePicker($("#m-sources"), { multi: true, max: 5, preselect: pre });
form.addEventListener("submit", async (e) => {
  e.preventDefault();
  const ids = picker.selected();
  if (ids.length < 2 || ids.length > 5) { toast("Choose between 2 and 5 sources to compare.", "warning"); return; }
  const topic = $("#ic-topic").value.trim() || null;
  await run(e.submitter, box, "Comparing sources. This can take a minute…", async () => {
    showResult(box, "infoconflict", await api("/infoconflict/compare", { method: "POST", body: { source_ids: ids, topic } }));
    recent("infoconflict", recentBox, box);
  });
});
recent("infoconflict", recentBox, box);
