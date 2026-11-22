from uuid import UUID
from pydantic import BaseModel, Field


class CompareRequest(BaseModel):
    source_ids: list[UUID] = Field(min_length=2, max_length=5)
    topic: str | None = Field(default=None, max_length=200)
