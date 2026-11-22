import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.schemas.civicprobe import AnalyzeRequest, AnalyzeResponse
from app.services import persist
from app.services.civicprobe import ProbeError, analyze_site
from app.services.fetcher import Fetcher
from app.services.gemini import get_gemini
from app.utils.url_safety import UnsafeURL, validate_public_url

router = APIRouter(prefix="/api/civicprobe", tags=["civicprobe"])
TIMEOUT_SECONDS = 150


@router.post("/analyze", response_model=AnalyzeResponse)
@limiter.limit("5/minute")
async def analyze(request: Request, body: AnalyzeRequest, user: CurrentUser = Depends(get_current_user)):
    try:
        url = await asyncio.to_thread(validate_public_url, body.url)
    except UnsafeURL as e:
        raise HTTPException(400, str(e))

    db = for_user(user.token)
    analysis_id = persist.start_analysis(db, user.id, "civicprobe", f"Audit of {url}", {"url": url, "max_pages": body.max_pages})
    try:
        result = await asyncio.wait_for(analyze_site(url, Fetcher(), get_gemini(), max_pages=body.max_pages), TIMEOUT_SECONDS)
    except ProbeError as e:
        persist.finish_analysis(db, analysis_id, False, str(e))
        persist.notify(db, user.id, "error", "CivicProbe audit failed", str(e))
        raise HTTPException(422, str(e))
    except asyncio.TimeoutError:
        persist.finish_analysis(db, analysis_id, False, "timeout")
        raise HTTPException(504, "The audit took too long. Try fewer pages.")
    except Exception:
        persist.finish_analysis(db, analysis_id, False, "internal error")
        raise

    out = result.to_dict()
    db.table("civicprobe_results").insert({
        "analysis_id": analysis_id, "user_id": user.id, "target_url": url,
        "pages_scanned": out["pages_scanned"], "links_checked": out["links_checked"],
        "broken_links": out["broken_links"], "summary": out["summary"],
        "health_score": out["health_score"],
        "findings": out["findings"],
    }).execute()
    sev = {s: sum(1 for f in out["findings"] if f["severity"] == s) for s in ("critical", "high", "medium", "low")}
    report_id = persist.save_report(db, user.id, analysis_id, "civicprobe", f"CivicProbe audit: {url}",
                                    out["summary"], sev, out)
    persist.finish_analysis(db, analysis_id, True)
    persist.notify(db, user.id, "success" if not sev["high"] and not sev["critical"] else "warning",
                   "CivicProbe audit complete", out["summary"], "/reports-and-findings")
    return {"analysis_id": analysis_id, "report_id": report_id, "result": out}


@router.get("/analyses")
def list_analyses(user: CurrentUser = Depends(get_current_user)):
    rows = (for_user(user.token).table("civicprobe_results")
            .select("id,analysis_id,target_url,pages_scanned,links_checked,broken_links,health_score,summary,created_at")
            .order("created_at", desc=True).limit(20).execute().data)
    return {"items": rows}


@router.get("/analyses/{analysis_id}")
def get_analysis(analysis_id: UUID, user: CurrentUser = Depends(get_current_user)):
    rows = (for_user(user.token).table("civicprobe_results").select("*")
            .eq("analysis_id", str(analysis_id)).limit(1).execute().data)
    if not rows:
        raise HTTPException(404, "Analysis not found.")
    return rows[0]
