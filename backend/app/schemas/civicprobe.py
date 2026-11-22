from typing import Literal
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    url: str = Field(min_length=3, max_length=2048, description="Government website address, e.g. https://example.gov.in")
    max_pages: int = Field(default=8, ge=1, le=25)


class FindingOut(BaseModel):
    type: str
    severity: Literal["critical", "high", "medium", "low"]
    description: str
    url: str
    evidence: str
    confidence: Literal["high", "medium", "low"]
    origin: Literal["automated", "ai"]
    found_on: list[str] = []


class ProbeResultOut(BaseModel):
    target_url: str
    pages_scanned: int
    links_checked: int
    broken_links: int
    health_score: int
    findings: list[FindingOut]
    summary: str
    ai_status: dict
    limitations: list[str]
    score_method: str


class AnalyzeResponse(BaseModel):
    analysis_id: str
    report_id: str
    result: ProbeResultOut
