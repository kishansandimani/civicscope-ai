"""Source ingestion: validate uploads, extract text, chunk, and persist (user-scoped client => RLS applies)."""
import hashlib
import re
import unicodedata
from dataclasses import dataclass

from app.services.chunking import Chunk, chunk_pages
from app.services.extract import decode_body, extract_pdf_pages, parse_html

ALLOWED_EXT = {".pdf": "pdf", ".txt": "document", ".html": "document", ".htm": "document"}
MIME_FOR = {".pdf": "application/pdf", ".txt": "text/plain", ".html": "text/html", ".htm": "text/html"}
MAX_CHUNKS_PER_SOURCE = 1500
MAX_SOURCES_PER_USER = 150


class IngestError(ValueError):
    """User-safe message."""


@dataclass
class Prepared:
    ext: str
    kind: str                 # pdf | document
    mime: str
    filename: str
    sha256: str
    pages: list[tuple[int | None, str]]
    page_count: int | None


def sanitize_filename(name: str) -> str:
    name = unicodedata.normalize("NFKC", name or "document").replace("\\", "/").split("/")[-1]
    stem, dot, ext = name.rpartition(".")
    stem = re.sub(r"[^\w\- ]", "_", stem or name, flags=re.UNICODE).strip(" _.")[:80] or "document"
    return f"{stem}.{ext.lower()}" if dot and ext.isalnum() else stem


def validate_and_prepare(filename: str, data: bytes, max_bytes: int) -> Prepared:
    if not data:
        raise IngestError("The file is empty.")
    if len(data) > max_bytes:
        raise IngestError(f"The file is larger than the {max_bytes // (1024 * 1024)} MB limit.")
    clean = sanitize_filename(filename)
    ext = "." + clean.rsplit(".", 1)[-1].lower() if "." in clean else ""
    if ext not in ALLOWED_EXT:
        raise IngestError("Only PDF, TXT and HTML files are supported.")
    sha = hashlib.sha256(data).hexdigest()

    if ext == ".pdf":
        if not data.startswith(b"%PDF-"):
            raise IngestError("That file is not a valid PDF.")
        try:
            pages = extract_pdf_pages(data)
        except Exception:
            raise IngestError("The PDF could not be read. It may be corrupted or password-protected.")
        if not any(t.strip() for _, t in pages):
            raise IngestError("This PDF has no readable text (it may be a scan). OCR is not supported yet.")
        return Prepared(ext, "pdf", MIME_FOR[ext], clean, sha, pages, len(pages))

    if b"\x00" in data[:4096]:
        raise IngestError("That file looks like binary data, not text.")
    text = decode_body(data)
    if ext in (".html", ".htm"):
        if "<" not in text:
            raise IngestError("That file does not look like HTML.")
        text = parse_html(text, "https://uploaded.local/").text
    if not text.strip():
        raise IngestError("The file contains no readable text.")
    return Prepared(ext, "document", MIME_FOR[ext], clean, sha, [(None, text)], None)


def clean_text(s: str) -> str:
    return s.replace("\x00", "")


def to_chunk_rows(chunks: list[Chunk], source_id: str, user_id: str) -> list[dict]:
    return [{"source_id": source_id, "user_id": user_id, "chunk_index": c.index, "content": clean_text(c.content),
             "page_number": c.page_number, "section_heading": clean_text(c.heading)[:200] if c.heading else None,
             "token_estimate": c.token_estimate} for c in chunks[:MAX_CHUNKS_PER_SOURCE]]


def persist_chunks(db, source_id: str, user_id: str, pages) -> int:
    rows = to_chunk_rows(chunk_pages(pages), source_id, user_id)
    for i in range(0, len(rows), 100):
        db.table("source_chunks").insert(rows[i:i + 100]).execute()
    return len(rows)


def load_chunks(db, source_id: str) -> list[dict]:
    return (db.table("source_chunks").select("chunk_index,content,page_number,section_heading")
            .eq("source_id", source_id).order("chunk_index").limit(MAX_CHUNKS_PER_SOURCE).execute().data)
