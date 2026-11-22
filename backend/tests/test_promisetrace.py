import asyncio
from datetime import date
from app.services.infoconflict import SourceInput
from app.services.promisetrace import trace_commitments, TraceError

S1 = SourceInput("s1", "Budget speech", None, [{"chunk_index": 0, "page_number": 5, "content":
     "The government will deploy 8,000 electric buses across the city by 31 December 2025. A metro extension will be completed by 2024."}])
S2 = SourceInput("s2", "Progress report", None, [{"chunk_index": 0, "page_number": 2, "content":
     "As of 1 June 2025, 2,100 electric buses have been deployed and the programme remains on track."}])


class G:
    model = "fake"
    async def generate_json(self, system, prompt, **kw):
        return {"projects": [
            {"title": "Electric buses", "department": "Transport", "source": "S1", "commitment_quote": "will deploy 8,000 electric buses across the city by 31 December 2025",
             "announced_on": None, "target_date": "2025-12-31", "status": "on_track",
             "milestones": [{"title": "Reach 2,100 buses", "due_date": "2025-06-01", "status": "completed", "evidence": "2,100 electric buses have been deployed", "source": "S2"}],
             "progress_updates": [{"date": "2025-06-01", "description": "2,100 buses deployed; on track", "evidence": "the programme remains on track", "source": "S2"},
                                  {"date": "2025-07-01", "description": "fabricated", "evidence": "all buses were delivered early", "source": "S2"}]},
            {"title": "Metro extension", "department": None, "source": "S1", "commitment_quote": "A metro extension will be completed by 2024",
             "announced_on": None, "target_date": "2024-13-45", "status": "delayed", "milestones": [], "progress_updates": []},
            {"title": "Invented flyover", "source": "S1", "commitment_quote": "a flyover will open in March", "status": "on_track"},
        ]}


def test_trace_enforces_evidence_rules():
    r = asyncio.run(trace_commitments(G(), [S1, S2], today=date(2026, 11, 18)))
    titles = [p["title"] for p in r["projects"]]
    assert titles == ["Electric buses", "Metro extension"]            # invented flyover dropped
    bus, metro = r["projects"]
    assert bus["status"] == "on_track" and len(bus["progress_updates"]) == 1 and bus["progress_updates"][0]["page"] == 2
    assert bus["commitment"]["page"] == 5
    assert metro["status"] == "no_update_found"                          # 'delayed' with no evidence is refused
    assert "does not mean the commitment has failed" in metro["status_note"]
    assert metro["target_date"] is None                                  # impossible date dropped, not guessed
    assert [e["type"] for e in bus["timeline"]] == ["milestone", "update", "target"] or bus["timeline"][0]["date"] <= bus["timeline"][-1]["date"]
    assert r["ai_status"]["dropped_ungrounded"] == 2      # fabricated update + invented project


def test_past_due_without_update_is_a_prompt_to_check_not_a_failure():
    class G2(G):
        async def generate_json(self, *a, **k):
            return {"projects": [{"title": "Bridge", "source": "S1", "commitment_quote": "A metro extension will be completed by 2024",
                                  "target_date": "2024-12-31", "status": "unclear"}]}
    r = asyncio.run(trace_commitments(G2(), [S1], today=date(2026, 11, 18)))
    p = r["projects"][0]
    assert p["status"] == "no_update_found" and "has passed" in p["status_note"] and "check official channels" in p["status_note"]


def test_requires_ai_and_sources():
    for call in (lambda: trace_commitments(None, [S1]), lambda: trace_commitments(G(), [])):
        try:
            asyncio.run(call()); assert False
        except TraceError:
            pass
