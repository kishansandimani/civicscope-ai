"""InfoConflict — compare several sources and surface contradictions, without ever deciding which is right.

AI proposes claims/conflicts; code then verifies every quoted claim against the real source text, attaches the
real page number, drops anything ungrounded, and only keeps conflicts that still have >=2 grounded sources with
genuinely different values.
"""
import re
from dataclasses import dataclass

from app.services.grounding import evidence_in_text, normalise
from app.services.injection import SYSTEM_GUARD, new_boundary, scan, wrap_untrusted
from app.services.retrieval import BM25

FIELDS = ["eligibility", "deadline", "benefit_amount", "documents_required", "age_limit", "income_limit",
          "application_process", "other"]
HIGH_IMPACT = {"deadline", "benefit_amount", "eligibility", "age_limit", "income_limit"}
DEFAULT_QUERY = "eligibility deadline last date benefit amount documents required age income apply how"
RESOLUTION_NOTE = ("CivicScope cannot determine which source is correct. Verify with the issuing department "
                   "(check the notification date and gazette/official order) before acting.")


class ConflictError(Exception):
    """User-safe message."""


@dataclass
class SourceInput:
    id: str
    name: str
    url: str | None
    chunks: list[dict]   # {chunk_index, content, page_number}


def full_text(src: SourceInput) -> str:
    return "\n\n".join(c["content"] for c in src.chunks)


def select_text(src: SourceInput, query: str, budget: int) -> tuple[str, bool]:
    """Whole document if it fits; otherwise the most relevant chunks (BM25), kept in document order."""
    if len(full_text(src)) <= budget:
        return full_text(src), False
    bm = BM25([c["content"] for c in src.chunks])
    picked, used = [], 0
    ranked = [i for i, _ in bm.search(query, k=len(src.chunks))] or list(range(len(src.chunks)))
    for i in ranked:
        n = len(src.chunks[i]["content"])
        if used + n > budget:
            continue
        picked.append(i); used += n
    parts = []
    for i in sorted(picked):
        pg = src.chunks[i].get("page_number")
        parts.append((f"[page {pg}] " if pg else "") + src.chunks[i]["content"])
    return "\n\n".join(parts), True


def locate(src: SourceInput, evidence: str) -> tuple[bool, int | None]:
    """(grounded?, page number of the first chunk containing the evidence)."""
    for c in src.chunks:
        if evidence_in_text(evidence, c["content"]):
            return True, c.get("page_number")
    return (evidence_in_text(evidence, full_text(src)), None)   # evidence spanning two chunks


PROMPT = """Compare how the sources below describe the SAME scheme/topic{topic_clause}.
Extract concrete claims for these fields: {fields}.
Then list CONFLICTS: places where two or more sources give different values for the same field.

Rules:
- Every claim and conflict-claim needs an "evidence" quote copied EXACTLY (max 200 chars) from that source.
- Use the source labels exactly as given (S1, S2, ...).
- A conflict needs claims from at least two different sources with genuinely different values. Different wording of the same value is NOT a conflict.
- Describe conflicts neutrally. NEVER say which source is correct or newer unless a source itself states its date; do not recommend one.
- If a source does not mention a field, do not invent a claim for it.
Return JSON:
{{"claims":[{{"source":"S1","field":"deadline","value":"...","evidence":"..."}}],
 "conflicts":[{{"field":"deadline","severity":"low|medium|high","explanation":"neutral description of the difference",
   "claims":[{{"source":"S1","value":"...","evidence":"..."}},{{"source":"S2","value":"...","evidence":"..."}}]}}]}}

{blocks}"""


