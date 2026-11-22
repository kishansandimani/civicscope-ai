import asyncio
from app.services.voice import answer_question, translate_text, VoiceError, NO_DATA

R = [{"id": "r1", "module": "civicprobe", "title": "Audit of welfare.gov.in", "summary": "Found 2 issues.",
      "body": {"findings": [{"severity": "high", "description": "Link returns HTTP 404.", "url": "https://welfare.gov.in/gone"}]}}]


class G:
    model = "fake"
    def __init__(self, payload): self.payload = payload
    async def generate_json(self, system, prompt, **kw):
        assert "R1: Audit of welfare.gov.in" in prompt or "Translate" in prompt
        return self.payload


def test_no_reports_is_deterministic_and_localised():
    for lang in ("en", "hi", "kn"):
        r = asyncio.run(answer_question(None, "what did you find", lang, []))
        assert r["answer"] == NO_DATA[lang] and r["grounded"] is False


def test_references_must_exist():
    r = asyncio.run(answer_question(G({"answer": "One broken link was found.", "references": ["R1", "R9"]}), "any broken links?", "en", R))
    assert [x["id"] for x in r["references"]] == ["r1"] and r["grounded"]


def test_errors_are_user_safe():
    for call in (lambda: answer_question(None, "hello there", "en", R), lambda: translate_text(None, "hi", "kn"),
                 lambda: translate_text(G({}), "text", "fr"), lambda: answer_question(G({"answer": ""}), "hello there", "en", R)):
        try:
            asyncio.run(call()); assert False
        except VoiceError:
            pass
    assert asyncio.run(translate_text(G({"translation": "ನಮಸ್ಕಾರ"}), "Hello", "kn")) == "ನಮಸ್ಕಾರ"
