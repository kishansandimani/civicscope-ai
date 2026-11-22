"""Shared Gemini client (REST). One place for auth, timeouts, retries, model fallback, limits and JSON parsing.

The HTTP call is injectable (`sender`) so the retry / fallback logic is unit-tested without a network."""
import asyncio
import json
import re
from typing import Awaitable, Callable

from app.core.config import get_settings

API = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
RETRY_STATUS = {429, 500, 502, 503, 504}


class AIError(Exception):
    """User-safe description of why the AI step failed."""


class SendTimeout(Exception):
    pass


class SendFailed(Exception):
    pass


Sender = Callable[[str, dict, dict, float], Awaitable[tuple[int, dict | None]]]


async def httpx_sender(url: str, headers: dict, body: dict, timeout: float) -> tuple[int, dict | None]:
    import httpx
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=headers, json=body)
    except httpx.TimeoutException:
        raise SendTimeout()
    except httpx.HTTPError:
        raise SendFailed()
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, None


class GeminiService:
    # Newer Gemini models "think" before answering and thinking tokens count against maxOutputTokens, so a short budget can come
    # back empty or cut off. We add headroom; the visible answer length is still controlled by the prompt.
    THINKING_HEADROOM = 4096

    def __init__(self, api_key: str, model: str, fallback_model: str = "", timeout: float = 60.0, max_retries: int = 3,
                 max_prompt_chars: int = 60_000, concurrency: int = 3, sender: Sender = httpx_sender, thinking_level: str = "low",
                 sleep: Callable[[float], Awaitable] = asyncio.sleep):
        self.api_key, self.model = api_key, model
        self.models = [m for m in dict.fromkeys([model, fallback_model]) if m]
        self.timeout, self.max_retries, self.max_prompt_chars = timeout, max_retries, max_prompt_chars
        self._sem = asyncio.Semaphore(concurrency)
        self._send, self._sleep = sender, sleep
        self.thinking_level = thinking_level
        self.requests_made = 0
        self.last_model_used: str | None = None

    async def generate_json(self, system: str, prompt: str, *, max_output_tokens: int = 4096, temperature: float = 0.1) -> dict:
        if len(prompt) + len(system) > self.max_prompt_chars:
            raise AIError("The content is too large for a single AI request. Try fewer or smaller sources.")
        headers = {"x-goog-api-key": self.api_key, "Content-Type": "application/json"}
        last = "AI service unavailable."
        async with self._sem:
            for model in self.models:
                gen = {"responseMimeType": "application/json", "maxOutputTokens": max_output_tokens + self.THINKING_HEADROOM}
                is_g3 = model.startswith("gemini-3")
                if not is_g3:                                   # Google recommends the default temperature for Gemini 3 models
                    gen["temperature"] = temperature
                if is_g3 and self.thinking_level:               # extraction tasks do not need deep reasoning; keeps answers fast
                    gen["thinkingConfig"] = {"thinkingLevel": self.thinking_level}
                body = {"systemInstruction": {"parts": [{"text": system}]},
                        "contents": [{"role": "user", "parts": [{"text": prompt}]}], "generationConfig": gen}
                delay = 1.0
                for attempt in range(self.max_retries):
                    self.requests_made += 1
                    try:
                        status, data = await self._send(API.format(model=model), headers, body, self.timeout)
                    except SendTimeout:
                        last = "The AI service timed out."
                    except SendFailed:
                        last = "Could not reach the AI service."
                    else:
                        if status == 200:
                            self.last_model_used = model
                            return self._parse(data or {})
                        if status == 404:                       # model name not available for this key: try the fallback model
                            last = f"The AI model “{model}” is not available. Check GEMINI_MODEL."
                            break
                        if status in RETRY_STATUS:
                            last = "The AI service is busy. Please retry shortly."
                        elif status == 400 and "thinkingConfig" in gen:   # this model rejects the thinking setting: retry once without it
                            del gen["thinkingConfig"]
                            continue
                        elif status in (400, 401, 403):
                            raise AIError("The AI service rejected the request. Check the server's Gemini API key and model name.")
                        else:
                            raise AIError(f"The AI service returned an unexpected error ({status}).")
                    if attempt < self.max_retries - 1:
                        await self._sleep(delay); delay *= 2
        raise AIError(last)

    @staticmethod
    def _parse(data: dict) -> dict:
        if data.get("promptFeedback", {}).get("blockReason"):
            raise AIError("The AI service declined to process this content.")
        cands = data.get("candidates") or []
        if not cands:
            raise AIError("The AI service returned no answer.")
        cand = cands[0]
        text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
        if cand.get("finishReason") == "MAX_TOKENS":
            raise AIError("The AI answer was cut off. Try a smaller source.")
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            raise AIError("The AI answer was not valid structured data.")
        if not isinstance(parsed, dict):
            raise AIError("The AI answer had an unexpected shape.")
        return parsed


def get_gemini() -> GeminiService | None:
    s = get_settings()
    return GeminiService(s.gemini_api_key, s.gemini_model, s.gemini_fallback_model, timeout=s.gemini_timeout) if s.gemini_configured else None