import asyncio

from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import admin, for_user
from app.schemas.accessshadow import AccessRequest
from app.services import persist
from app.services.accessshadow import analyze_html, analyze_pdf, summarize
from app.services.extract import decode_body
from app.services.fetcher import Fetcher
from app.utils.url_safety import UnsafeURL, validate_public_url

router = APIRouter(prefix="/api/accessshadow", tags=["accessshadow"])


async def _fetch(url: str):
    res = await Fetcher().fetch(url)
    if res.status is None:
        raise HTTPException(422, f"Could not open that address ({res.error}).")
    if not res.ok:
        raise HTTPException(422, f"The address returned HTTP {res.status}.")
    return res


def _run_on_bytes(body: bytes, content_type: str, is_pdf: bool, name: str) -> dict:
    if is_pdf:
        try:
            return analyze_pdf(body, name)
        except Exception:
            raise HTTPException(422, "The PDF could not be analysed (it may be corrupted or encrypted).")
    return analyze_html(decode_body(body, content_type), name)


@router.post("/analyze")
@limiter.limit("8/minute")
async def analyze(request: Request, body: AccessRequest, user: CurrentUser = Depends(get_current_user)):
    db = for_user(user.token)
    source_id, target = None, None
    if body.url:
        try:
            target = await asyncio.to_thread(validate_public_url, body.url)
        except UnsafeURL as e:
            raise HTTPException(400, str(e))
        res = await _fetch(target)
        content, ctype, is_pdf = res.body, res.content_type, res.is_pdf
        if not (res.is_html or is_pdf):
            raise HTTPException(422, "Only web pages and PDFs can be analysed.")
        target = res.final_url
    else:
        source_id = str(body.source_id)
        rows = db.table("sources").select("id,name,kind,url,storage_path,mime_type").eq("id", source_id).limit(1).execute().data
        if not rows:
            raise HTTPException(404, "Source not found.")
        s = rows[0]
        target = s["name"]
        if s.get("storage_path"):
            content = admin().storage.from_("civic-documents").download(s["storage_path"])   # row was fetched through RLS, so the path is the user's own
            ctype, is_pdf = s.get("mime_type") or "", s["kind"] == "pdf"
            if not is_pdf and "html" not in ctype:
                raise HTTPException(422, "Plain-text files have no structure to check for accessibility.")
        elif s.get("url"):
            res = await _fetch(s["url"])
            content, ctype, is_pdf = res.body, res.content_type, res.is_pdf
        else:
            raise HTTPException(422, "This source has no stored content to analyse.")

    analysis_id = persist.start_analysis(db, user.id, "accessshadow", f"Accessibility check: {target}"[:200], {"target": target})
    try:
        result = summarize(await asyncio.to_thread(_run_on_bytes, content, ctype, is_pdf, target))
    except HTTPException as e:
        persist.finish_analysis(db, analysis_id, False, e.detail)
        raise
    except Exception:
        persist.finish_analysis(db, analysis_id, False, "internal error")
        raise
    db.table("accessshadow_results").insert({
        "analysis_id": analysis_id, "user_id": user.id, "source_id": source_id, "target": target[:500],
        "automated_findings": result["automated_findings"], "manual_review_items": result["manual_review_items"],
        "language_findings": result["language_findings"], "counts": result["counts"], "summary": result["summary"]}).execute()
    report_id = persist.save_report(db, user.id, analysis_id, "accessshadow", f"AccessShadow: {target}", result["summary"],
                                    {k: result["counts"][k] for k in ("high", "medium", "low")}, result)
    persist.finish_analysis(db, analysis_id, True)
    persist.notify(db, user.id, "warning" if result["counts"]["high"] else "info", "AccessShadow analysis complete",
                   result["summary"], "/reports-and-findings")
    return {"analysis_id": analysis_id, "report_id": report_id, "result": result}


@router.get("/results")
def list_results(user: CurrentUser = Depends(get_current_user)):
    rows = (for_user(user.token).table("accessshadow_results").select("id,analysis_id,target,counts,summary,created_at")
            .order("created_at", desc=True).limit(20).execute().data)
    return {"items": rows}
