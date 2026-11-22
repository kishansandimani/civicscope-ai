// CivicVoice: browser speech-to-text + text-to-speech, spoken navigation, grounded Q&A, accessible dock.
// Uses the Web Speech API (best in Chrome/Edge). Every voice action also has a visual control.
import { api } from "./api.js";
import { toast, escapeHtml } from "./ui.js";
import { parseCommand } from "./voice-commands.js";

const TAGS = { en: "en-IN", hi: "hi-IN", kn: "kn-IN" };
const NAMES = { en: "English", hi: "हिन्दी", kn: "ಕನ್ನಡ" };
const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const synth = window.speechSynthesis;

const state = {
  lang: "en", rate: 1, pitch: 50, listening: false, speaking: false, paused: false,
  lastText: "", lastLang: "en", chimes: true, assertive: false, blind: false, warnedNoVoice: {},
};
const listeners = new Set();
let recognition = null, queue = [], current = null;

function emit() { listeners.forEach(fn => fn({ ...state })); document.dispatchEvent(new CustomEvent("civic:voice-state", { detail: { ...state } })); }
export function onState(fn) { listeners.add(fn); fn({ ...state }); return () => listeners.delete(fn); }
export const supported = { recognition: Boolean(SR), synthesis: Boolean(synth) };

// ------------------------------------------------------------------ preferences
const PREF_CSS = `
html.civic-high-contrast { filter: contrast(1.35) brightness(1.08); }
html.civic-large-text { font-size: 118%; }
html.civic-reduce-motion *, html.civic-reduce-motion *::before, html.civic-reduce-motion *::after { animation: none !important; transition: none !important; }
.civic-sr-only { position:absolute; width:1px; height:1px; overflow:hidden; clip:rect(0 0 0 0); white-space:nowrap; }`;
function injectCss() {
  if (document.getElementById("civic-pref-css")) return;
  const s = document.createElement("style"); s.id = "civic-pref-css"; s.textContent = PREF_CSS; document.head.appendChild(s);
}
export function applySettings(s) {
  injectCss();
  const root = document.documentElement;
  if ("high_contrast" in s) root.classList.toggle("civic-high-contrast", !!s.high_contrast);   // partial patches must not reset other prefs
  if ("large_text" in s) root.classList.toggle("civic-large-text", !!s.large_text);
  if ("reduce_motion" in s) root.classList.toggle("civic-reduce-motion", !!s.reduce_motion);
  if (s.voice_language) state.lang = s.voice_language;
  if (s.speech_rate) state.rate = Number(s.speech_rate);
  if (typeof s.speech_pitch === "number") state.pitch = s.speech_pitch;
  if (typeof s.voice_enabled === "boolean") state.blind = s.voice_enabled;
  emit();
}
let saveTimer, pendingPatch = {};
export function saveSettings(patch) {
  pendingPatch = { ...pendingPatch, ...patch };            // merge: several quick changes must all be saved
  clearTimeout(saveTimer);
  saveTimer = setTimeout(() => {
    const body = pendingPatch; pendingPatch = {};
    api("/settings", { method: "PATCH", body }).catch(e => toast(e.message, "error"));
  }, 400);
}
export function pref(key, fallback) { try { const v = localStorage.getItem("civic:" + key); return v === null ? fallback : JSON.parse(v); } catch { return fallback; } }
export function setPref(key, value) { try { localStorage.setItem("civic:" + key, JSON.stringify(value)); } catch { /* private mode */ } }

// ------------------------------------------------------------------ cues (tactile chimes)
export function cue(kind = "start") {
  if (!state.chimes) return;
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const o = ctx.createOscillator(), g = ctx.createGain();
    o.frequency.value = kind === "start" ? 880 : 440; g.gain.value = 0.08;
    o.connect(g); g.connect(ctx.destination); o.start(); o.stop(ctx.currentTime + 0.12);
    o.onended = () => ctx.close();
  } catch { /* audio not available */ }
  if (navigator.vibrate) navigator.vibrate(kind === "start" ? 40 : [30, 40, 30]);
}

