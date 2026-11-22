import asyncio
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.services.gemini import get_gemini
from app.services.voice import VoiceError, answer_question, translate_text

router = APIRouter(prefix="/api/voice", tags=["civicvoice"])
Lang = Literal["en", "hi", "kn"]


class AskRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    language: Lang = "en"


class TranslateRequest(BaseModel):
    text: str = Field(min_length=1, max_length=4000)
    target: Lang


@router.post("/ask")
@limiter.limit("20/minute")
async def ask(request: Request, body: AskRequest, user: CurrentUser = Depends(get_current_user)):
    reports = for_user(user.token).table("reports").select("id,module,title,summary,body").order("created_at", desc=True).limit(8).execute().data
    try:
        return await asyncio.wait_for(answer_question(get_gemini(), body.question, body.language, reports), 60)
    except VoiceError as e:
        raise HTTPException(422, str(e))
    except asyncio.TimeoutError:
        raise HTTPException(504, "The assistant took too long. Please try again.")


@router.post("/translate")
@limiter.limit("20/minute")
async def translate(request: Request, body: TranslateRequest, user: CurrentUser = Depends(get_current_user)):
    try:
        return {"translation": await asyncio.wait_for(translate_text(get_gemini(), body.text, body.target), 60)}
    except VoiceError as e:
        raise HTTPException(422, str(e))
    except asyncio.TimeoutError:
        raise HTTPException(504, "Translation took too long. Please try again.")
