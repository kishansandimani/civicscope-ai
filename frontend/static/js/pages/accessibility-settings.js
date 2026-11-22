import { api } from "../api.js";
import { toast } from "../ui.js";

const $ = (s) => document.querySelector(s);
const SAMPLE = {
  en: "This is CivicVoice. Reports will be read aloud at this speed and pitch.",
  hi: "यह सिविक वॉइस है। रिपोर्ट इसी गति और स्वर में पढ़ी जाएंगी।",
  kn: "ಇದು ಸಿವಿಕ್ ವಾಯ್ಸ್. ವರದಿಗಳನ್ನು ಈ ವೇಗ ಮತ್ತು ಸ್ವರದಲ್ಲಿ ಓದಲಾಗುತ್ತದೆ.",
};
const DEFAULTS = { voice_enabled: false, voice_language: "en", speech_rate: 1.0, speech_pitch: 50, high_contrast: false, large_text: false, reduce_motion: false };

function fill(s) {
  $("#as-voice").checked = !!s.voice_enabled; $("#as-lang").value = s.voice_language || "en";
  $("#as-rate").value = s.speech_rate ?? 1; $("#as-rate-v").textContent = Number(s.speech_rate ?? 1).toFixed(1);
  $("#as-pitch").value = s.speech_pitch ?? 50; $("#as-pitch-v").textContent = s.speech_pitch ?? 50;
  $("#as-contrast").checked = !!s.high_contrast; $("#as-large").checked = !!s.large_text; $("#as-motion").checked = !!s.reduce_motion;
}

async function init() {
  const v = window.civicVoice;
  let settings;
  try { settings = await api("/settings"); } catch (e) { toast(e.message, "error"); return; }
  fill(settings);
  if (!v) return toast("Voice is still loading; reload if the controls do not respond.", "warning");
  if (!v.supported.synthesis) $("#as-voice-note").textContent = "This browser cannot read text aloud. Try Chrome or Edge.";
  const change = (patch) => { v.applySettings(patch); v.saveSettings(patch); };
  $("#as-voice").addEventListener("change", e => { change({ voice_enabled: e.target.checked }); v.say(e.target.checked ? "Blind-friendly mode on." : "Blind-friendly mode off."); });
  $("#as-lang").addEventListener("change", e => { v.setLang(e.target.value); });
  $("#as-rate").addEventListener("input", e => { const r = parseFloat(e.target.value); $("#as-rate-v").textContent = r.toFixed(1); v.setRate(r); });
  $("#as-pitch").addEventListener("input", e => { const p = parseInt(e.target.value, 10); $("#as-pitch-v").textContent = p; v.setPitch(p); });
  $("#as-contrast").addEventListener("change", e => change({ high_contrast: e.target.checked }));
  $("#as-large").addEventListener("change", e => change({ large_text: e.target.checked }));
  $("#as-motion").addEventListener("change", e => change({ reduce_motion: e.target.checked }));
  $("#as-test").addEventListener("click", () => { const l = $("#as-lang").value; v.speak(SAMPLE[l], { lang: l }); });
  $("#as-reset").addEventListener("click", () => { fill(DEFAULTS); v.applySettings(DEFAULTS); v.saveSettings(DEFAULTS); toast("Accessibility settings reset to defaults.", "success"); });
}

if (window.civicVoice) init(); else document.addEventListener("civic:voice-ready", init, { once: true });