// ------------------------------------------------------------------ speech synthesis
function pickVoice(lang) {
  const voices = synth?.getVoices?.() || [];
  const tag = TAGS[lang];
  return voices.find(v => v.lang === tag) || voices.find(v => v.lang.toLowerCase().startsWith(lang)) || null;
}
function sentences(text, max = 180) {
  const raw = (text || "").replace(/\s+/g, " ").match(/[^.!?।]+[.!?।]?/g) || [text];
  const out = [];
  for (let s of raw) {
    s = s.trim();
    while (s.length > max) { let cut = s.lastIndexOf(" ", max); if (cut < 40) cut = max; out.push(s.slice(0, cut)); s = s.slice(cut).trim(); }
    if (s) out.push(s);
  }
  return out;
}
function playNext() {
  if (!queue.length) { state.speaking = false; state.paused = false; current = null; emit(); cue("end"); return; }
  const u = queue.shift(); current = u;
  u.onend = () => { if (current === u) playNext(); };
  u.onerror = () => { if (current === u) playNext(); };
  synth.speak(u);
}
export function speak(text, { lang = state.lang, remember = true, rate = null } = {}) {
  if (!synth) { toast("This browser cannot read text aloud. Try Chrome or Edge.", "warning"); return; }
  if (!text || !text.trim()) return;
  stopSpeaking(false);
  if (remember) { state.lastText = text; state.lastLang = lang; }
  const voice = pickVoice(lang);
  if (!voice && lang !== "en" && !state.warnedNoVoice[lang]) {
    state.warnedNoVoice[lang] = true;
    toast(`No ${NAMES[lang]} voice is installed on this device, so pronunciation may be wrong. Add one in your system's speech settings.`, "warning");
  }
  queue = sentences(text).map(part => {
    const u = new SpeechSynthesisUtterance(part);
    u.lang = TAGS[lang]; if (voice) u.voice = voice; u.rate = rate ?? state.rate; u.pitch = state.pitch / 50;
    return u;
  });
  state.speaking = true; state.paused = false; emit(); playNext();
}
export function stopSpeaking(notify = true) { queue = []; current = null; synth?.cancel(); state.speaking = false; state.paused = false; if (notify) emit(); }
export function pauseSpeaking() { if (state.speaking && !state.paused) { synth.pause(); state.paused = true; emit(); } }
export function resumeSpeaking() { if (state.paused) { synth.resume(); state.paused = false; emit(); } }
export function repeatLast() { if (state.lastText) speak(state.lastText, { lang: state.lastLang }); else say("There is nothing to repeat yet."); }
export function setRate(r) { state.rate = Math.min(2, Math.max(0.5, Math.round(r * 10) / 10)); emit(); saveSettings({ speech_rate: state.rate }); }
export function setPitch(p) { state.pitch = Math.min(100, Math.max(0, Math.round(p))); emit(); saveSettings({ speech_pitch: state.pitch }); }
export function setLang(code) { if (!TAGS[code]) return; state.lang = code; if (recognition) recognition.lang = TAGS[code]; emit(); saveSettings({ voice_language: code }); }
export function say(msg) { announce(msg); if (state.blind || state.listening) speak(msg, { remember: false }); }

// ------------------------------------------------------------------ live region for screen readers
function announce(msg) {
  let r = document.getElementById("civic-live");
  if (!r) { r = document.createElement("div"); r.id = "civic-live"; r.className = "civic-sr-only"; document.body.appendChild(r); }
  r.setAttribute("aria-live", state.assertive ? "assertive" : "polite");
  r.textContent = ""; setTimeout(() => (r.textContent = msg), 30);
}
export function setAssertive(v) { state.assertive = !!v; emit(); }
export function setChimes(v) { state.chimes = !!v; emit(); }

