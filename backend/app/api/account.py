"""Profile, settings, notifications and dashboard statistics (all RLS-scoped)."""
from fastapi import APIRouter, Depends, HTTPException

from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import for_user
from app.schemas.common import ProfileOut, ProfileUpdate, SettingsUpdate

router = APIRouter(prefix="/api", tags=["account"])


def _one(res):
    data = res.data
    if isinstance(data, list):
        return data[0] if data else None
    return data


@router.get("/me", response_model=ProfileOut)
def me(user: CurrentUser = Depends(get_current_user)):
    row = _one(for_user(user.token).table("profiles").select("*").eq("id", user.id).limit(1).execute()) or {}
    return ProfileOut(id=user.id, email=user.email, **{k: row.get(k) for k in
                      ("full_name", "designation", "organization") if k in row},
                      preferred_language=row.get("preferred_language", "en"))


@router.patch("/me", response_model=ProfileOut)
def update_me(body: ProfileUpdate, user: CurrentUser = Depends(get_current_user)):
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(400, "Nothing to update.")
    db = for_user(user.token)
    db.table("profiles").update(patch).eq("id", user.id).execute()
    return me(user)


@router.get("/settings")
def get_settings_endpoint(user: CurrentUser = Depends(get_current_user)):
    db = for_user(user.token)
    row = _one(db.table("user_settings").select("*").eq("user_id", user.id).limit(1).execute())
    if row is None:  # e.g. user created before the trigger existed
        row = _one(db.table("user_settings").insert({"user_id": user.id}).execute())
    return row


@router.patch("/settings")
def update_settings(body: SettingsUpdate, user: CurrentUser = Depends(get_current_user)):
    patch = body.model_dump(exclude_none=True)
    if not patch:
        raise HTTPException(400, "Nothing to update.")
    db = for_user(user.token)
    db.table("user_settings").upsert({"user_id": user.id, **patch}).execute()
    return get_settings_endpoint(user)


@router.get("/notifications")
def list_notifications(user: CurrentUser = Depends(get_current_user)):
    res = for_user(user.token).table("notifications").select("*").order("created_at", desc=True).limit(50).execute()
    return {"items": res.data, "unread": sum(1 for n in res.data if not n["is_read"])}


@router.post("/notifications/read-all")
def mark_all_read(user: CurrentUser = Depends(get_current_user)):
    for_user(user.token).table("notifications").update({"is_read": True}).eq("is_read", False).execute()
    return {"ok": True}


@router.get("/dashboard/stats")
def dashboard_stats(user: CurrentUser = Depends(get_current_user)):
    """Only real, stored numbers. Empty accounts return zeros, never invented data."""
    db = for_user(user.token)
    analyses = db.table("analyses").select("id,module,status,title,created_at").order("created_at", desc=True).limit(500).execute().data
    by_module = {m: 0 for m in ("civicprobe", "infoconflict", "accessshadow", "rulestress", "promisetrace")}
    for a in analyses:
        by_module[a["module"]] = by_module.get(a["module"], 0) + 1
    sources = db.table("sources").select("id", count="exact").limit(1).execute().count or 0
    reports = db.table("reports").select("id", count="exact").limit(1).execute().count or 0
    return {
        "totals": {"analyses": len(analyses), "sources": sources, "reports": reports},
        "by_module": by_module,
        "recent": analyses[:8],
        "is_empty": len(analyses) == 0 and sources == 0,
    }
