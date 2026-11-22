"""AccessShadow — automated accessibility checks for web pages and PDFs.

Everything here is a deterministic rule applied to real markup / PDF structure. Items that machines cannot judge
(colour contrast, reading order as announced, caption quality ...) are listed separately as manual-review items,
never as automated pass/fail results.
"""
import re
from collections import Counter
from dataclasses import asdict, dataclass, field
from io import BytesIO

from bs4 import BeautifulSoup

GENERIC_LINK_TEXT = {"click here", "here", "read more", "more", "link", "details", "know more", "click", "यहाँ क्लिक करें", "यहां क्लिक करें", "ಇಲ್ಲಿ ಕ್ಲಿಕ್ ಮಾಡಿ"}
NON_TEXT_INPUT = {"hidden", "submit", "button", "reset", "image"}
SCRIPTS = {"Devanagari": (0x0900, 0x097F), "Kannada": (0x0C80, 0x0CFF), "Tamil": (0x0B80, 0x0BFF),
           "Telugu": (0x0C00, 0x0C7F), "Bengali": (0x0980, 0x09FF), "Latin": (0x0041, 0x024F)}
LANG_SCRIPT = {"en": "Latin", "hi": "Devanagari", "kn": "Kannada", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "mr": "Devanagari"}
WCAG = {"alt": "WCAG 1.1.1", "heading": "WCAG 1.3.1 / 2.4.6", "label": "WCAG 1.3.1 / 3.3.2 / 4.1.2", "link": "WCAG 2.4.4",
        "lang": "WCAG 3.1.1 / 3.1.2", "keyboard": "WCAG 2.1.1", "zoom": "WCAG 1.4.4", "title": "WCAG 2.4.2",
        "skip": "WCAG 2.4.1", "table": "WCAG 1.3.1", "frame": "WCAG 4.1.2", "pdf": "PDF/UA / WCAG 1.3.1"}


@dataclass
class A11yFinding:
    rule: str
    severity: str            # high | medium | low
    description: str
    evidence: str            # markup / structure that triggered the rule (verbatim, truncated)
    count: int = 1
    wcag: str = ""
    kind: str = "automated"  # automated findings only; manual items use ManualItem
    locations: list[str] = field(default_factory=list)


@dataclass
class ManualItem:
    check: str
    why_manual: str
    how_to_test: str
    prompted_by: str | None = None


def _snip(tag, n=160) -> str:
    return re.sub(r"\s+", " ", str(tag))[:n]


def script_share(text: str) -> dict[str, float]:
    counts: Counter = Counter()
    for ch in text:
        o = ord(ch)
        if ch.isalpha():
            for name, (lo, hi) in SCRIPTS.items():
                if lo <= o <= hi:
                    counts[name] += 1
                    break
    total = sum(counts.values())
    return {k: round(v / total, 3) for k, v in counts.most_common()} if total else {}


def _labelled(soup, el) -> bool:
    if el.get("aria-label", "").strip() or el.get("aria-labelledby", "").strip() or el.get("title", "").strip():
        return True
    if el.get("id") and soup.find("label", attrs={"for": el["id"]}):
        return True
    return el.find_parent("label") is not None


def _add(bucket: dict, rule, severity, description, evidence, wcag, location=None):
    f = bucket.get(rule)
    if f is None:
        bucket[rule] = A11yFinding(rule, severity, description, evidence, 1, wcag, "automated", [location] if location else [])
    else:
        f.count += 1