// ------------------------------------------------------------------ speech recognition
export function startListening() {
  if (!SR) { toast("Speech recognition isn't available in this browser. Use Chrome or Edge, or type your command below.", "warning"); openDock(true); return false; }
  if (state.listening) return true;
  stopSpeaking();
  recognition = new SR();
  recognition.lang = TAGS[state.lang]; recognition.interimResults = false; recognition.maxAlternatives = 1; recognition.continuous = false;
  recognition.onstart = () => { state.listening = true; emit(); cue("start"); announce(`Listening in ${NAMES[state.lang]}`); };
  recognition.onend = () => { state.listening = false; emit(); };
  recognition.onerror = (e) => {
    state.listening = false; emit();
    const msg = { "not-allowed": "Microphone permission was denied. Allow it in your browser's site settings, or type your command.",
      "no-speech": "I didn't hear anything. Try again.", "language-not-supported": `Your browser does not support ${NAMES[state.lang]} recognition.`,
      "audio-capture": "No microphone was found." }[e.error] || "Voice recognition stopped. Try again or type your command.";
    toast(msg, "warning");
  };
  recognition.onresult = (e) => { const text = e.results[0][0].transcript; handleTranscript(text); };
  try { recognition.start(); return true; } catch { return false; }
}
export function stopListening() { try { recognition?.stop(); } catch { /* ignore */ } state.listening = false; emit(); }
export function toggleListening() { return state.listening ? (stopListening(), false) : startListening(); }

// ------------------------------------------------------------------ command execution
export const HELP = "You can say: go to reports; open CivicProbe and audit a website; compare two sources by name; read this page; read the latest discrepancy report; pause; resume; stop; repeat; faster; slower; switch to Kannada or Hindi; or ask a question about your saved reports.";
export const log = [];
function record(role, text, extra = {}) { log.push({ role, text, ...extra, at: new Date() }); document.dispatchEvent(new CustomEvent("civic:voice-log", { detail: log[log.length - 1] })); }

function pageText() {
  const el = document.querySelector("[data-speakable]") || document.querySelector("main") || document.body;
  return (el.innerText || "").replace(/\s+/g, " ").trim().slice(0, 3500);
}
async function readLatestReport(module) {
  const { items } = await api("/reports" + (module ? `?module=${module}` : ""));
  if (!items.length) return say(module ? "You have no saved reports for that module yet." : "You have no saved reports yet.");
  const { text } = await api(`/reports/${items[0].id}/speakable`);
  record("assistant", text, { reportId: items[0].id }); speak(text);
}
async function compareByName(a, b) {
  const { items } = await api("/sources");
  const find = (q) => { const toks = q.split(" ").filter(Boolean); return items.find(s => toks.every(t => s.name.toLowerCase().includes(t))); };
  const sa = find(a), sb = find(b);
  if (!sa || !sb) return say(`I couldn't find ${!sa ? a : b} in your source library. Upload it first, or open InfoConflict and choose sources manually.`);
  if (sa.id === sb.id) return say("Those match the same source. Name two different sources.");
  say(`Opening InfoConflict with ${sa.name} and ${sb.name} selected.`);
  location.href = `/infoconflict?sources=${sa.id},${sb.id}`;
}

