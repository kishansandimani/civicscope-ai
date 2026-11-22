// CivicVoice page controller: binds every control on /civicvoice to the shared voice engine.
import { api } from "./api.js";
import { toast } from "./ui.js";
import { HELP } from "./voice.js";

const NAMES = { en: "English (IN)", hi: "हिन्दी (Hindi)", kn: "ಕನ್ನಡ (Kannada)" };

function textNode(startsWith) {
  const w = document.createTreeWalker(document.querySelector("main"), NodeFilter.SHOW_TEXT);
  while (w.nextNode()) if (w.currentNode.nodeValue.trim().startsWith(startsWith)) return w.currentNode;
  return null;
}

function setup() {
  const v = window.civicVoice;
  if (!v) return;
  const $ = (s) => document.querySelector(s);
  const all = (s) => [...document.querySelectorAll(s)];
  const status = $("#assistantStatusRegion");
  const micChip = textNode("Microphone input:");
  const srChip = textNode("Speech recognition:");
  if (srChip) srChip.nodeValue = v.supported.recognition ? "Speech recognition: available in this browser" : "Speech recognition: not supported here, use the text box";
  if (!v.supported.synthesis) toast("This browser cannot read text aloud. Try Chrome or Edge.", "warning");

  // ---- status region + sliders reflect live state
  function render(s) {
    const lang = NAMES[s.lang];
    const dot = s.listening ? "bg-cyan-400 shadow-[0_0_10px_#06b6d4] animate-ping" : s.speaking ? "bg-purple-400 animate-pulse" : "bg-white/30";
    const headline = s.listening ? `Listening in <span class="bg-gradient-to-r from-purple-300 to-cyan-300 bg-clip-text text-transparent"></span>…`
      : s.speaking ? (s.paused ? "Paused." : "Speaking…") : "Voice assistant is idle.";
    status.setAttribute("role", "status"); status.setAttribute("aria-live", s.assertive ? "assertive" : "polite");
    status.innerHTML = `<div class="flex items-center justify-center gap-2"><span class="h-2.5 w-2.5 rounded-full ${dot}"></span>
      <p class="font-headline-sm text-headline-sm text-white font-bold tracking-wide">${headline}</p></div>
      <p class="font-body-sm text-body-sm text-on-surface-variant font-medium">Press <kbd class="font-code-sm bg-white/10 border border-white/15 px-2 py-0.5 rounded-lg text-white">Space</kbd> or Alt+V to ${s.listening ? "stop" : "start"} listening.</p>`;
    const span = status.querySelector("span.bg-clip-text"); if (span) span.textContent = lang;
    if (micChip) micChip.nodeValue = s.listening ? "Microphone input: listening" : "Microphone input: idle";
    $("#centralMicBtn")?.setAttribute("aria-pressed", String(s.listening));
    $("#centralMicBtn")?.classList.toggle("opacity-70", !s.listening);
    all("[data-cv-lang]").forEach(b => { const on = b.dataset.cvLang === s.lang; b.setAttribute("aria-pressed", String(on)); b.classList.toggle("ring-2", on); b.classList.toggle("ring-purple-300", on); });
    const sp = $("#speedSlider"); if (sp && document.activeElement !== sp) sp.value = s.rate;
    $("#speedValue") && ($("#speedValue").textContent = s.rate.toFixed(1) + "x");
    const pt = $("#pitchSlider"); if (pt && document.activeElement !== pt) pt.value = s.pitch;
    $("#pitchValue") && ($("#pitchValue").textContent = s.pitch < 35 ? "Deep" : s.pitch > 65 ? "High clarity" : "Standard");
    const blind = $("#blindModeToggle"); if (blind) { blind.setAttribute("aria-pressed", String(s.blind)); const n = textNode("Blind-Friendly"); if (n) n.nodeValue = s.blind ? "Blind-Friendly On" : "Blind-Friendly Off"; }
    const chimes = $("[data-cv=chimes]"); if (chimes) chimes.checked = s.chimes;
    const as = $("[data-cv=assertive]"); if (as) as.checked = s.assertive;
  }
  v.onState(render);

  // ---- main controls
  const bind = (sel, fn) => all(sel).forEach(el => el.addEventListener("click", fn));
  bind("#centralMicBtn, [data-cv=listen]", () => v.toggleListening());
  bind("[data-cv=stop]", () => { v.stopSpeaking(); v.stopListening(); });
  bind("[data-cv=repeat]", () => v.repeatLast());
  bind("[data-cv=slow], [data-cv=replay-slow]", () => v.state.lastText ? v.speak(v.state.lastText, { lang: v.state.lastLang, rate: 0.8 }) : v.say("There is nothing to replay yet."));
  bind("[data-cv=cue]", () => { v.cue("start"); setTimeout(() => v.cue("end"), 250); });
  bind("[data-cv=manual]", () => v.handleTranscript("help"));
  bind("[data-cv-lang]", (e) => v.setLang(e.currentTarget.dataset.cvLang));
  bind("[data-cv=reset]", () => { v.setRate(1); v.setPitch(50); toast("Speech settings reset.", "success"); });
  $("#speedSlider")?.addEventListener("input", e => v.setRate(parseFloat(e.target.value)));
  $("#pitchSlider")?.addEventListener("input", e => v.setPitch(parseInt(e.target.value, 10)));
  $("#blindModeToggle")?.addEventListener("click", () => {
    const on = !v.state.blind; const patch = { voice_enabled: on, ...(on ? { high_contrast: true } : {}) };
    v.applySettings(patch); v.saveSettings(patch); v.say(on ? "Blind-friendly mode on. Results will be read aloud." : "Blind-friendly mode off.");
  });
  $("#contrastQuickToggle")?.addEventListener("click", () => {
    const on = !document.documentElement.classList.contains("civic-high-contrast");
    v.applySettings({ high_contrast: on }); v.saveSettings({ high_contrast: on });
  });
  $("[data-cv=chimes]")?.addEventListener("change", e => { v.setChimes(e.target.checked); v.setPref("chimes", e.target.checked); });
  $("[data-cv=assertive]")?.addEventListener("change", e => { v.setAssertive(e.target.checked); v.setPref("assertive", e.target.checked); });
  window.addEventListener("keydown", e => {
    if (e.code === "Space" && e.target === document.body) { e.preventDefault(); v.toggleListening(); }
  });

  // ---- command library: tap or press Enter/Space to run the shown phrase
  all("[data-cv-phrase]").forEach(card => {
    const run = () => v.handleTranscript(card.dataset.cvPhrase);
    card.addEventListener("click", run);
    card.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); run(); } });
  });

  // ---- typed input (visual alternative to speaking)
  $("#cv-form")?.addEventListener("submit", e => {
    e.preventDefault(); const i = $("#cv-input"); const t = i.value.trim(); i.value = ""; if (t) v.handleTranscript(t);
  });

  // ---- transcript
  const box = $("#cv-transcript");
  function addMessage(m) {
    $("#cv-empty")?.remove(); $("#cv-actions")?.classList.remove("hidden");
    const user = m.role === "user";
    const card = document.createElement("div");
    card.className = `rounded-2xl p-4 border ${m.error ? "border-rose-400/50 bg-rose-500/10" : user ? "border-cyan-400/30 bg-cyan-500/5" : "border-purple-400/30 bg-purple-500/5"}`;
    const who = document.createElement("div"); who.className = "text-xs uppercase tracking-wider text-violet-300/70 mb-1";
    who.textContent = user ? "You" : m.error ? "CivicVoice · problem" : "CivicVoice";
    const body = document.createElement("div"); body.className = "text-white leading-relaxed"; body.textContent = m.text;   // textContent: never HTML
    card.append(who, body);
    if (m.references?.length) {
      const refs = document.createElement("div"); refs.className = "mt-2 flex flex-wrap gap-2";
      m.references.forEach(r => { const a = document.createElement("a"); a.href = "/reports-and-findings"; a.className = "text-xs px-2 py-1 rounded-lg bg-white/10 border border-white/15 text-violet-200 underline"; a.textContent = `Ref: ${r.title}`; refs.appendChild(a); });
      card.appendChild(refs);
    }
    box.appendChild(card); card.scrollIntoView({ block: "nearest" });
  }
  v.log.forEach(addMessage);
  document.addEventListener("civic:voice-log", e => addMessage(e.detail));

  const transcriptText = () => v.log.map(m => `${m.role === "user" ? "You" : "CivicVoice"}: ${m.text}`).join("\n\n");
  async function readIn(lang) {
    const last = [...v.log].reverse().find(m => m.role === "assistant" && !m.error);
    if (!last) return toast("There is no answer to translate yet.", "warning");
    try {
      const { translation } = await api("/voice/translate", { method: "POST", body: { text: last.text.slice(0, 4000), target: lang } });
      document.dispatchEvent(new CustomEvent("civic:voice-log", { detail: { role: "assistant", text: translation, lang } }));
      v.log.push({ role: "assistant", text: translation, lang });
      v.speak(translation, { lang });
    } catch (e) { toast(e.message, "error"); }
  }
  bind("[data-cv=read-kn]", () => readIn("kn"));
  bind("[data-cv=read-hi]", () => readIn("hi"));
  bind("[data-cv=copy]", async () => { try { await navigator.clipboard.writeText(transcriptText()); toast("Transcript copied.", "success"); } catch { toast("Copy was blocked by the browser.", "error"); } });
  bind("[data-cv=download]", () => {
    const url = URL.createObjectURL(new Blob([transcriptText()], { type: "text/plain;charset=utf-8" }));
    const a = Object.assign(document.createElement("a"), { href: url, download: "civicvoice-transcript.txt" }); a.click(); URL.revokeObjectURL(url);
  });
}

if (window.civicVoice) setup(); else document.addEventListener("civic:voice-ready", setup, { once: true });