async def compare_sources(gemini, sources: list[SourceInput], topic: str | None = None) -> dict:
    if gemini is None:
        raise ConflictError("InfoConflict needs the Gemini API key, which is not configured on the server.")
    if not 2 <= len(sources) <= 5:
        raise ConflictError("Choose between 2 and 5 sources to compare.")
    for s in sources:
        if not s.chunks:
            raise ConflictError(f"“{s.name}” has no readable text yet.")

    boundary = new_boundary()
    budget = min(14000, 48000 // len(sources))
    labels = {f"S{i + 1}": s for i, s in enumerate(sources)}
    blocks, meta, warnings = [], [], []
    for label, s in labels.items():
        text, truncated = select_text(s, topic or DEFAULT_QUERY, budget)
        if scan(text):
            warnings.append({"source": s.name, "snippet": scan(text)[0]})
        blocks.append(wrap_untrusted(f"{label}: {s.name}", text, boundary, max_chars=budget + 200))
        meta.append({"id": s.id, "label": label, "name": s.name, "url": s.url, "chars_sent": len(text), "truncated": truncated})

    prompt = PROMPT.format(topic_clause=f" ({topic})" if topic else "", fields=", ".join(FIELDS), blocks="\n\n".join(blocks))
    try:
        data = await gemini.generate_json(SYSTEM_GUARD, prompt, max_output_tokens=6000)
    except Exception as e:
        raise ConflictError(str(e) if e.__class__.__name__ == "AIError" else "The AI comparison step failed.")

    dropped = 0

    def verify(label, evidence):
        src = labels.get(label)
        if src is None or not isinstance(evidence, str):
            return None
        ok, page = locate(src, evidence)
        return {"source_id": src.id, "source": src.name, "url": src.url, "page": page} if ok else None

    claims = []
    for c in data.get("claims") or []:
        if not isinstance(c, dict):
            continue
        v = verify(c.get("source"), c.get("evidence"))
        field = c.get("field") if c.get("field") in FIELDS else "other"
        if v is None or not str(c.get("value", "")).strip():
            dropped += 1; continue
        claims.append({**v, "field": field, "value": str(c["value"])[:300], "evidence": str(c["evidence"])[:300]})

    conflicts = []
    for k in data.get("conflicts") or []:
        if not isinstance(k, dict):
            continue
        field = k.get("field") if k.get("field") in FIELDS else "other"
        good = []
        for c in k.get("claims") or []:
            v = verify(c.get("source"), c.get("evidence")) if isinstance(c, dict) else None
            if v is None or not str(c.get("value", "")).strip():
                dropped += 1; continue
            good.append({**v, "value": str(c["value"])[:300], "evidence": str(c["evidence"])[:300]})
        distinct_sources = {g["source_id"] for g in good}
        distinct_values = {normalise(g["value"]) for g in good}
        if len(distinct_sources) < 2 or len(distinct_values) < 2:
            dropped += 1; continue
        sev = k.get("severity") if k.get("severity") in ("low", "medium", "high") else "medium"
        if field in HIGH_IMPACT and sev == "low":
            sev = "medium"
        conflicts.append({"field": field, "severity": sev, "explanation": str(k.get("explanation", ""))[:600],
                          "claims": good, "resolution": RESOLUTION_NOTE})

    agreements = []
    for field in FIELDS:
        per_source = {}
        for c in claims:
            if c["field"] == field:
                per_source.setdefault(c["source_id"], c)
        if len(per_source) >= 2 and len({normalise(c["value"]) for c in per_source.values()}) == 1:
            agreements.append({"field": field, "value": next(iter(per_source.values()))["value"],
                               "sources": [{"source_id": c["source_id"], "source": c["source"], "page": c["page"],
                                            "evidence": c["evidence"]} for c in per_source.values()]})

    table: dict[str, dict[str, list]] = {}
    for c in claims:
        table.setdefault(c["field"], {}).setdefault(c["source_id"], []).append(
            {"value": c["value"], "evidence": c["evidence"], "page": c["page"]})

    order = {"high": 0, "medium": 1, "low": 2}
    conflicts.sort(key=lambda x: order[x["severity"]])
    summary = (f"Compared {len(sources)} sources and found {len(conflicts)} conflict(s) and {len(agreements)} matching field(s)."
               if conflicts or agreements else
               f"Compared {len(sources)} sources. No conflicts were found among the information that could be extracted and verified.")
    return {
        "topic": topic, "sources": meta, "conflicts": conflicts, "agreements": agreements, "comparison": table,
        "summary": summary,
        "ai_status": {"ran": True, "model": getattr(gemini, "model", None), "dropped_ungrounded": dropped,
                      "injection_warnings": warnings},
        "limitations": [
            "Only claims whose quoted evidence was found verbatim in the source text are shown.",
            "Fields a source does not mention are not compared; absence of a conflict is not proof of agreement.",
            "Long documents are sampled by relevance, so some passages may not have been compared." if any(m["truncated"] for m in meta)
            else "Whole documents were compared.",
            "This tool never decides which source is authoritative.",
        ],
    }
