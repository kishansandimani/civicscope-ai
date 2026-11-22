import asyncio
from app.services.infoconflict import SourceInput, compare_sources, ConflictError, select_text


def src(i, name, text, page=1):
    return SourceInput(i, name, None, [{"chunk_index": 0, "content": text, "page_number": page}])


A = src("a", "Dept website", "Scholarship applications close on 31 March 2025. Annual family income must be below Rs 2,50,000.", 1)
B = src("b", "Gazette notification", "Last date to apply for the scholarship is 30 April 2025. Family income limit is Rs 2,50,000 per year.", 4)


class G:
    model = "fake"
    async def generate_json(self, system, prompt, **kw):
        assert "S1: Dept website" in prompt and "never say which source is correct".lower() in prompt.lower().replace("NEVER say", "never say")
        return {"claims": [
            {"source": "S1", "field": "deadline", "value": "31 March 2025", "evidence": "Scholarship applications close on 31 March 2025"},
            {"source": "S2", "field": "deadline", "value": "30 April 2025", "evidence": "Last date to apply for the scholarship is 30 April 2025"},
            {"source": "S1", "field": "income_limit", "value": "Rs 2,50,000", "evidence": "income must be below Rs 2,50,000"},
            {"source": "S2", "field": "income_limit", "value": "Rs 2,50,000", "evidence": "Family income limit is Rs 2,50,000 per year"},
            {"source": "S2", "field": "benefit_amount", "value": "Rs 50,000", "evidence": "a one-time grant of Rs 50,000 is paid"},   # fabricated
        ], "conflicts": [
            {"field": "deadline", "severity": "low", "explanation": "The sources give different closing dates.",
             "claims": [{"source": "S1", "value": "31 March 2025", "evidence": "applications close on 31 March 2025"},
                        {"source": "S2", "value": "30 April 2025", "evidence": "Last date to apply for the scholarship is 30 April 2025"}]},
            {"field": "income_limit", "severity": "high", "explanation": "Fake conflict: same value worded the same.",
             "claims": [{"source": "S1", "value": "Rs 2,50,000", "evidence": "income must be below Rs 2,50,000"},
                        {"source": "S2", "value": "rs 2,50,000", "evidence": "Family income limit is Rs 2,50,000 per year"}]},
            {"field": "benefit_amount", "severity": "high", "explanation": "Invented.",
             "claims": [{"source": "S1", "value": "Rs 10,000", "evidence": "a grant of Rs 10,000"},
                        {"source": "S2", "value": "Rs 50,000", "evidence": "a one-time grant of Rs 50,000 is paid"}]},
        ]}


def test_conflicts_grounded_and_neutral():
    r = asyncio.run(compare_sources(G(), [A, B], "scholarship"))
    assert [c["field"] for c in r["conflicts"]] == ["deadline"]
    c = r["conflicts"][0]
    assert c["severity"] == "medium"                      # 'low' raised: deadlines affect citizens
    assert {x["page"] for x in c["claims"]} == {1, 4}     # real pages, not AI-supplied
    assert "cannot determine which source is correct" in c["resolution"]
    assert [a["field"] for a in r["agreements"]] == ["income_limit"]
    assert r["ai_status"]["dropped_ungrounded"] >= 3
    assert "benefit_amount" not in r["comparison"]        # fabricated claim never reaches the table


def test_needs_ai_and_two_sources():
    for call in (lambda: compare_sources(None, [A, B]), lambda: compare_sources(G(), [A])):
        try:
            asyncio.run(call()); assert False
        except ConflictError:
            pass


def test_select_text_samples_long_docs():
    chunks = [{"chunk_index": i, "content": ("filler text " * 40) if i != 7 else "The deadline to apply is 5 May.", "page_number": i + 1} for i in range(30)]
    text, truncated = select_text(SourceInput("x", "n", None, chunks), "deadline apply", 1500)
    assert truncated and "deadline to apply" in text and "[page 8]" in text
