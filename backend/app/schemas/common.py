from typing import Literal
from pydantic import BaseModel, Field


class ProfileOut(BaseModel):
    id: str
    email: str | None = None
    full_name: str | None = None
    designation: str | None = None
    organization: str | None = None
    preferred_language: str = "en"


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=120)
    designation: str | None = Field(default=None, max_length=120)
    organization: str | None = Field(default=None, max_length=160)
    preferred_language: Literal["en", "hi", "kn", "ta", "te", "bn"] | None = None


class SettingsUpdate(BaseModel):
    voice_enabled: bool | None = None
    voice_language: Literal["en", "hi", "kn"] | None = None
    speech_rate: float | None = Field(default=None, ge=0.5, le=2.0)
    speech_pitch: int | None = Field(default=None, ge=0, le=100)
    high_contrast: bool | None = None
    large_text: bool | None = None
    reduce_motion: bool | None = None
    notify_email: bool | None = None
    notify_in_app: bool | None = None
