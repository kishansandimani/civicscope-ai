import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import load_inputs
from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.schemas.modules import PromiseTraceRequest
from app.services import persist
from app.services.gemini import get_gemini
from app.services.promisetrace import TraceError, trace_commitments

router = APIRouter(prefix="/api/promisetrace", tags=["promisetrace"])


@router.post("/analyze")
@limiter.limit("6/minute")
async def analyze(request: Request, body: PromiseTraceRequest, user: CurrentUser = Depends(get_current_user)):
    ids = [str(i) for i in dict.fromkeys(body.source_ids)]
    db = for_user(user.token)
    inputs = await load_inputs(db, ids)
    analysis_id = persist.start_analysis(db, user.id, "promisetrace", f"Commitment trace: {', '.join(s.name for s in inputs)}"[:200], {"source_ids": ids})
    try:
        out = await asyncio.wait_for(trace_commitments(get_gemini(), inputs), 150)
    except TraceError as e:
        persist.finish_analysis(db, analysis_id, False, str(e))
        raise HTTPException(422, str(e))
    except asyncio.TimeoutError:
        persist.finish_analysis(db, analysis_id, False, "timeout")
        raise HTTPException(504, "The analysis took too long. Try fewer or smaller sources.")
    except Exception:
        persist.finish_analysis(db, analysis_id, False, "internal error")
        raise

    for p in out["projects"]:
        row = db.table("promisetrace_projects").insert({
            "user_id": user.id, "analysis_id": analysis_id, "title": p["title"], "department": p["department"],
            "commitment_text": p["commitment"]["quote"], "announced_on": p["announced_on"], "target_date": p["target_date"],
            "status": p["status"], "evidence_summary": p["status_note"], "source_ids": ids}).execute().data[0]
        p["project_id"] = row["id"]
        if p["milestones"]:
            db.table("promise_milestones").insert([{
                "project_id": row["id"], "user_id": user.id, "title": m["title"], "due_date": m["due_date"], "status": m["status"],
                "evidence": m["evidence"], "source_id": m["source_id"], "page_number": m["page"]} for m in p["milestones"]]).execute()
    report_id = persist.save_report(db, user.id, analysis_id, "promisetrace", "PromiseTrace: commitment tracker", out["summary"], out["counts"], out)
    persist.finish_analysis(db, analysis_id, True)
    persist.notify(db, user.id, "info", "PromiseTrace analysis complete", out["summary"], "/promisetrace")
    return {"analysis_id": analysis_id, "report_id": report_id, "result": out}


@router.get("/projects")
def list_projects(user: CurrentUser = Depends(get_current_user)):
    db = for_user(user.token)
    projects = db.table("promisetrace_projects").select("*").order("created_at", desc=True).limit(100).execute().data
    if projects:
        ms = db.table("promise_milestones").select("*").in_("project_id", [p["id"] for p in projects]).order("due_date").execute().data
        for p in projects:
            p["milestones"] = [m for m in ms if m["project_id"] == p["id"]]
    return {"items": projects}
