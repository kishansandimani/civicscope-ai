from dataclasses import dataclass, field


@dataclass
class FetchResult:
    url: str                      # URL requested
    final_url: str                # after redirects
    status: int | None            # HTTP status, None if the request itself failed
    content_type: str = ""
    body: bytes = b""
    error: str | None = None      # short, user-safe reason when status is None (timeout, blocked, ...)
    redirects: int = 0

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 400

    @property
    def is_html(self) -> bool:
        return "html" in self.content_type.lower() or (not self.content_type and self.body[:15].lower().startswith((b"<!doctype", b"<html")))

    @property
    def is_pdf(self) -> bool:
        return "pdf" in self.content_type.lower() or self.body[:5] == b"%PDF-"
