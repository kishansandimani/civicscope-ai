from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import account, accessshadow, civicprobe, infoconflict, promisetrace, reports, rulestress, sources, voice
from app.core.limiter import limiter
from app.core.config import get_settings
from app.database.supabase_client import SupabaseNotConfigured

settings = get_settings()

app = FastAPI(title="CivicScope AI API", version="0.1.0",
              docs_url="/api/docs", openapi_url="/api/openapi.json")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_list, allow_credentials=True,
                   allow_methods=["GET", "POST", "PATCH", "DELETE"], allow_headers=["Authorization", "Content-Type"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    resp.headers.setdefault("X-Frame-Options", "DENY")
    return resp


@app.exception_handler(SupabaseNotConfigured)
async def _not_configured(_, exc):
    return JSONResponse(status_code=503, content={"detail": "Database is not configured on the server."})


@app.exception_handler(Exception)
async def _unhandled(_, exc):
    # Never leak internals to the client; details go to server logs.
    import logging
    logging.getLogger("civicscope").exception("Unhandled error", exc_info=exc)
    return JSONResponse(status_code=500, content={"detail": "Something went wrong. Please try again."})


app.include_router(account.router)
app.include_router(civicprobe.router)
app.include_router(sources.router)
app.include_router(infoconflict.router)
app.include_router(accessshadow.router)
app.include_router(rulestress.router)
app.include_router(promisetrace.router)
app.include_router(reports.router)
app.include_router(voice.router)


@app.get("/api/health")
def health():
    return {"status": "ok", "supabase_configured": settings.supabase_configured,
            "gemini_configured": settings.gemini_configured}


# ---- frontend -------------------------------------------------------------
FRONTEND = Path(__file__).resolve().parents[2] / "frontend"
PAGES = FRONTEND / "pages"


@app.get("/static/js/config.js", include_in_schema=False)
def runtime_config():
    """Public runtime config. Only the anon key is exposed; it is designed to be public."""
    js = ("window.CIVIC_CONFIG = " + JSONResponse({
        "supabaseUrl": settings.supabase_url, "supabaseAnonKey": settings.supabase_anon_key}).body.decode() + ";")
    return PlainTextResponse(js, media_type="application/javascript")


app.mount("/static", StaticFiles(directory=FRONTEND / "static"), name="static")
app.mount("/design", StaticFiles(directory=FRONTEND / "design"), name="design")


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/overview")


@app.get("/{page}", include_in_schema=False)
def page(page: str):
    f = (PAGES / f"{page}.html").resolve()
    if PAGES.resolve() not in f.parents or not f.is_file():
        raise HTTPException(404, "Page not found")
    return FileResponse(f)
