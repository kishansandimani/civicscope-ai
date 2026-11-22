from uuid import UUID
from pydantic import BaseModel, Field


class RuleStressRequest(BaseModel):
    source_id: UUID
    scenario: str = Field(min_length=10, max_length=1500)


class PromiseTraceRequest(BaseModel):
    source_ids: list[UUID] = Field(min_length=1, max_length=5)
