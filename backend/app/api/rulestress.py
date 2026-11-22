import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.api.deps import load_inputs
from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.schemas.modules import RuleStressRequest
from app.services import persist
from app.services.gemini import get_gemini
from app.services.rulestress import RuleError, stress_test

router = APIRouter(prefix="/api/rulestress", tags=["rulestress"])


@router.post("/test")
@limiter.limit("12/minute")
async def test_scenario(request: Request, body: RuleStressRequest, user: CurrentUser = Depends(get_current_user)):
    db = for_user(user.token)
    (src,) = await load_inputs(db, [str(body.source_id)])
    analysis_id = persist.start_analysis(db, user.id, "rulestress", f"Scenario test: {body.scenario[:80]}", {"source_id": src.id})
    try:
        out = await asyncio.wait_for(stress_test(get_gemini(), src, body.scenario), 90)
    except RuleError as e:
        persist.finish_analysis(db, analysis_id, False, str(e))
        raise HTTPException(422, str(e))
    except asyncio.TimeoutError:
        persist.finish_analysis(db, analysis_id, False, "timeout")
        raise HTTPException(504, "The analysis took too long. Please try again.")
    except Exception:
        persist.finish_analysis(db, analysis_id, False, "internal error")
        raise
    db.table("rulestress_results").insert({
        "analysis_id": analysis_id, "user_id": user.id, "source_id": src.id, "scenario": out["scenario"],
        "verdict": out["verdict"], "answer": out["answer"], "conditions": out["conditions"],
        "ambiguities": out["ambiguities"], "evidence": out["evidence"], "confidence": out["confidence"]}).execute()
    report_id = persist.save_report(db, user.id, analysis_id, "rulestress", f"RuleStress: {src.name}",
                                    out["answer"][:300], {"ambiguities": len(out["ambiguities"])}, out)
    persist.finish_analysis(db, analysis_id, True)
    return {"analysis_id": analysis_id, "report_id": report_id, "result": out}


@router.get("/results")
def list_results(user: CurrentUser = Depends(get_current_user)):
    rows = (for_user(user.token).table("rulestress_results").select("id,analysis_id,source_id,scenario,verdict,confidence,created_at")
            .order("created_at", desc=True).limit(30).execute().data)
    return {"items": rows}
