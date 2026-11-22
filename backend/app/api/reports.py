from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.services.reporting import speakable, to_markdown

router = APIRouter(prefix="/api/reports", tags=["reports"])
MODULES = {"civicprobe", "infoconflict", "accessshadow", "rulestress", "promisetrace"}


def _get(user: CurrentUser, report_id: UUID) -> dict:
    rows = for_user(user.token).table("reports").select("*").eq("id", str(report_id)).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Report not found.")
    return rows[0]


@router.get("")
def list_reports(module: str | None = Query(default=None), user: CurrentUser = Depends(get_current_user)):
    if module and module not in MODULES:
        raise HTTPException(400, "Unknown module.")
    q = for_user(user.token).table("reports").select("id,module,title,summary,severity_counts,created_at").order("created_at", desc=True).limit(100)
    if module:
        q = q.eq("module", module)
    return {"items": q.execute().data}


@router.get("/{report_id}")
def get_report(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    return _get(user, report_id)


@router.get("/{report_id}/markdown")
def export_markdown(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    r = _get(user, report_id)
    name = "".join(c if c.isalnum() else "-" for c in r["title"])[:60].strip("-") or "report"
    return PlainTextResponse(to_markdown(r["title"], r["module"], r["created_at"], r["body"]), media_type="text/markdown; charset=utf-8",
                             headers={"Content-Disposition": f'attachment; filename="{name}.md"'})


@router.get("/{report_id}/speakable")
def speakable_text(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    r = _get(user, report_id)
    return {"id": r["id"], "title": r["title"], "text": speakable(r["title"], r["module"], r["body"])}


@router.delete("/{report_id}", status_code=204)
def delete_report(report_id: UUID, user: CurrentUser = Depends(get_current_user)):
    _get(user, report_id)
    for_user(user.token).table("reports").delete().eq("id", str(report_id)).execute()
