"""Turn HTML / PDF bytes into text + structure. Parsing only; no network."""
import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urldefrag, urlsplit

from bs4 import BeautifulSoup

SKIP_SCHEMES = ("mailto:", "tel:", "javascript:", "data:", "sms:", "whatsapp:")


@dataclass
class ParsedPage:
    url: str
    title: str = ""
    lang: str | None = None
    text: str = ""
    headings: list[tuple[int, str]] = field(default_factory=list)
    links: list[tuple[str, str]] = field(default_factory=list)       # (absolute url, anchor text)
    images: list[tuple[str, str | None]] = field(default_factory=list)  # (src, alt or None if attribute missing)


def parse_html(html: str, base_url: str) -> ParsedPage:
    soup = BeautifulSoup(html or "", "lxml")
    page = ParsedPage(url=base_url)
    page.title = (soup.title.get_text(" ", strip=True) if soup.title else "")[:300]
    html_tag = soup.find("html")
    page.lang = (html_tag.get("lang") or None) if html_tag else None

    for h in soup.find_all(re.compile(r"^h[1-6]$")):
        t = h.get_text(" ", strip=True)
        if t:
            page.headings.append((int(h.name[1]), t[:300]))
    for img in soup.find_all("img"):
        page.images.append((img.get("src") or "", img.get("alt") if img.has_attr("alt") else None))

    seen = set()
    base_tag = soup.find("base", href=True)
    base = urljoin(base_url, base_tag["href"]) if base_tag else base_url
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        if not href or href.startswith("#") or href.lower().startswith(SKIP_SCHEMES):
            continue
        absolute, _ = urldefrag(urljoin(base, href))
        if urlsplit(absolute).scheme not in ("http", "https") or absolute in seen:
            continue
        seen.add(absolute)
        page.links.append((absolute, a.get_text(" ", strip=True)[:150]))

    for t in soup(["script", "style", "noscript", "template", "svg"]):
        t.decompose()
    text = soup.get_text("\n", strip=True)
    page.text = re.sub(r"\n{3,}", "\n\n", text)
    return page


def decode_body(body: bytes, content_type: str = "") -> str:
    m = re.search(r"charset=([\w\-]+)", content_type or "", re.I)
    for enc in ([m.group(1)] if m else []) + ["utf-8", "latin-1"]:
        try:
            return body.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return body.decode("utf-8", errors="replace")


def extract_pdf_pages(data: bytes, max_pages: int = 200) -> list[tuple[int, str]]:
    """Return [(page_number starting at 1, text)]. Scanned PDFs without a text layer return empty strings."""
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(stream=data, filetype="pdf")
        return [(i + 1, doc[i].get_text("text")) for i in range(min(len(doc), max_pages))]
    except ImportError:
        from io import BytesIO
        from pypdf import PdfReader
        reader = PdfReader(BytesIO(data))
        return [(i + 1, (reader.pages[i].extract_text() or "")) for i in range(min(len(reader.pages), max_pages))]
