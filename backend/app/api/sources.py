import asyncio
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from app.core.config import get_settings
from app.core.limiter import limiter
from app.core.security import CurrentUser, get_current_user
from app.database.supabase_client import admin, for_user
from app.schemas.sources import UrlSourceRequest
from app.services import sources as svc
from app.services.extract import decode_body, extract_pdf_pages, parse_html
from app.services.fetcher import Fetcher
from app.utils.url_safety import UnsafeURL, validate_public_url

router = APIRouter(prefix="/api/sources", tags=["sources"])
COLS = "id,kind,name,url,status,page_count,size_bytes,error_message,created_at"


def _guard_quota(db):
    n = db.table("sources").select("id", count="exact").limit(1).execute().count or 0
    if n >= svc.MAX_SOURCES_PER_USER:
        raise HTTPException(409, f"You have reached the limit of {svc.MAX_SOURCES_PER_USER} sources. Delete some first.")


@router.get("")
def list_sources(user: CurrentUser = Depends(get_current_user)):
    rows = for_user(user.token).table("sources").select(COLS).order("created_at", desc=True).limit(200).execute().data
    return {"items": rows}


@router.post("/upload", status_code=201)
@limiter.limit("20/minute")
async def upload(request: Request, file: UploadFile = File(...), user: CurrentUser = Depends(get_current_user)):
    max_bytes = get_settings().max_upload_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)          # never read more than limit+1 bytes into memory
    try:
        prep = await asyncio.to_thread(svc.validate_and_prepare, file.filename or "document", data, max_bytes)
    except svc.IngestError as e:
        raise HTTPException(400, str(e))

    db = for_user(user.token)
    _guard_quota(db)
    dup = db.table("sources").select("id,name").eq("content_hash", prep.sha256).limit(1).execute().data
    if dup:
        raise HTTPException(409, f"You already uploaded this file as “{dup[0]['name']}”.")
    source_id = str(uuid4())
    path = f"{user.id}/{source_id}/{prep.filename}"
    db.table("sources").insert({"id": source_id, "user_id": user.id, "kind": prep.kind, "name": prep.filename,
                                "storage_path": path, "mime_type": prep.mime, "size_bytes": len(data),
                                "content_hash": prep.sha256, "status": "processing", "page_count": prep.page_count}).execute()
    try:
        admin().storage.from_("civic-documents").upload(path, data, {"content-type": prep.mime})   # path = <user id>/<new uuid>/<clean name>
        n = await asyncio.to_thread(svc.persist_chunks, db, source_id, user.id, prep.pages)
        db.table("sources").update({"status": "ready"}).eq("id", source_id).execute()
    except Exception:
        db.table("sources").update({"status": "failed", "error_message": "Processing failed."}).eq("id", source_id).execute()
        raise HTTPException(500, "The file was received but could not be processed.")
    return {"id": source_id, "name": prep.filename, "kind": prep.kind, "chunks": n, "page_count": prep.page_count}


@router.post("/url", status_code=201)
@limiter.limit("10/minute")
async def add_url(request: Request, body: UrlSourceRequest, user: CurrentUser = Depends(get_current_user)):
    try:
        url = await asyncio.to_thread(validate_public_url, body.url)
    except UnsafeURL as e:
        raise HTTPException(400, str(e))
    db = for_user(user.token)
    _guard_quota(db)
    res = await Fetcher().fetch(url)
    if res.status is None:
        raise HTTPException(422, f"Could not open that address ({res.error}).")
    if not res.ok:
        raise HTTPException(422, f"The address returned HTTP {res.status}.")
    if res.is_pdf:
        pages, kind, title = await asyncio.to_thread(extract_pdf_pages, res.body), "pdf", res.final_url.rsplit("/", 1)[-1] or res.final_url
    elif res.is_html:
        parsed = parse_html(decode_body(res.body, res.content_type), res.final_url)
        pages, kind, title = [(None, parsed.text)], "url", parsed.title or res.final_url
    else:
        raise HTTPException(422, "Only web pages and PDFs can be added by address.")
    if not any(t.strip() for _, t in pages):
        raise HTTPException(422, "No readable text was found at that address.")
    row = db.table("sources").insert({"user_id": user.id, "kind": "url" if kind == "url" else "pdf", "name": title[:200],
                                      "url": res.final_url, "mime_type": res.content_type[:100], "size_bytes": len(res.body),
                                      "status": "processing", "page_count": len(pages) if kind == "pdf" else None}).execute().data[0]
    try:
        n = await asyncio.to_thread(svc.persist_chunks, db, row["id"], user.id, pages)
        db.table("sources").update({"status": "ready", "fetched_at": datetime.now(timezone.utc).isoformat()}).eq("id", row["id"]).execute()
    except Exception:
        db.table("sources").update({"status": "failed", "error_message": "Processing failed."}).eq("id", row["id"]).execute()
        raise HTTPException(500, "The page was fetched but could not be processed.")
    return {"id": row["id"], "name": row["name"], "kind": row["kind"], "chunks": n}


@router.get("/{source_id}")
def get_source(source_id: UUID, user: CurrentUser = Depends(get_current_user)):
    db = for_user(user.token)
    rows = db.table("sources").select(COLS).eq("id", str(source_id)).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Source not found.")
    chunks = db.table("source_chunks").select("id", count="exact").eq("source_id", str(source_id)).limit(1).execute().count or 0
    return {**rows[0], "chunks": chunks}


@router.delete("/{source_id}", status_code=204)
def delete_source(source_id: UUID, user: CurrentUser = Depends(get_current_user)):
    db = for_user(user.token)
    rows = db.table("sources").select("storage_path").eq("id", str(source_id)).limit(1).execute().data
    if not rows:
        raise HTTPException(404, "Source not found.")
    if rows[0].get("storage_path"):
        try:
            admin().storage.from_("civic-documents").remove([rows[0]["storage_path"]])   # path came from a row RLS already showed this user
        except Exception:
            pass  # row deletion still proceeds; orphaned object is private to the user's folder
    db.table("sources").delete().eq("id", str(source_id)).execute()
