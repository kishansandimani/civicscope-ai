// Pure spoken-command parser (no DOM) so it can be unit-tested. Supports English, Hindi and Kannada keywords.
const NAV = {
  "overview": ["overview", "dashboard", "home", "होम", "डैशबोर्ड", "ಡ್ಯಾಶ್‌ಬೋರ್ಡ್", "ಡ್ಯಾಶ್ಬೋರ್ಡ್", "ಮುಖಪುಟ", "ಡ್ಯಾಶ್ ಬೋರ್ಡ್"],
  "civicprobe": ["civic probe", "civicprobe", "website auditor", "probe", "सिविक प्रोब", "ಸಿವಿಕ್ ಪ್ರೋಬ್"],
  "infoconflict": ["info conflict", "infoconflict", "conflict detector", "conflicts", "इन्फो कॉन्फ्लिक्ट", "ಇನ್ಫೋ ಕಾನ್ಫ್ಲಿಕ್ಟ್"],
  "accessshadow": ["access shadow", "accessshadow", "accessibility analyzer", "accessibility analyser", "एक्सेस शैडो", "ಆಕ್ಸೆಸ್ ಶ್ಯಾಡೋ"],
  "rulestress-ai": ["rule stress", "rulestress", "scenario tester", "रूल स्ट्रेस", "ರೂಲ್ ಸ್ಟ್ರೆಸ್"],
  "promisetrace": ["promise trace", "promisetrace", "promise tracker", "commitments", "प्रॉमिस ट्रेस", "ಪ್ರಾಮಿಸ್ ಟ್ರೇಸ್"],
  "civicvoice": ["civic voice", "civicvoice", "voice assistant", "सिविक वॉइस", "ಸಿವಿಕ್ ವಾಯ್ಸ್"],
  "reports-and-findings": ["reports", "report page", "findings", "रिपोर्ट", "रिपोर्ट्स", "ವರದಿ", "ರಿಪೋರ್ಟ್"],
  "source-library": ["source library", "library", "sources", "स्रोत", "ಮೂಲಗಳು"],
  "accessibility-settings": ["accessibility settings", "पहुंच सेटिंग", "ಪ್ರವೇಶ ಸೆಟ್ಟಿಂಗ್"],
  "platform-settings": ["platform settings", "settings", "सेटिंग", "ಸೆಟ್ಟಿಂಗ್", "ಸೆಟ್ಟಿಂಗ್ಸ್"],
};
const NAV_VERBS = /\b(go to|open|show|navigate|take me to|switch to)\b|खोलो|खोलें|जाओ|जाइए|दिखाओ|ತೆರೆಯಿರಿ|ತೆರೆ|ಹೋಗಿ|ತೋರಿಸಿ/;
const READ_MODULE = [
  ["infoconflict", /discrepanc|conflict|विसंगति|ಅಸಂಗತ|ಸಂಘರ್ಷ/],
  ["accessshadow", /accessib|एक्सेस|ಪ್ರವೇಶ/],
  ["civicprobe", /audit|probe|website|ऑडिट|ಆಡಿಟ್/],
  ["rulestress", /scenario|rule|नियम|ನಿಯಮ/],
  ["promisetrace", /promise|commitment|वादा|ಭರವಸೆ/],
];
const LANGS = [["hi", /hindi|हिंदी|हिन्दी/], ["kn", /kannada|ಕನ್ನಡ|कन्नड़|कन्नड/], ["en", /english|अंग्रेज़ी|अंग्रेजी|ಇಂಗ್ಲಿಷ್/]];

