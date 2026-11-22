import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.schemas.infoconflict import CompareRequest
from app.services import persist, sources as src_svc
from app.services.gemini import get_gemini
from app.services.infoconflict import ConflictError, SourceInput, compare_sources

router = APIRouter(prefix="/api/infoconflict", tags=["infoconflict"])


@router.post("/compare")
@limiter.limit("6/minute")
async def compare(request: Request, body: CompareRequest, user: CurrentUser = Depends(get_current_user)):
    ids = [str(i) for i in dict.fromkeys(body.source_ids)]
    if len(ids) < 2:
        raise HTTPException(400, "Choose at least two different sources.")
    db = for_user(user.token)
    rows = db.table("sources").select("id,name,url,status").in_("id", ids).execute().data
    if len(rows) != len(ids):
        raise HTTPException(404, "One or more sources were not found.")
    not_ready = [r["name"] for r in rows if r["status"] != "ready"]
    if not_ready:
        raise HTTPException(409, f"Still processing or failed: {', '.join(not_ready)}")
    inputs = [SourceInput(r["id"], r["name"], r.get("url"), await asyncio.to_thread(src_svc.load_chunks, db, r["id"])) for r in rows]

    topic = (body.topic or "").strip() or None
    analysis_id = persist.start_analysis(db, user.id, "infoconflict", f"Comparison: {topic or ', '.join(r['name'] for r in rows)}"[:200],
                                         {"source_ids": ids, "topic": topic})
    try:
        out = await asyncio.wait_for(compare_sources(get_gemini(), inputs, topic), 150)
    except ConflictError as e:
        persist.finish_analysis(db, analysis_id, False, str(e))
        raise HTTPException(422, str(e))
    except asyncio.TimeoutError:
        persist.finish_analysis(db, analysis_id, False, "timeout")
        raise HTTPException(504, "The comparison took too long. Try fewer or smaller sources.")
    except Exception:
        persist.finish_analysis(db, analysis_id, False, "internal error")
        raise

    db.table("infoconflict_results").insert({"analysis_id": analysis_id, "user_id": user.id, "topic": topic,
                                             "source_ids": ids, "summary": out["summary"],
                                             "conflicts": out["conflicts"], "agreements": out["agreements"]}).execute()
    sev = {s: sum(1 for c in out["conflicts"] if c["severity"] == s) for s in ("high", "medium", "low")}
    report_id = persist.save_report(db, user.id, analysis_id, "infoconflict", f"InfoConflict: {topic or 'source comparison'}",
                                    out["summary"], sev, out)
    persist.finish_analysis(db, analysis_id, True)
    persist.notify(db, user.id, "warning" if out["conflicts"] else "success", "InfoConflict comparison complete",
                   out["summary"], "/reports-and-findings")
    return {"analysis_id": analysis_id, "report_id": report_id, "result": out}


@router.get("/results")
def list_results(user: CurrentUser = Depends(get_current_user)):
    rows = (for_user(user.token).table("infoconflict_results").select("id,analysis_id,topic,summary,source_ids,created_at")
            .order("created_at", desc=True).limit(20).execute().data)
    return {"items": rows}