export async function handleTranscript(raw) {
  const cmd = parseCommand(raw);
  if (cmd.type === "empty") return;
  record("user", raw);
  try {
    switch (cmd.type) {
      case "lang": setLang(cmd.code); say(`Language set to ${NAMES[cmd.code]}.`); break;
      case "control": {
        const a = cmd.action;
        if (a === "pause") pauseSpeaking();
        else if (a === "resume") resumeSpeaking();
        else if (a === "stop") { stopSpeaking(); stopListening(); }
        else if (a === "repeat") repeatLast();
        else if (a === "faster") { setRate(state.rate + 0.2); say(`Speed ${state.rate.toFixed(1)}.`); }
        else if (a === "slower") { setRate(state.rate - 0.2); say(`Speed ${state.rate.toFixed(1)}.`); }
        else if (a === "help") { record("assistant", HELP); speak(HELP); }
        else if (a === "confirm") document.dispatchEvent(new CustomEvent("civic:voice-confirm"));
        break;
      }
      case "nav": say(`Opening ${cmd.path.replace(/-/g, " ")}.`); setTimeout(() => (location.href = "/" + cmd.path), 700); break;
      case "probe": say(`Opening CivicProbe for ${cmd.url}. Say confirm or press Start Audit.`); setTimeout(() => (location.href = `/civicprobe?url=${encodeURIComponent(cmd.url)}&voice=1`), 900); break;
      case "compare": await compareByName(cmd.a, cmd.b); break;
      case "read":
        if (cmd.target === "page") { const t = pageText(); record("assistant", t); speak(t); } else await readLatestReport(cmd.module);
        break;
      case "mode": {
        const patch = { voice_enabled: true, ...(cmd.contrast ? { high_contrast: true } : {}) };
        applySettings(patch); saveSettings(patch); say("Blind-friendly mode is on. Results will be read aloud and contrast is increased."); break;
      }
      case "ask": {
        const lang = cmd.language || state.lang;
        const res = await api("/voice/ask", { method: "POST", body: { question: cmd.question, language: lang } });
        record("assistant", res.answer, { references: res.references, lang }); speak(res.answer, { lang });
        break;
      }
    }
  } catch (e) { record("assistant", e.message, { error: true }); toast(e.message, "error"); announce(e.message); }
}

// ------------------------------------------------------------------ dock (visual controls on every page)
let dock;
export function openDock(open = true) { dock?.querySelector("[data-panel]")?.classList.toggle("hidden", !open); dock?.querySelector("[data-toggle]")?.setAttribute("aria-expanded", String(open)); }

