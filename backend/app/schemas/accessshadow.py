from uuid import UUID
from pydantic import BaseModel, Field, model_validator


class AccessRequest(BaseModel):
    url: str | None = Field(default=None, min_length=3, max_length=2048)
    source_id: UUID | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if bool(self.url) == bool(self.source_id):
            raise ValueError("Provide either a website address or a source, not both.")
        return self
