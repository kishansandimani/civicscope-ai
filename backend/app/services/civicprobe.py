"""CivicProbe — government website auditor.

Deterministic checks (broken links, stale dates, HTTPS, missing titles) are computed from real fetched pages.
The AI step looks for softer problems (outdated wording, missing instructions) and every AI finding must quote
evidence that really appears in the fetched page, otherwise it is discarded.
"""
import asyncio
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from urllib.parse import urlsplit

from app.services.extract import ParsedPage, decode_body, parse_html
from app.services.grounding import evidence_in_text
from app.services.injection import SYSTEM_GUARD, new_boundary, scan, wrap_untrusted

SEVERITY_WEIGHT = {"critical": 20, "high": 10, "medium": 4, "low": 1}
SEVERITIES = tuple(SEVERITY_WEIGHT)
NON_HTML_EXT = (".pdf", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp", ".zip", ".rar", ".doc", ".docx",
                ".xls", ".xlsx", ".ppt", ".pptx", ".mp3", ".mp4", ".avi", ".csv", ".xml", ".json", ".ico", ".css", ".js")
AI_FINDING_TYPES = {"outdated_info", "missing_instructions", "unclear_contact", "other"}


class ProbeError(Exception):
    """Raised with a user-safe message when the audit cannot run at all."""


@dataclass
class Finding:
    type: str
    severity: str
    description: str
    url: str
    evidence: str
    confidence: str            # high | medium | low
    origin: str                # automated | ai
    found_on: list[str] = field(default_factory=list)


@dataclass
class ProbeResult:
    target_url: str
    pages_scanned: int
    links_checked: int
    broken_links: int
    health_score: int
    findings: list[Finding]
    summary: str
    ai_status: dict
    limitations: list[str]
    score_method: str = "Heuristic: 100 minus weighted findings (critical 20, high 10, medium 4, low 1), floor 0. Not an official rating."

    def to_dict(self) -> dict:
        d = asdict(self)
        return d


# ---------------------------------------------------------------- dates
_MONTHS = r"(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DATE_RE = re.compile(
    rf"(\d{{1,2}}(?:st|nd|rd|th)?[\s/\-.]+{_MONTHS}[\s/\-.,]+\d{{4}}"
    rf"|{_MONTHS}\.?\s+\d{{1,2}}(?:st|nd|rd|th)?,?\s+\d{{4}}"
    rf"|\d{{1,2}}[/\-.]\d{{1,2}}[/\-.]\d{{4}}"
    rf"|\d{{4}}-\d{{2}}-\d{{2}})", re.I)
UPDATED_RE = re.compile(r"(last\s+(?:updated|modified|reviewed)|updated\s+on|as\s+(?:on|of)|page\s+last\s+updated)\s*[:\-]?\s*", re.I)
DEADLINE_RE = re.compile(r"(last\s+date|closing\s+date|deadline|due\s+date|apply\s+(?:by|before|on or before)|last\s+date\s+of\s+submission)[^.\n]{0,60}?", re.I)


