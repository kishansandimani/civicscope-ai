"""Verifies your .env and cloud setup. Run from backend/ after `pip install -r requirements.txt`:
    python scripts/check_setup.py
Prints PASS / FAIL / WARN per check with the fix. Nothing is modified."""
import asyncio
import sys

import httpx

sys.path.insert(0, ".")
from app.core.config import get_settings  # noqa: E402
from app.services.gemini import AIError, GeminiService  # noqa: E402

s = get_settings()
bad = 0


def line(status, msg, fix=""):
    global bad
    if status == "FAIL":
        bad += 1
    print(f"[{status}] {msg}" + (f"\n        -> {fix}" if fix else ""))


def need(name, value, hint):
    if value:
        line("PASS", f"{name} is set")
    else:
        line("FAIL", f"{name} is missing", hint)
    return bool(value)


print("== Environment (.env) ==")
ok_url = need("SUPABASE_URL", s.supabase_url, "Copy the Project URL from Supabase -> Project Settings -> API")
ok_anon = need("SUPABASE_ANON_KEY", s.supabase_anon_key, "Copy the anon/public key")
ok_srv = need("SUPABASE_SERVICE_ROLE_KEY", s.supabase_service_role_key, "Copy the service_role key (server only, never share it)")
ok_gem = need("GEMINI_API_KEY", s.gemini_api_key, "Create one at https://aistudio.google.com/apikey")
if s.supabase_url and not s.supabase_url.startswith("https://"):
    line("WARN", "SUPABASE_URL should start with https://")

if ok_url and ok_srv:
    base, hdr = s.supabase_url.rstrip("/"), {"apikey": s.supabase_service_role_key, "Authorization": f"Bearer {s.supabase_service_role_key}"}
    print("\n== Supabase ==")
    try:
        r = httpx.get(f"{base}/rest/v1/profiles?select=id&limit=1", headers=hdr, timeout=15)
        if r.status_code == 200:
            line("PASS", "Database reachable and `profiles` table exists")
        elif r.status_code in (404, 400) or "relation" in r.text:
            line("FAIL", "Connected, but the tables are missing", "Open Supabase -> SQL Editor, paste supabase/schema.sql, Run")
        elif r.status_code in (401, 403):
            line("FAIL", "Supabase rejected the service-role key", "Re-copy SUPABASE_SERVICE_ROLE_KEY (the long 'service_role' one)")
        else:
            line("FAIL", f"Unexpected response {r.status_code}: {r.text[:160]}")
        for t in ("analyses", "sources", "source_chunks", "reports", "notifications", "user_settings", "promisetrace_projects"):
            rr = httpx.get(f"{base}/rest/v1/{t}?select=*&limit=1", headers=hdr, timeout=15)
            if rr.status_code != 200:
                line("FAIL", f"Table `{t}` not accessible ({rr.status_code})", "Re-run supabase/schema.sql")
                break
        else:
            line("PASS", "Core tables are accessible")
        b = httpx.get(f"{base}/storage/v1/bucket/civic-documents", headers=hdr, timeout=15)
        line("PASS", "Storage bucket `civic-documents` exists") if b.status_code == 200 else line("FAIL", "Storage bucket `civic-documents` not found", "Re-run supabase/schema.sql (it creates the bucket)")
        if ok_anon:
            a = httpx.get(f"{base}/auth/v1/settings", headers={"apikey": s.supabase_anon_key}, timeout=15)
            if a.status_code == 200:
                j = a.json()
                line("PASS", "Auth endpoint reachable with the anon key")
                if not j.get("mailer_autoconfirm", True):
                    line("WARN", "Email confirmation is ON: new users must click an email link before signing in",
                         "For a quick demo: Authentication -> Providers -> Email -> turn off 'Confirm email'")
                if j.get("disable_signup"):
                    line("WARN", "Sign-ups are disabled in Supabase; the Register page will fail")
            else:
                line("FAIL", f"Auth endpoint returned {a.status_code}", "Check SUPABASE_ANON_KEY")
    except httpx.HTTPError as e:
        line("FAIL", f"Could not reach Supabase: {e.__class__.__name__}", "Check SUPABASE_URL and your internet connection")

if ok_gem:
    print("\n== Gemini ==")
    try:
        out = asyncio.run(GeminiService(s.gemini_api_key, s.gemini_model, timeout=30, max_retries=2).generate_json(
            "Reply only with JSON.", 'Return {"ok": true, "word": "civic"}', max_output_tokens=50))
        line("PASS", f"Gemini model `{s.gemini_model}` answered: {out}") if out.get("ok") else line("WARN", f"Gemini answered but unexpectedly: {out}")
    except AIError as e:
        line("FAIL", f"Gemini call failed: {e}", "Check GEMINI_API_KEY and GEMINI_MODEL (e.g. gemini-2.0-flash)")

print("\n== Result ==")
print("All required checks passed. Start the app: uvicorn app.main:app --reload --port 8000" if not bad else f"{bad} problem(s) found. Fix them and run this script again.")
sys.exit(1 if bad else 0)