def analyze_html(html: str, url: str) -> dict:
    soup = BeautifulSoup(html or "", "lxml")
    f: dict[str, A11yFinding] = {}
    manual: list[ManualItem] = []

    html_tag = soup.find("html")
    lang = (html_tag.get("lang") or "").strip() if html_tag else ""
    if not lang:
        _add(f, "missing_lang", "medium", "The page does not declare its language, so screen readers may pronounce it with the wrong voice.", "<html> has no lang attribute", WCAG["lang"])
    if not (soup.title and soup.title.get_text(strip=True)):
        _add(f, "missing_title", "medium", "The page has no title.", "no <title> element", WCAG["title"])

    imgs = soup.find_all("img")
    empty_alt = 0
    for img in imgs:
        if not img.has_attr("alt"):
            _add(f, "img_missing_alt", "high", "Images without an alt attribute are announced as file names or skipped by screen readers.", _snip(img), WCAG["alt"], img.get("src", "")[:120])
        elif not img["alt"].strip():
            empty_alt += 1
    if empty_alt:
        manual.append(ManualItem("Confirm empty-alt images are decorative", "A tool cannot tell whether an image carries information.",
                                 "Review each image with alt=\"\"; add real alt text if it conveys meaning (e.g. charts, scanned notices).", f"{empty_alt} image(s) have alt=\"\""))
    for a in soup.find_all("area"):
        if not a.get("alt", "").strip():
            _add(f, "area_missing_alt", "high", "Image-map areas need alt text.", _snip(a), WCAG["alt"])

    levels = [int(h.name[1]) for h in soup.find_all(re.compile(r"^h[1-6]$"))]
    if not levels:
        _add(f, "no_headings", "medium", "The page has no headings, so screen-reader users cannot jump between sections.", "no <h1>–<h6> found", WCAG["heading"])
    else:
        if levels.count(1) == 0:
            _add(f, "no_h1", "medium", "The page has no main (h1) heading.", f"heading levels: {levels[:12]}", WCAG["heading"])
        if levels.count(1) > 1:
            _add(f, "multiple_h1", "low", "The page has more than one h1 heading.", f"{levels.count(1)} h1 elements", WCAG["heading"])
        for prev, cur in zip(levels, levels[1:]):
            if cur > prev + 1:
                _add(f, "skipped_heading_level", "low", "Heading levels skip (for example h2 followed by h4), which confuses document outlines.", f"h{prev} → h{cur}", WCAG["heading"])
    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        if not h.get_text(strip=True) and not h.find("img", alt=True):
            _add(f, "empty_heading", "medium", "A heading element is empty.", _snip(h), WCAG["heading"])

    for el in soup.find_all(["input", "select", "textarea"]):
        if el.name == "input" and (el.get("type", "text").lower() in NON_TEXT_INPUT):
            if el.get("type", "").lower() == "image" and not el.get("alt", "").strip():
                _add(f, "image_button_no_alt", "high", "Image buttons need alt text.", _snip(el), WCAG["label"])
            continue
        if not _labelled(soup, el):
            _add(f, "form_control_no_label", "high", "A form field has no programmatic label (label/for, aria-label or title). Placeholder text alone is not a label.", _snip(el), WCAG["label"])
    for b in soup.find_all("button"):
        if not (b.get_text(strip=True) or b.get("aria-label", "").strip() or b.get("title", "").strip() or b.find("img", alt=re.compile(r"\S"))):
            _add(f, "button_no_name", "high", "A button has no accessible name.", _snip(b), WCAG["label"])

    for a in soup.find_all("a", href=True):
        name = a.get_text(" ", strip=True) or a.get("aria-label", "").strip() or a.get("title", "").strip()
        if not name and a.find("img", alt=re.compile(r"\S")):
            continue
        if not name:
            _add(f, "link_no_name", "high", "A link has no discernible text.", _snip(a), WCAG["link"], a["href"][:120])
        elif name.lower() in GENERIC_LINK_TEXT:
            _add(f, "generic_link_text", "low", "Link text like “click here” or “read more” is meaningless out of context (screen readers list links on their own).", _snip(a), WCAG["link"], a["href"][:120])

    for el in soup.find_all(["div", "span", "li", "td"], attrs={"onclick": True}):
        if not el.get("tabindex") and not el.get("role"):
            _add(f, "click_not_keyboard_accessible", "high", "An element reacts to mouse clicks but cannot be reached or activated by keyboard.", _snip(el), WCAG["keyboard"])
    if soup.find(attrs={"tabindex": re.compile(r"^[1-9]\d*$")}):
        _add(f, "positive_tabindex", "medium", "tabindex values above 0 override the natural keyboard order and usually cause confusing navigation.", "tabindex > 0 present", WCAG["keyboard"])

    for fr in soup.find_all(["iframe", "frame"]):
        if not fr.get("title", "").strip():
            _add(f, "frame_no_title", "medium", "A frame has no title describing its content.", _snip(fr), WCAG["frame"])
    for t in soup.find_all("table"):
        if not t.find("th") and len(t.find_all("tr")) > 1:
            _add(f, "table_no_headers", "medium", "A data table has no header cells (th), so screen readers cannot associate cells with headers.", _snip(t, 120), WCAG["table"])

    vp = soup.find("meta", attrs={"name": re.compile("^viewport$", re.I)})
    if vp:
        c = vp.get("content", "").lower().replace(" ", "")
        m = re.search(r"maximum-scale=([\d.]+)", c)
        if "user-scalable=no" in c or "user-scalable=0" in c or (m and float(m.group(1)) < 2):
            _add(f, "zoom_disabled", "high", "Pinch-zoom is blocked, which prevents low-vision users from enlarging text on phones.", _snip(vp), WCAG["zoom"])

    first_links = [a.get("href", "") for a in soup.find_all("a", href=True)][:5]
    if not any(h.startswith("#") and len(h) > 1 for h in first_links):
        _add(f, "no_skip_link", "low", "No “skip to main content” link was found near the top (best practice for keyboard users).", "first links: " + ", ".join(first_links[:3]), WCAG["skip"])

    # --- language accessibility
    for t in soup(["script", "style", "noscript"]):
        t.decompose()
    text = soup.get_text(" ", strip=True)
    share = script_share(text)
    lang_findings = []
    declared = LANG_SCRIPT.get(lang.split("-")[0].lower()) if lang else None
    if declared and share and share.get(declared, 0) < 0.5:
        dominant = next(iter(share))
        lang_findings.append({"rule": "declared_language_mismatch", "severity": "medium", "confidence": "medium",
                              "description": f"The page declares lang=\"{lang}\" ({declared} script) but most letters are {dominant}. Screen readers may mispronounce the content.",
                              "evidence": f"script share: {share}", "wcag": WCAG["lang"]})
    others = [k for k, v in share.items() if v >= 0.1 and k != declared]
    if others:
        manual.append(ManualItem("Mark language changes inside the page", "Mixed-script text was detected but a tool cannot tell which passages need lang attributes.",
                                 f"Check that passages in {', '.join(others)} are wrapped with the matching lang attribute.", f"script share: {share}"))
    words = re.findall(r"\b[\w']+\b", text)
    sentences = [s for s in re.split(r"[.!?।]+\s", text) if len(s.split()) >= 3]
    avg = round(len(words) / max(len(sentences), 1), 1) if share.get("Latin", 0) > 0.8 and sentences else None
    if avg and avg > 25:
        lang_findings.append({"rule": "long_sentences", "severity": "low", "confidence": "low",
                              "description": f"Average sentence length is about {avg} words, which can be hard to follow (plain-language guidance suggests ~15–20).",
                              "evidence": f"{len(words)} words, {len(sentences)} sentences", "wcag": "WCAG 3.1.5 (AAA)"})

    manual += [
        ManualItem("Colour contrast", "Needs rendered colours/backgrounds and images; not reliably derivable from markup.", "Run a contrast checker on text, buttons and focus indicators (4.5:1 for body text)."),
        ManualItem("Screen-reader walkthrough", "Announcement order and clarity can only be judged by listening.", "Test key tasks with NVDA (Windows), VoiceOver or TalkBack, with the screen off."),
        ManualItem("Keyboard-only walkthrough and visible focus", "Dynamic behaviour (menus, dialogs, focus traps) is not visible in static HTML.", "Complete the main task using Tab, Shift+Tab, Enter and Esc only."),
        ManualItem("Media captions / transcripts", "Presence of captions can't be verified from static markup.", "Check that videos have captions and audio has transcripts."),
        ManualItem("Quality of alt text and link text", "Tools detect missing text, not whether it is meaningful.", "Read alt texts and link texts aloud out of context."),
    ]

    findings = sorted(f.values(), key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x.severity], -x.count))
    return {"target": url, "target_type": "web_page", "automated_findings": [asdict(x) for x in findings],
            "language_findings": lang_findings, "manual_review_items": [asdict(m) for m in manual],
            "stats": {"images": len(imgs), "headings": len(levels), "links": len(soup.find_all("a", href=True)),
                      "form_controls": len(soup.find_all(["input", "select", "textarea"])), "declared_lang": lang or None,
                      "script_share": share}}


