"""PromiseTrace — extract public commitments, deadlines and progress evidence from real sources.

Rules enforced in code:
- every commitment, milestone and update must quote text found verbatim in a source (page number attached by code)
- a status of on_track / delayed / completed needs at least one verified progress-update quote, otherwise it becomes
  "no_update_found"; a missing update is never turned into "delayed" or "failed"
- dates must parse as real calendar dates; invalid ones are dropped, not guessed
"""
from datetime import date

from app.services.infoconflict import SourceInput, locate, select_text
from app.services.injection import SYSTEM_GUARD, new_boundary, scan, wrap_untrusted

PROJECT_STATUS = ("on_track", "delayed", "completed", "no_update_found", "unclear")
MILESTONE_STATUS = ("unknown", "pending", "in_progress", "completed", "delayed")
NEEDS_EVIDENCE = {"on_track", "delayed", "completed"}
QUERY = "will announced committed target by deadline completed progress launched inaugurated milestone phase"


class TraceError(Exception):
    """User-safe message."""


PROMPT = """Today's date is {today}. From the sources below, extract PUBLIC COMMITMENTS made by government bodies
(promised projects, schemes, targets, deadlines) and any OFFICIAL PROGRESS UPDATES about them.

Rules:
- Only extract commitments clearly stated in the text. Quote the commitment exactly in "commitment_quote" (max 200 chars).
- "target_date"/"announced_on"/"due_date"/"update.date" must be ISO YYYY-MM-DD, only if a full date is stated; otherwise null. Never guess a date.
- "progress_updates": official statements about progress. Quote each exactly. Include which source label it came from.
- status: completed / on_track / delayed ONLY when a progress update says so. If no progress update exists, status MUST be "no_update_found".
  Missing information is NOT evidence of failure or delay.
- milestone status: unknown | pending | in_progress | completed | delayed (delayed only if a source says it was delayed or rescheduled).
Return JSON: {{"projects":[{{"title":"...","department":"...|null","source":"S1","commitment_quote":"...",
"announced_on":null,"target_date":null,"status":"...",
"milestones":[{{"title":"...","due_date":null,"status":"unknown","evidence":"...","source":"S1"}}],
"progress_updates":[{{"date":null,"description":"...","evidence":"...","source":"S2"}}]}}]}}
Return at most {max_projects} projects.

{blocks}"""


def iso(d) -> str | None:
    if not isinstance(d, str):
        return None
    try:
        return date.fromisoformat(d.strip()[:10]).isoformat()
    except ValueError:
        return None


async def trace_commitments(gemini, sources: list[SourceInput], today: date | None = None, max_projects: int = 12) -> dict:
    if gemini is None:
        raise TraceError("PromiseTrace needs the Gemini API key, which is not configured on the server.")
    if not 1 <= len(sources) <= 5:
        raise TraceError("Choose between 1 and 5 sources.")
    for s in sources:
        if not s.chunks:
            raise TraceError(f"“{s.name}” has no readable text yet.")
    today = today or date.today()
    boundary = new_boundary()
    budget = min(16000, 48000 // len(sources))
    labels = {f"S{i + 1}": s for i, s in enumerate(sources)}
    blocks, warnings = [], []
    for label, s in labels.items():
        text, _ = select_text(s, QUERY, budget)
        if scan(text):
            warnings.append({"source": s.name, "snippet": scan(text)[0]})
        blocks.append(wrap_untrusted(f"{label}: {s.name}", text, boundary, max_chars=budget + 200))
    try:
        data = await gemini.generate_json(SYSTEM_GUARD, PROMPT.format(today=today.isoformat(), max_projects=max_projects, blocks="\n\n".join(blocks)), max_output_tokens=7000)
    except Exception as e:
        raise TraceError(str(e) if e.__class__.__name__ == "AIError" else "The AI extraction step failed.")

    dropped = 0

    def verify(label, evidence):
        s = labels.get(label)
        if s is None or not isinstance(evidence, str):
            return None
        ok, page = locate(s, evidence)
        return {"source_id": s.id, "source": s.name, "page": page} if ok else None

    projects = []
    for p in (data.get("projects") or [])[:max_projects]:
        if not isinstance(p, dict) or not str(p.get("title", "")).strip():
            continue
        v = verify(p.get("source"), p.get("commitment_quote"))
        if v is None:
            dropped += 1; continue           # no verified commitment => not a commitment we can report
        updates = []
        for u in p.get("progress_updates") or []:
            uv = verify(u.get("source"), u.get("evidence")) if isinstance(u, dict) else None
            if uv is None:
                dropped += 1; continue
            updates.append({"date": iso(u.get("date")), "description": str(u.get("description", ""))[:500],
                            "evidence": str(u["evidence"])[:300], **uv})
        milestones = []
        for m in p.get("milestones") or []:
            mv = verify(m.get("source"), m.get("evidence")) if isinstance(m, dict) else None
            if mv is None:
                dropped += 1; continue
            st = m.get("status") if m.get("status") in MILESTONE_STATUS else "unknown"
            milestones.append({"title": str(m.get("title", ""))[:300], "due_date": iso(m.get("due_date")), "status": st,
                               "evidence": str(m["evidence"])[:300], **mv})
        status = p.get("status") if p.get("status") in PROJECT_STATUS else "unclear"
        note = None
        if status in NEEDS_EVIDENCE and not updates:
            status, note = "no_update_found", "No official progress update was found in the provided sources. This does not mean the commitment has failed."
        if not updates and status == "unclear":
            status = "no_update_found"
        if not updates:
            for m in milestones:             # a passed due date alone never means "delayed"
                if m["status"] in ("delayed", "completed", "in_progress"):
                    m["status"] = "unknown"
        target = iso(p.get("target_date"))
        past_due_note = None
        if target and target < today.isoformat() and status in ("no_update_found", "unclear"):
            past_due_note = f"Target date {target} has passed and no update was found in the provided sources; check official channels."
        projects.append({
            "title": str(p["title"])[:300], "department": (str(p["department"])[:200] if p.get("department") else None),
            "commitment": {"quote": str(p["commitment_quote"])[:300], **v}, "announced_on": iso(p.get("announced_on")),
            "target_date": target, "status": status, "status_note": note or past_due_note,
            "milestones": milestones, "progress_updates": updates,
            "timeline": sorted([e for e in (
                [{"date": iso(p.get("announced_on")), "type": "announced", "label": "Commitment announced"}]
                + [{"date": m["due_date"], "type": "milestone", "label": m["title"], "status": m["status"]} for m in milestones]
                + [{"date": u["date"], "type": "update", "label": u["description"]} for u in updates]
                + [{"date": target, "type": "target", "label": "Target date"}]) if e["date"]], key=lambda e: e["date"]),
        })
    counts = {s: sum(1 for p in projects if p["status"] == s) for s in PROJECT_STATUS}
    return {
        "projects": projects, "counts": counts,
        "summary": (f"Found {len(projects)} verifiable commitment(s): " + ", ".join(f"{n} {s.replace('_', ' ')}" for s, n in counts.items() if n) + "."
                    if projects else "No verifiable public commitments were found in the provided sources."),
        "sources": [{"id": s.id, "label": l, "name": s.name} for l, s in labels.items()],
        "ai_status": {"ran": True, "model": getattr(gemini, "model", None), "dropped_ungrounded": dropped, "injection_warnings": warnings},
        "limitations": [
            "Only commitments and updates quoted in the provided sources are shown; other announcements may exist elsewhere.",
            "“No update found” means none appears in these sources, not that nothing has happened.",
            "Dates are shown only when a full date is stated in the source.",
        ],
    }
