"""End-to-end check against a RUNNING server and your real Supabase project.
    1) python scripts/check_setup.py   (must pass)
    2) uvicorn app.main:app --port 8000   (in another terminal)
    3) python scripts/e2e_check.py [http://127.0.0.1:8000]
Creates two throw-away users, exercises auth, settings, uploads, AccessShadow, reports, and verifies that user B
cannot see user A's data (Row Level Security). Users and their data are deleted at the end."""
import sys
import uuid

import httpx

sys.path.insert(0, ".")
from app.core.config import get_settings  # noqa: E402

s = get_settings()
APP = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")
SB = s.supabase_url.rstrip("/")
ADMIN = {"apikey": s.supabase_service_role_key, "Authorization": f"Bearer {s.supabase_service_role_key}"}
results = []


def check(name, cond, detail=""):
    results.append(cond)
    print(f"[{'PASS' if cond else 'FAIL'}] {name}" + (f"  ({detail})" if detail and not cond else ""))
    return cond


def make_user(tag):
    email, pw = f"civicscope-e2e-{tag}-{uuid.uuid4().hex[:8]}@example.com", "E2e-" + uuid.uuid4().hex
    r = httpx.post(f"{SB}/auth/v1/admin/users", headers=ADMIN, json={"email": email, "password": pw, "email_confirm": True}, timeout=20)
    r.raise_for_status()
    uid = r.json()["id"]
    t = httpx.post(f"{SB}/auth/v1/token?grant_type=password", headers={"apikey": s.supabase_anon_key}, json={"email": email, "password": pw}, timeout=20)
    t.raise_for_status()
    return {"id": uid, "email": email, "h": {"Authorization": f"Bearer {t.json()['access_token']}"}}


users = []
try:
    c = httpx.Client(base_url=APP, timeout=60)
    check("server health", c.get("/api/health").json().get("supabase_configured") is True)
    check("page /login served", c.get("/login").status_code == 200)
    check("unknown page is 404", c.get("/nope").status_code == 404)
    check("API rejects missing token", c.get("/api/me").status_code == 401)
    check("API rejects bad token", c.get("/api/me", headers={"Authorization": "Bearer garbage"}).status_code == 401)

    a, b = make_user("a"), make_user("b"); users += [a, b]
    r = c.get("/api/me", headers=a["h"]); check("profile auto-created at signup", r.status_code == 200 and r.json()["email"] == a["email"], r.text[:120])
    check("update profile", c.patch("/api/me", headers=a["h"], json={"full_name": "E2E Tester", "designation": "QA"}).json().get("full_name") == "E2E Tester")
    st = c.get("/api/settings", headers=a["h"]).json(); check("settings exist with defaults", st.get("speech_rate") == 1.0 or st.get("speech_rate") == 1)
    check("update settings", c.patch("/api/settings", headers=a["h"], json={"speech_rate": 1.4, "high_contrast": True}).json().get("speech_rate") == 1.4)
    check("settings validation rejects bad value", c.patch("/api/settings", headers=a["h"], json={"speech_rate": 9}).status_code == 422)
    d = c.get("/api/dashboard/stats", headers=a["h"]).json(); check("dashboard is empty for a new user (no fake data)", d["is_empty"] and d["totals"]["analyses"] == 0)

    html = b"<html><head><title>Test</title></head><body><h1>Pension scheme</h1><img src='a.png'><p>" + b"Citizens aged 60 or above are eligible. " * 30 + b"</p></body></html>"
    up = c.post("/api/sources/upload", headers=a["h"], files={"file": ("pension.html", html, "text/html")}); check("upload HTML source", up.status_code == 201, up.text[:160])
    sid = up.json().get("id")
    check("reject non-PDF disguised as PDF", c.post("/api/sources/upload", headers=a["h"], files={"file": ("fake.pdf", b"hello", "application/pdf")}).status_code == 400)
    check("reject unsupported type", c.post("/api/sources/upload", headers=a["h"], files={"file": ("x.exe", b"MZ....", "application/octet-stream")}).status_code == 400)
    check("duplicate upload blocked", c.post("/api/sources/upload", headers=a["h"], files={"file": ("pension2.html", html, "text/html")}).status_code == 409)
    check("source listed for owner", any(x["id"] == sid for x in c.get("/api/sources", headers=a["h"]).json()["items"]))
    check("source NOT visible to other user (RLS)", all(x["id"] != sid for x in c.get("/api/sources", headers=b["h"]).json()["items"]))
    check("other user cannot read source by id", c.get(f"/api/sources/{sid}", headers=b["h"]).status_code == 404)

    ar = c.post("/api/accessshadow/analyze", headers=a["h"], json={"source_id": sid}); check("AccessShadow on uploaded page", ar.status_code == 200, ar.text[:200])
    if ar.status_code == 200:
        rules = {f["rule"] for f in ar.json()["result"]["automated_findings"]}
        check("AccessShadow found the missing alt text and missing lang", {"img_missing_alt", "missing_lang"} <= rules, str(rules))
        rid = ar.json()["report_id"]
        check("report listed", any(x["id"] == rid for x in c.get("/api/reports", headers=a["h"]).json()["items"]))
        check("report markdown export", c.get(f"/api/reports/{rid}/markdown", headers=a["h"]).text.startswith("# "))
        check("report speakable text", len(c.get(f"/api/reports/{rid}/speakable", headers=a["h"]).json()["text"]) > 50)
        check("report NOT readable by other user (RLS)", c.get(f"/api/reports/{rid}", headers=b["h"]).status_code == 404)
        check("notification created", c.get("/api/notifications", headers=a["h"]).json()["unread"] >= 1)
    check("SSRF: localhost rejected", c.post("/api/civicprobe/analyze", headers=a["h"], json={"url": "http://127.0.0.1:8000/"}).status_code == 400)
    check("SSRF: cloud metadata rejected", c.post("/api/sources/url", headers=a["h"], json={"url": "http://169.254.169.254/latest/meta-data"}).status_code == 400)
    check("voice ask with no reports for user B is graceful", c.post("/api/voice/ask", headers=b["h"], json={"question": "what did you find", "language": "kn"}).json().get("grounded") is False)

    if s.gemini_configured:
        r = c.post("/api/rulestress/test", headers=a["h"], json={"source_id": sid, "scenario": "I am 58 years old. Can I get the pension?"})
        check("RuleStress (live Gemini)", r.status_code == 200 and r.json()["result"]["verdict"] in ("applies", "does_not_apply", "partially_applies", "not_addressed", "ambiguous"), r.text[:200])
        r = c.post("/api/voice/ask", headers=a["h"], json={"question": "Summarise my latest report", "language": "hi"}); check("voice ask (live Gemini, Hindi)", r.status_code == 200 and r.json().get("answer"), r.text[:160])
        r = c.post("/api/civicprobe/analyze", headers=a["h"], json={"url": "https://example.com", "max_pages": 2}); check("CivicProbe on example.com (live)", r.status_code == 200, r.text[:200])
    else:
        print("[SKIP] Gemini-dependent checks (GEMINI_API_KEY not set)")

    check("delete source", c.delete(f"/api/sources/{sid}", headers=a["h"]).status_code == 204)
finally:
    for u in users:
        try:
            httpx.delete(f"{SB}/auth/v1/admin/users/{u['id']}", headers=ADMIN, timeout=20)
        except Exception:
            print(f"[WARN] could not delete test user {u['email']}; remove it in Supabase -> Authentication")
    print(f"\n{sum(results)}/{len(results)} checks passed")
    sys.exit(0 if all(results) else 1)
