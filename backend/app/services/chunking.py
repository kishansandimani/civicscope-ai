"""Split extracted text into overlapping chunks that remember their page number (for citations)."""
import re
from dataclasses import dataclass


@dataclass
class Chunk:
    index: int
    content: str
    page_number: int | None
    heading: str | None
    token_estimate: int


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def _split_long(paragraph: str, target: int) -> list[str]:
    if len(paragraph) <= target:
        return [paragraph]
    sentences = re.split(r"(?<=[.!?।])\s+", paragraph)
    out, cur = [], ""
    for s in sentences:
        while len(s) > target:  # unbroken run: hard split
            if cur:
                out.append(cur); cur = ""
            out.append(s[:target]); s = s[target:]
        if len(cur) + len(s) + 1 > target and cur:
            out.append(cur); cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def chunk_pages(pages: list[tuple[int | None, str]], target: int = 1200, overlap: int = 150) -> list[Chunk]:
    chunks: list[Chunk] = []
    for page_no, text in pages:
        text = (text or "").strip()
        if not text:
            continue
        pieces: list[str] = []
        for para in re.split(r"\n\s*\n", text):
            para = re.sub(r"[ \t]+", " ", para).strip()
            if para:
                pieces.extend(_split_long(para, target))
        cur, heading = "", None
        for piece in pieces:
            if len(piece) < 90 and not piece.endswith((".", "।")) and not cur:
                heading = piece  # short line before body text: treat as a heading
            if cur and len(cur) + len(piece) + 2 > target:
                chunks.append(Chunk(len(chunks), cur, page_no, heading, estimate_tokens(cur)))
                tail = cur[-overlap:] if overlap else ""
                cur = f"{tail} {piece}".strip() if tail else piece
            else:
                cur = f"{cur}\n\n{piece}".strip() if cur else piece
        if cur:
            chunks.append(Chunk(len(chunks), cur, page_no, heading, estimate_tokens(cur)))
    return chunks
