"""Generate real module outputs (using the offline fakes) so the frontend renderer/CSV tests run on true backend shapes.
Run from backend/:  python tests/make_samples.py"""
import asyncio, json, os, sys
sys.path.insert(0, "."); sys.path.insert(0, "tests")
from datetime import date
import test_accessshadow as ta, test_civicprobe as tc, test_infoconflict as ti, test_promisetrace as tp, test_rulestress as tr
from app.services.accessshadow import analyze_html, summarize
from app.services.civicprobe import analyze_site
from app.services.infoconflict import compare_sources
from app.services.promisetrace import trace_commitments
from app.services.rulestress import stress_test

out = {
    "civicprobe": asyncio.run(analyze_site("https://welfare.gov.in/", tc.FakeFetcher(), tc.FakeGemini(), max_pages=5, today=tc.TODAY)).to_dict(),
    "infoconflict": asyncio.run(compare_sources(ti.G(), [ti.A, ti.B], "scholarship")),
    "accessshadow": summarize(analyze_html(ta.BAD, "https://x.gov.in/")),
    "rulestress": asyncio.run(stress_test(tr.G({"verdict": "does_not_apply", "answer": "Below the age.", "confidence": "high",
        "conditions": [{"condition": "Age", "status": "not_met", "evidence": "aged 60 years or above is eligible", "chunk": "C1"}],
        "ambiguities": [], "missing_information": ["Domicile"]}), tr.DOC, "I am 58 and want the pension")),
    "promisetrace": asyncio.run(trace_commitments(tp.G(), [tp.S1, tp.S2], today=date(2026, 11, 18))),
}
dest = os.path.join("..", "frontend", "tests", "samples.json")
json.dump(out, open(dest, "w", encoding="utf8"), ensure_ascii=False)
print("wrote", dest)