def parse_date(s: str) -> date | None:
    s = re.sub(r"(?<=\d)(st|nd|rd|th)\b", "", s.strip(), flags=re.I)
    s = re.sub(r"\bsept\b", "sep", s, flags=re.I)
    s = re.sub(r"[,.]", " ", s)
    s = re.sub(r"[\s/\-]+", " ", s).strip()
    for fmt in ("%d %B %Y", "%d %b %Y", "%B %d %Y", "%b %d %Y", "%d %m %Y", "%Y %m %d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def dated_mentions(text: str, marker: re.Pattern, window: int = 90):
    """Yield (date, snippet) for dates that directly follow a marker phrase such as 'Last updated'."""
    for m in marker.finditer(text):
        tail = text[m.end(): m.end() + window]
        d = DATE_RE.match(tail.lstrip()) or DATE_RE.search(tail[:60])
        if d:
            parsed = parse_date(d.group(1))
            if parsed and 1990 <= parsed.year <= 2100:
                snippet = text[m.start(): m.end() + tail.find(d.group(1)) + len(d.group(1))] if d else ""
                yield parsed, re.sub(r"\s+", " ", snippet).strip()


def date_findings(page: ParsedPage, today: date) -> list[Finding]:
    out: list[Finding] = []
    updates = list(dated_mentions(page.text, UPDATED_RE))
    if updates:
        newest, snippet = max(updates, key=lambda x: x[0])
        age = today - newest
        if age > timedelta(days=730):
            out.append(Finding("stale_page_date", "medium" if age > timedelta(days=1460) else "low",
                               f"The page states it was last updated on {newest.isoformat()}, about {age.days // 365} year(s) ago. "
                               "The information may be outdated (the page may also simply not display newer edits).",
                               page.url, snippet, "low", "automated"))
    seen = set()
    for d, snippet in dated_mentions(page.text, DEADLINE_RE, window=140):
        if d < today - timedelta(days=30) and snippet not in seen:
            seen.add(snippet)
            out.append(Finding("expired_deadline_still_listed", "medium",
                               f"A deadline of {d.isoformat()} is still shown on this page and appears to have passed. "
                               "Check whether the page is an archive or needs updating.",
                               page.url, snippet, "medium", "automated"))
    return out


# ---------------------------------------------------------------- crawl helpers
def _host(url: str) -> str:
    h = (urlsplit(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


def _is_internal(url: str, root_host: str) -> bool:
    return _host(url) == root_host


def _crawlable(url: str) -> bool:
    return not urlsplit(url).path.lower().endswith(NON_HTML_EXT)


def classify_link(status: int | None, error: str | None, internal: bool) -> tuple[str, str, str, str] | None:
    """Return (type, severity, confidence, explanation) or None when the link is fine."""
    if status is None:
        if error and error.startswith("blocked"):
            return None  # we refused to fetch (private network); not evidence the link is broken
        return ("unreachable_link", "medium", "medium", f"The link could not be reached ({error or 'unknown error'}); it may be down or blocking automated checks.")
    if status in (404, 410):
        return ("broken_link", "high" if internal else "medium", "high", f"The link returns HTTP {status} (page not found).")
    if 500 <= status < 600:
        return ("server_error_link", "medium", "medium", f"The link returns HTTP {status}; this may be temporary.")
    if status in (401, 403, 429):
        return ("unverifiable_link", "low", "low", f"The server answered HTTP {status}, so the link could not be verified automatically. Check manually.")
    if status >= 400:
        return ("broken_link", "medium", "medium", f"The link returns HTTP {status}.")
    return None


def compute_score(findings: list[Finding]) -> int:
    return max(0, 100 - sum(SEVERITY_WEIGHT.get(f.severity, 0) for f in findings))


# ---------------------------------------------------------------- AI step
AI_PROMPT = """Today's date is {today}.
You are auditing pages of a government website for citizen transparency.
Look ONLY for these problem types in the page text below:
- outdated_info: wording that is clearly out of date (e.g. refers to a past year as upcoming, expired schemes, old officials) 
- missing_instructions: a service/form/scheme is mentioned but the page gives no steps, eligibility, documents, fees, or deadline a citizen would need
- unclear_contact: citizens are told to contact someone but no way to do so is given
- other: any other clear problem for a citizen

Rules:
- Report at most {max_findings} findings; fewer is fine. Report nothing if you are not sure.
- "evidence" MUST be an exact quote (max 200 characters) copied from that page. For missing_instructions/unclear_contact quote the sentence that mentions the service or contact.
- "url" MUST be one of the page URLs given.
- confidence is high only when the text itself clearly shows the problem. Do not guess.
Return JSON: {{"findings": [{{"type": "...", "severity": "low|medium|high", "description": "...", "url": "...", "evidence": "...", "confidence": "high|medium|low"}}]}}

{pages}"""


async def ai_findings(gemini, pages: list[ParsedPage], today: date, max_pages: int = 5, max_findings: int = 8):
    status = {"ran": False, "model": getattr(gemini, "model", None), "dropped_ungrounded": 0,
              "injection_warnings": [], "error": None, "pages_sent": 0}
    chosen = [p for p in pages if len(p.text) > 200][:max_pages]
    if not chosen:
        status["error"] = "No page had enough text for AI review."
        return [], status
    boundary = new_boundary()
    blocks = []
    for p in chosen:
        hits = scan(p.text)
        if hits:
            status["injection_warnings"].append({"url": p.url, "snippet": hits[0]})
        blocks.append(wrap_untrusted(p.url, p.text, boundary, max_chars=5000))
    status["pages_sent"] = len(chosen)
    try:
        data = await gemini.generate_json(SYSTEM_GUARD, AI_PROMPT.format(today=today.isoformat(), max_findings=max_findings,
                                                                          pages="\n\n".join(blocks)))
    except Exception as e:  # AIError or anything unexpected: degrade honestly, keep automated results
        status["error"] = str(e) if e.__class__.__name__ == "AIError" else "The AI review step failed."
        return [], status
    status["ran"] = True
    by_url = {p.url: p for p in chosen}
    out: list[Finding] = []
    for raw in (data.get("findings") or [])[:max_findings]:
        if not isinstance(raw, dict):
            continue
        url, evidence = str(raw.get("url", "")), str(raw.get("evidence", ""))
        ftype = raw.get("type") if raw.get("type") in AI_FINDING_TYPES else "other"
        sev = raw.get("severity") if raw.get("severity") in ("low", "medium", "high") else "low"
        conf = raw.get("confidence") if raw.get("confidence") in ("high", "medium", "low") else "low"
        page = by_url.get(url)
        if page is None or not evidence_in_text(evidence, page.text):
            status["dropped_ungrounded"] += 1
            continue
        out.append(Finding(ftype, sev, str(raw.get("description", ""))[:500], url, evidence[:300], conf, "ai"))
    return out, status


# ---------------------------------------------------------------- main entry
async def analyze_site(url: str, fetcher, gemini=None, max_pages: int = 8, max_links: int = 60,
                       today: date | None = None) -> ProbeResult:
    today = today or date.today()
    max_pages = max(1, min(max_pages, 25))
    start = await fetcher.fetch(url)
    if start.status is None:
        raise ProbeError(f"Could not open that website ({start.error}).")
    if not start.ok or not start.is_html:
        raise ProbeError(f"The address did not return a web page (HTTP {start.status}, {start.content_type or 'unknown type'}).")

    root_host = _host(start.final_url)
    findings: list[Finding] = []
    pages: dict[str, ParsedPage] = {}
    queue = [start.final_url]
    visited = {start.final_url}
    known: dict[str, object] = {}   # URL -> FetchResult for pages that failed while crawling
    sem = asyncio.Semaphore(4)

    async def load(u: str, first: bool = False):
        async with sem:
            res = start if first else await fetcher.fetch(u)
        return u, res

    while queue and len(pages) < max_pages:
        batch, queue = queue[: max_pages - len(pages)], queue[max_pages - len(pages):]
        for u, res in await asyncio.gather(*[load(b, first=(b == start.final_url and not pages)) for b in batch]):
            if res.status is None or res.status >= 400:
                known[u] = res          # reported once, with "found on" pages, in the link phase below
                continue
            if not res.is_html:
                continue
            page = parse_html(decode_body(res.body, res.content_type), res.final_url)
            pages[res.final_url] = page
            for link, _ in page.links:
                if _is_internal(link, root_host) and _crawlable(link) and link not in visited and len(visited) < max_pages * 4:
                    visited.add(link); queue.append(link)

    # --- per-page deterministic checks
    for p in pages.values():
        if p.url.startswith("http://"):
            findings.append(Finding("insecure_http", "medium", "The page is served over unencrypted HTTP, so visitors' data and the page itself can be altered in transit.",
                                    p.url, p.url, "high", "automated"))
        if not p.title.strip():
            findings.append(Finding("missing_page_title", "low", "The page has no <title>, which makes it hard to identify in browser tabs and search results.",
                                    p.url, "(no <title> element found)", "high", "automated"))
        findings.extend(date_findings(p, today))
        hits = scan(p.text)
        if hits:
            findings.append(Finding("ai_instruction_text", "low", "The page contains text that looks like instructions aimed at AI systems. It was ignored by this audit.",
                                    p.url, hits[0], "low", "automated"))

    # --- link checking
    link_sources: dict[str, list[str]] = {}
    for p in pages.values():
        for link, _ in p.links:
            link_sources.setdefault(link, []).append(p.url)
    to_check = [l for l in link_sources if l not in pages][:max_links]
    lsem = asyncio.Semaphore(6)

    async def check(l: str):
        if l in known:
            return l, known[l]
        async with lsem:
            return l, await fetcher.check(l)

    broken = 0
    for l, res in await asyncio.gather(*[check(l) for l in to_check]):
        kind = classify_link(res.status, res.error, _is_internal(l, root_host))
        if kind:
            if kind[0] in ("broken_link", "unreachable_link", "server_error_link"):
                broken += 1
            findings.append(Finding(kind[0], kind[1], kind[3], l, f"HTTP {res.status}" if res.status else (res.error or ""),
                                    kind[2], "automated", found_on=link_sources[l][:5]))

    # --- AI step
    if gemini is None:
        ai_status = {"ran": False, "error": "AI review skipped: no Gemini API key is configured on the server.",
                     "dropped_ungrounded": 0, "injection_warnings": [], "model": None, "pages_sent": 0}
    else:
        ai_f, ai_status = await ai_findings(gemini, list(pages.values()), today)
        findings.extend(ai_f)

    findings.sort(key=lambda f: (-SEVERITY_WEIGHT.get(f.severity, 0), f.type, f.url))
    sev_counts = {s: sum(1 for f in findings if f.severity == s) for s in SEVERITIES}
    summary = (f"Scanned {len(pages)} page(s) and checked {len(to_check)} link(s) on {root_host}. "
               f"Found {len(findings)} issue(s): "
               + ", ".join(f"{n} {s}" for s, n in sev_counts.items() if n) + "." if findings else
               f"Scanned {len(pages)} page(s) and checked {len(to_check)} link(s) on {root_host}. No issues were detected by the checks that were run.")
    limitations = [
        f"Only the first {len(pages)} page(s) reachable from the address were scanned (limit {max_pages}); other pages were not audited.",
        f"At most {max_links} distinct links were checked.",
        "Pages that need JavaScript to show their content may be only partly visible to this audit.",
        "Links that block automated requests (HTTP 401/403/429) are reported as unverifiable, not broken.",
        "'Outdated' findings are indications based on dates and wording on the page, not proof the information is wrong.",
    ]
    return ProbeResult(url, len(pages), len(to_check), broken, compute_score(findings), findings, summary, ai_status, limitations)
