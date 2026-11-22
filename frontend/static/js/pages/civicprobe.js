import { api } from "../api.js";
import { toast } from "../ui.js";
import { $, qparams, run, showResult, recent } from "../module-common.js";

const form = $("#m-form"), box = $("#m-result"), recentBox = $("#m-recent");
const q = qparams();
if (q.get("url")) $("#cp-url").value = q.get("url");

async function start(btn) {
  const url = $("#cp-url").value.trim();
  if (!url) { toast("Enter the website address to audit.", "warning"); $("#cp-url").focus(); return; }
  await run(btn, box, "Auditing the website. This can take up to two minutes…", async () => {
    const resp = await api("/civicprobe/analyze", { method: "POST", body: { url, max_pages: parseInt($("#cp-pages").value, 10) } });
    showResult(box, "civicprobe", resp); recent("civicprobe", recentBox, box);
  });
}
form.addEventListener("submit", e => { e.preventDefault(); start(e.submitter || form.querySelector("button[type=submit]")); });
document.addEventListener("civic:voice-confirm", () => start(form.querySelector("button[type=submit]")));
if (q.get("voice") === "1" && q.get("url")) {
  const arm = () => window.civicVoice?.say(`Ready to audit ${q.get("url")}. Say confirm or press Start audit.`);
  window.civicVoice ? arm() : document.addEventListener("civic:voice-ready", arm, { once: true });
}
recent("civicprobe", recentBox, box);