function buildDock() {
  dock = document.createElement("div");
  dock.id = "civic-dock"; dock.className = "fixed bottom-5 left-5 z-[90] font-sans";
  dock.innerHTML = `
  <button data-toggle type="button" aria-expanded="false" aria-controls="civic-dock-panel" aria-label="CivicVoice voice assistant (Alt+V to listen)"
     class="h-12 w-12 rounded-full bg-gradient-to-br from-violet-600 to-cyan-500 text-white border border-white/30 shadow-[0_8px_24px_rgba(0,0,0,0.6)] flex items-center justify-center focus:outline-none focus:ring-2 focus:ring-purple-300">
     <span class="material-symbols-outlined">record_voice_over</span></button>
  <div id="civic-dock-panel" data-panel class="hidden absolute bottom-14 left-0 w-80 rounded-2xl bg-[#101221]/95 backdrop-blur-2xl border border-white/15 shadow-[0_20px_50px_rgba(0,0,0,0.7)] p-4 text-white text-sm" role="region" aria-label="CivicVoice controls">
    <div class="flex items-center justify-between mb-3"><span class="font-bold">CivicVoice</span>
      <select data-lang aria-label="Voice language" class="bg-[#0b0d1b] border border-white/15 rounded-lg px-2 py-1 text-xs">
        <option value="en">English</option><option value="hi">हिन्दी</option><option value="kn">ಕನ್ನಡ</option></select></div>
    <div class="flex gap-2 mb-3">
      <button data-act="listen" type="button" aria-pressed="false" class="flex-1 rounded-xl py-2 bg-violet-600/80 hover:bg-violet-500 border border-white/20 flex items-center justify-center gap-1"><span class="material-symbols-outlined text-[18px]">mic</span><span data-listen-label>Listen</span></button>
      <button data-act="pause" type="button" aria-label="Pause or resume reading" class="rounded-xl px-3 bg-white/10 hover:bg-white/20 border border-white/15"><span class="material-symbols-outlined text-[18px]">pause</span></button>
      <button data-act="stop" type="button" aria-label="Stop reading" class="rounded-xl px-3 bg-white/10 hover:bg-white/20 border border-white/15"><span class="material-symbols-outlined text-[18px]">stop</span></button>
      <button data-act="repeat" type="button" aria-label="Repeat last answer" class="rounded-xl px-3 bg-white/10 hover:bg-white/20 border border-white/15"><span class="material-symbols-outlined text-[18px]">replay</span></button></div>
    <div class="flex items-center gap-2 mb-3"><button data-act="slower" type="button" aria-label="Slower" class="rounded-lg px-2 py-1 bg-white/10 border border-white/15">−</button>
      <span class="text-xs flex-1 text-center">Speed <b data-rate>1.0</b>×</span>
      <button data-act="faster" type="button" aria-label="Faster" class="rounded-lg px-2 py-1 bg-white/10 border border-white/15">+</button></div>
    <label class="block text-xs mb-1" for="civic-dock-text">Type a command or question</label>
    <form data-form class="flex gap-2"><input id="civic-dock-text" type="text" autocomplete="off" maxlength="500" placeholder="e.g. go to reports" class="flex-1 bg-[#0b0d1b] border border-white/15 rounded-lg px-3 py-1.5 focus:outline-none focus:border-purple-400/60">
      <button type="submit" class="rounded-lg px-3 bg-cyan-600/80 hover:bg-cyan-500 border border-white/20">Go</button></form>
    <p data-out class="mt-3 text-xs text-violet-200/80 max-h-28 overflow-auto" aria-live="polite"></p>
    <p class="mt-2 text-[10px] text-violet-300/50">Alt+V listen · Alt+R repeat · Alt+S stop. ${SR ? "" : "Voice input needs Chrome or Edge; typing works everywhere."}</p>
  </div>`;
  document.body.appendChild(dock);
  const q = (s) => dock.querySelector(s);
  q("[data-toggle]").addEventListener("click", () => openDock(q("[data-panel]").classList.contains("hidden")));
  q("[data-lang]").addEventListener("change", e => setLang(e.target.value));
  dock.addEventListener("click", e => {
    const act = e.target.closest("[data-act]")?.dataset.act; if (!act) return;
    ({ listen: toggleListening, pause: () => (state.paused ? resumeSpeaking() : pauseSpeaking()), stop: () => { stopSpeaking(); stopListening(); },
       repeat: repeatLast, slower: () => setRate(state.rate - 0.1), faster: () => setRate(state.rate + 0.1) })[act]();
  });
  q("[data-form]").addEventListener("submit", e => { e.preventDefault(); const i = q("#civic-dock-text"); const v = i.value.trim(); i.value = ""; if (v) handleTranscript(v); });
  onState(s => {
    q("[data-lang]").value = s.lang; q("[data-rate]").textContent = s.rate.toFixed(1);
    q("[data-act=listen]").setAttribute("aria-pressed", String(s.listening)); q("[data-listen-label]").textContent = s.listening ? "Listening…" : "Listen";
    q("[data-act=pause] span").textContent = s.paused ? "play_arrow" : "pause";
  });
  document.addEventListener("civic:voice-log", e => { q("[data-out]").textContent = (e.detail.role === "user" ? "You: " : "CivicVoice: ") + e.detail.text.slice(0, 400); });
}

function bindShortcuts() {
  window.addEventListener("keydown", (e) => {
    if (!e.altKey || e.ctrlKey || e.metaKey) return;
    const k = e.key.toLowerCase();
    if (k === "v") { e.preventDefault(); toggleListening(); }
    else if (k === "r") { e.preventDefault(); repeatLast(); }
    else if (k === "s") { e.preventDefault(); stopSpeaking(); stopListening(); }
  });
}

export async function initVoice() {
  state.chimes = pref("chimes", true); state.assertive = pref("assertive", false);
  synth?.getVoices?.();                       // warm up the voice list
  try { applySettings(await api("/settings")); } catch { /* settings optional */ }
  bindShortcuts();
  if (document.body.dataset.page !== "civicvoice") buildDock();
  window.civicVoice = { speak, say, stopSpeaking, pauseSpeaking, resumeSpeaking, repeatLast, startListening, stopListening, toggleListening,
    handleTranscript, setRate, setPitch, setLang, setChimes, setAssertive, applySettings, saveSettings, cue, onState, log, state, supported, pref, setPref, escapeHtml };
  document.dispatchEvent(new CustomEvent("civic:voice-ready"));
}
