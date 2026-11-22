// Makes the shared Stitch header/sidebar real: search, language, contrast, blind mode, alerts, profile menu, help links.
import { api } from "./api.js";
import { toast } from "./ui.js";
import { cell } from "./csv.js";

const $ = (s, r = document) => r.querySelector(s);
const NAMES = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ", ta: "தமிழ்", te: "తెలుగు", bn: "বাংলা" };
const DOMAIN = /^(https?:\/\/)?([a-z0-9-]+\.)+[a-z]{2,}(\/\S*)?$/i;

function setSwitch(btn, on) {              // same visual states the Stitch markup uses
  const circle = btn.querySelector(".toggle-circle");
  btn.setAttribute("aria-checked", String(on));
  btn.classList.toggle("bg-purple-600", on); btn.classList.toggle("bg-violet-950/80", !on);
  circle?.classList.toggle("translate-x-4", on); circle?.classList.toggle("bg-white", on); circle?.classList.toggle("bg-violet-300", !on);
}

function removeFakeBadges() {
  document.querySelectorAll('aside a[data-path="civicprobe"] span, aside a[data-path="infoconflict"] span').forEach(sp => {
    if (/^(live|alert)$/i.test(sp.textContent.trim())) sp.remove();
  });
}

async function exportActivityCsv() {
  const { items } = await api("/reports");
  const rows = [["created_at", "module", "title", "summary"], ...items.map(r => [r.created_at, r.module, r.title, r.summary])];
  const csv = rows.map(r => r.map(cell).join(",")).join("\r\n") + "\r\n";
  const url = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
  const a = Object.assign(document.createElement("a"), { href: url, download: "civicscope-activity-log.csv" });
  document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
}

export function wireHeader() {
  removeFakeBadges();

  const search = $('header input[placeholder^="Search policies"]');
  search?.setAttribute("aria-label", "Search reports, or enter a website address to audit");
  search?.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const v = search.value.trim(); if (!v) return;
    location.href = DOMAIN.test(v) ? `/civicprobe?url=${encodeURIComponent(v)}` : `/reports-and-findings?q=${encodeURIComponent(v)}`;
  });

  document.querySelectorAll("header button").forEach(b => {
    const t = b.textContent;
    if (/Ask CivicVoice/.test(t)) b.addEventListener("click", () => window.civicVoice?.toggleListening());
    if (/Sign Out/i.test(t)) return;
  });

  document.querySelectorAll(".lang-option").forEach(opt => opt.addEventListener("click", () => {
    const code = opt.getAttribute("data-lang-code"); const v = window.civicVoice;
    if (["en", "hi", "kn"].includes(code)) v?.setLang(code);
    api("/me", { method: "PATCH", body: { preferred_language: code } }).catch(() => {});
    toast(["en", "hi", "kn"].includes(code) ? `Voice and spoken answers will now use ${NAMES[code]}. Page text stays in English.`
      : `${NAMES[code]} saved as your preferred language. Voice currently supports English, Hindi and Kannada; page text stays in English.`, "info");
  }));

  const blind = $('header button[title^="Blind-Friendly"]');
  blind?.setAttribute("aria-pressed", "false");
  blind?.addEventListener("click", () => {
    const v = window.civicVoice; if (!v) return;
    const on = !v.state.blind, patch = { voice_enabled: on };
    v.applySettings(patch); v.saveSettings(patch); v.say(on ? "Blind-friendly mode on. Results will be read aloud." : "Blind-friendly mode off.");
  });

  $('header button[title="Governance Alerts"]')?.addEventListener("click", () => (location.href = "/platform-settings"));

  document.querySelectorAll("#profile-dropdown a").forEach(a => {
    const t = a.textContent;
    if (/User Profile/i.test(t)) a.href = "/platform-settings";
    else if (/Audit Docket/i.test(t)) a.href = "/reports-and-findings";
    else if (/Audio Sensitiv/i.test(t)) a.href = "/accessibility-settings";
    else if (/Export Activity Log/i.test(t)) { a.href = "#"; a.addEventListener("click", async (e) => { e.preventDefault(); try { await exportActivityCsv(); } catch (err) { toast(err.message, "error"); } }); }
  });

  const contrast = $("#contrast-toggle");     // the page's inline script flips the look first; then we apply the real setting
  contrast?.addEventListener("click", () => {
    const on = contrast.getAttribute("aria-checked") === "true", v = window.civicVoice;
    v?.applySettings({ high_contrast: on }); v?.saveSettings({ high_contrast: on });
  });

  const help = [...document.querySelectorAll("aside a")].find(a => /Help & Support/i.test(a.textContent));
  help?.addEventListener("click", (e) => { e.preventDefault(); window.civicVoice?.handleTranscript("help"); window.civicVoice?.openDock?.(true); });
  const docs = [...document.querySelectorAll("aside a")].find(a => /Documentation/i.test(a.textContent));
  if (docs) { docs.href = "/api/docs"; docs.target = "_blank"; docs.rel = "noopener"; }
}

export function syncHeader() {
  const v = window.civicVoice; if (!v) return;
  const contrast = $("#contrast-toggle");
  if (contrast) setSwitch(contrast, document.documentElement.classList.contains("civic-high-contrast"));
  const label = $("#current-lang-label"); if (label) label.textContent = NAMES[v.state.lang] || "English";
  document.querySelectorAll(".lang-option").forEach(opt => opt.querySelector(".lang-check")?.classList.toggle("hidden", opt.getAttribute("data-lang-code") !== v.state.lang));
  $('header button[title^="Blind-Friendly"]')?.setAttribute("aria-pressed", String(v.state.blind));
}