def analyze_pdf(data: bytes, name: str) -> dict:
    from pypdf import PdfReader
    reader = PdfReader(BytesIO(data))
    root = reader.trailer["/Root"]
    f: dict[str, A11yFinding] = {}
    n_pages = len(reader.pages)

    mark = root.get("/MarkInfo")
    tagged = bool(mark and mark.get_object().get("/Marked")) and "/StructTreeRoot" in root
    if not tagged:
        _add(f, "pdf_untagged", "high", "The PDF is not tagged, so screen readers cannot determine headings, lists, tables or reading order.", "no /StructTreeRoot or /MarkInfo /Marked", WCAG["pdf"])
    if not root.get("/Lang"):
        _add(f, "pdf_no_language", "medium", "The PDF does not declare a document language.", "no /Lang in catalog", WCAG["lang"])
    title = (reader.metadata.title if reader.metadata else None) or ""
    if not title.strip():
        _add(f, "pdf_no_title", "medium", "The PDF has no document title in its metadata (screen readers fall back to the file name).", "metadata /Title empty", WCAG["title"])
    elif root.get("/ViewerPreferences") is None or not root["/ViewerPreferences"].get_object().get("/DisplayDocTitle"):
        _add(f, "pdf_title_not_displayed", "low", "The title exists but the PDF is not set to display it in the title bar.", "/DisplayDocTitle not set", WCAG["title"])

    empty_pages = [i + 1 for i, p in enumerate(reader.pages) if not (p.extract_text() or "").strip()]
    text_pages = n_pages - len(empty_pages)
    if empty_pages:
        sev = "high" if len(empty_pages) == n_pages else "medium"
        _add(f, "pdf_no_text_layer", sev, "Some pages have no extractable text (likely scanned images), which screen readers cannot read.", f"pages without text: {empty_pages[:20]}", WCAG["pdf"])
        f["pdf_no_text_layer"].count = len(empty_pages)
    if n_pages > 10 and not reader.outline:
        _add(f, "pdf_no_bookmarks", "low", "A document of more than 10 pages has no bookmarks for navigation.", f"{n_pages} pages, no outline", "WCAG 2.4.5")
    if "/AcroForm" in root:
        manual_form = True
    else:
        manual_form = False

    sample = " ".join((reader.pages[i].extract_text() or "") for i in range(min(n_pages, 5)))
    share = script_share(sample)
    manual = [
        ManualItem("Reading order of tagged content", "Tag order can only be judged by a screen reader or Acrobat's Reading Order tool.", "Open the PDF with NVDA/Acrobat 'Read Out Loud' and confirm logical order."),
        ManualItem("Alt text for figures and complex tables", "The checker does not evaluate figure tags or whether alternate text is meaningful.", "Use Acrobat's Accessibility Checker and review each figure."),
        ManualItem("Colour contrast of text and charts", "Not derivable from PDF structure.", "Check contrast in the source document."),
    ]
    if manual_form:
        manual.append(ManualItem("Form field labels and tab order", "The PDF contains an interactive form; field labels need testing.", "Tab through every field with a screen reader running."))
    if share and len([k for k, v in share.items() if v >= 0.1]) > 1:
        manual.append(ManualItem("Language changes within the document", "Mixed-script text detected.", "Ensure each passage has the right language tag.", f"script share: {share}"))
    findings = sorted(f.values(), key=lambda x: ({"high": 0, "medium": 1, "low": 2}[x.severity], -x.count))
    return {"target": name, "target_type": "pdf", "automated_findings": [asdict(x) for x in findings], "language_findings": [],
            "manual_review_items": [asdict(m) for m in manual],
            "stats": {"pages": n_pages, "pages_with_text": text_pages, "tagged": tagged, "declared_lang": str(root.get("/Lang") or "") or None,
                      "script_share": share}}


def summarize(result: dict) -> dict:
    all_f = result["automated_findings"] + result["language_findings"]
    counts = {s: sum(f.get("count", 1) if "count" in f else 1 for f in all_f if f["severity"] == s) for s in ("high", "medium", "low")}
    issues = len(all_f)
    result["counts"] = {**counts, "issue_types": issues, "manual_items": len(result["manual_review_items"])}
    result["summary"] = (f"Automated checks found {issues} issue type(s) ({counts['high']} high, {counts['medium']} medium, {counts['low']} low occurrences). "
                         f"{len(result['manual_review_items'])} further checks need manual testing. Passing the automated checks does not mean the content is fully accessible.")
    result["limitations"] = [
        "Automated tools detect only a portion of accessibility problems; manual testing with assistive technology is required.",
        "Pages that build their content with JavaScript may be only partly analysed.",
        "Findings reference WCAG 2.1 success criteria as guidance, not as a legal compliance verdict.",
    ]
    return result
