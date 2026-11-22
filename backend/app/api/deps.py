import asyncio

from fastapi import HTTPException

from app.services import sources as src_svc
from app.services.infoconflict import SourceInput


async def load_inputs(db, ids: list[str]) -> list[SourceInput]:
    rows = db.table("sources").select("id,name,url,status").in_("id", ids).execute().data
    if len(rows) != len(ids):
        raise HTTPException(404, "One or more sources were not found.")
    not_ready = [r["name"] for r in rows if r["status"] != "ready"]
    if not_ready:
        raise HTTPException(409, f"Still processing or failed: {', '.join(not_ready)}")
    by_id = {r["id"]: r for r in rows}
    out = []
    for i in ids:
        r = by_id[i]
        out.append(SourceInput(r["id"], r["name"], r.get("url"), await asyncio.to_thread(src_svc.load_chunks, db, r["id"])))
    return out