const CONTROLS = [
  ["pause", /^(please )?(pause|hold on)\b|^(रुको|पॉज़|पॉज|रुकिए|ವಿರಾಮ)/],
  ["resume", /^(please )?(resume|continue|carry on|जारी रखो|जारी रखें|आगे बढ़ो|ಮುಂದುವರಿಸಿ|ಮುಂದುವರೆಸಿ)/],
  ["stop", /^(please )?(stop|quiet|silence|बंद करो|बंद करें|चुप|ನಿಲ್ಲಿಸಿ|ಸಾಕು)/],
  ["repeat", /^(please )?(repeat|say (that )?again|once more|दोबारा|फिर से बोलो|फिर से सुनाओ|ಮತ್ತೆ ಹೇಳಿ|ಪುನಃ)/],
  ["faster", /(speed up|faster|तेज़|तेज बोलो|ವೇಗವಾಗಿ)/],
  ["slower", /(slow down|slower|धीमा|धीरे|ನಿಧಾನ)/],
  ["help", /^(help|what can i say|commands|मदद|सहायता|ಸಹಾಯ)/],
  ["confirm", /^(confirm|yes start|start it|go ahead|पुष्टि|हाँ शुरू|ಖಚಿತಪಡಿಸಿ|ಹೌದು ಪ್ರಾರಂಭಿಸಿ)/],
];

export function normaliseSpoken(raw) {
  return (raw || "").toLowerCase().replace(/[.,!?;]+$/g, "").replace(/\s+/g, " ").trim();
}

export function extractDomain(text) {
  const t = text.replace(/\s*\b(dot|डॉट|ಡಾಟ್)\b\s*/g, ".").replace(/\s*\b(dash|hyphen)\b\s*/g, "-");
  const m = t.match(/\b((?:https?:\/\/)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:\/[^\s]*)?)/i);
  return m ? m[1].replace(/[.,]+$/, "") : null;
}

export function parseCommand(raw) {
  const t = normaliseSpoken(raw);
  if (!t) return { type: "empty" };
  const words = t.split(" ").length;

  if (words <= 5) {
    for (const [code, rx] of LANGS) if (rx.test(t) && !/audit|compare|read|report/.test(t)) return { type: "lang", code };
  }
  if (words <= 6) {
    for (const [action, rx] of CONTROLS) if (rx.test(t)) return { type: "control", action };
  }
  const domain = extractDomain(t);
  if (domain && /(audit|check|probe|scan|inspect|ऑडिट|जांच|ಆಡಿಟ್|ಪರಿಶೀಲ)/.test(t)) return { type: "probe", url: domain };

  const cmp = t.match(/compare (.+?) (?:with|and|to|versus|vs) (.+)$/);
  if (cmp) return { type: "compare", a: cmp[1].trim(), b: cmp[2].trim() };

  if (/(enable|turn on|activate|switch on)\b.*(blind|high contrast)|(ब्लाइंड|हाई कंट्रास्ट|ಹೈ ಕಾಂಟ್ರಾಸ್ಟ್)/.test(t)) return { type: "mode", blind: /blind|ब्लाइंड/.test(t), contrast: /contrast|कंट्रास्ट|ಕಾಂಟ್ರಾಸ್ಟ್/.test(t) };

  if (/\b(read|read out|read aloud)\b|पढ़ो|पढ़ें|पढ़कर सुनाओ|ಓದಿ/.test(t)) {
    if (/(this page|the page|screen|इस पेज|ಈ ಪುಟ)/.test(t)) return { type: "read", target: "page" };
    for (const [module, rx] of READ_MODULE) if (rx.test(t)) return { type: "read", target: "report", module };
    if (/(report|results?|findings?|रिपोर्ट|ವರದಿ|latest|last)/.test(t)) return { type: "read", target: "report", module: null };
    return { type: "read", target: "page" };
  }

  if (NAV_VERBS.test(t)) {
    let best = null;
    for (const [path, keys] of Object.entries(NAV)) {
      for (const k of keys) {
        if (t.includes(k) && (!best || k.length > best.len)) best = { path, len: k.length };
      }
    }
    if (best) return { type: "nav", path: best.path };
  }

  let language = null;
  for (const [code, rx] of LANGS) if (new RegExp(`(in|में|ನಲ್ಲಿ)\\s+(plain\\s+)?(${rx.source})`).test(t)) language = code;
  return { type: "ask", question: raw.trim(), language };
}
