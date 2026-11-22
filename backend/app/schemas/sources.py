from typing import Literal
from pydantic import BaseModel, Field


class UrlSourceRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2048)


class SourceOut(BaseModel):
    id: str
    kind: Literal["url", "pdf", "document"]
    name: str
    url: str | None = None
    status: str
    page_count: int | None = None
    size_bytes: int | None = None
    error_message: str | None = None
    created_at: str
