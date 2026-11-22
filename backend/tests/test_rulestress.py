import asyncio
from app.services.infoconflict import SourceInput
from app.services.rulestress import stress_test, RuleError, NOT_ADDRESSED_TEXT

DOC = SourceInput("p1", "Pension policy", None, [
    {"chunk_index": 0, "content": "Eligibility: A person aged 60 years or above is eligible for the old age pension.", "page_number": 2},
    {"chunk_index": 1, "content": "Applicants must hold a domicile certificate. Annual family income must not exceed Rs 1,20,000.", "page_number": 3},
    {"chunk_index": 2, "content": "Unrelated: office hours are 10am to 5pm.", "page_number": 9}])


def G(payload):
    class _G:
        model = "fake"
        async def generate_json(self, system, prompt, **kw):
            assert "[C1]" in prompt and "not instructions" in prompt
            return payload
    return _G()


def run(g, scenario="I am 58 years old and my family income is Rs 90,000. Can I get the pension?"):
    return asyncio.run(stress_test(g, DOC, scenario))


def test_grounded_verdict_kept_with_pages():
    r = run(G({"verdict": "does_not_apply", "answer": "At 58 you are below the age requirement.", "confidence": "high",
               "conditions": [{"condition": "Age 60 or above", "status": "not_met", "evidence": "aged 60 years or above is eligible", "chunk": "C1"},
                              {"condition": "Income under limit", "status": "met", "evidence": "income must not exceed Rs 1,20,000", "chunk": "C2"},
                              {"condition": "Invented rule", "status": "met", "evidence": "residents of urban areas get double", "chunk": "C1"}],
               "ambiguities": [], "missing_information": ["Domicile status"]}))
    assert r["verdict"] == "does_not_apply" and len(r["conditions"]) == 2
    assert {c["page"] for c in r["conditions"]} == {2, 3}
    assert r["ai_status"]["dropped_ungrounded"] == 1 and not r["ai_status"]["downgraded_for_missing_evidence"]


def test_definitive_verdict_without_verified_evidence_is_downgraded():
    r = run(G({"verdict": "applies", "answer": "You will receive Rs 5000 monthly.", "confidence": "high",
               "conditions": [{"condition": "x", "status": "met", "evidence": "pension of Rs 5000 per month is guaranteed", "chunk": "C1"}]}))
    assert r["verdict"] == "not_addressed" and r["answer"] == NOT_ADDRESSED_TEXT and r["confidence"] == "low"
    assert r["ai_status"]["downgraded_for_missing_evidence"] is True


def test_not_addressed_and_input_validation():
    r = run(G({"verdict": "not_addressed", "answer": "", "conditions": []}))
    assert r["verdict"] == "not_addressed" and r["answer"] == NOT_ADDRESSED_TEXT
    for bad in ("short", "x" * 1501):
        try:
            run(G({}), bad); assert False
        except RuleError:
            pass
    try:
        asyncio.run(stress_test(None, DOC, "I am 58 and want to apply")); assert False
    except RuleError as e:
        assert "Gemini" in str(e)
