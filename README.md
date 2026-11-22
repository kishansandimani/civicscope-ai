# CivicScope AI

*Making Public Information Clear, Accessible and Accountable.*

A voice-first public-information platform built on your Google Stitch frontend. Five AI modules plus a shared
voice assistant, with a FastAPI backend, Supabase (Postgres, Auth, Storage, Row Level Security) and Gemini.

| Module | What it does |
|---|---|
| **CivicProbe** | Crawls a public government site; reports broken links, stale dates, expired deadlines, missing titles/HTTPS, and AI-spotted outdated or incomplete information, each with evidence and affected URLs. |
| **InfoConflict** | Compares 2–5 sources (PDFs, pages, notices); shows conflicts side by side with quoted evidence and page numbers. Never decides which source is right. |
| **AccessShadow** | ~20 rule checks on web pages and PDFs (alt text, headings, labels, keyboard, zoom, language, PDF tagging). Automated findings are separate from items needing manual testing. |
| **RuleStress AI** | Tests a citizen's situation against a policy document. "Applies / does not apply" requires a verified quote, otherwise "not addressed". |
| **PromiseTrace** | Extracts commitments, deadlines and progress updates. A missing update is "no update found", never "failed". |
| **CivicVoice** | Speech-to-text, text-to-speech, spoken navigation, read-aloud, grounded Q&A over your reports, English / Hindi / Kannada. Every voice action also has a button or keyboard shortcut. |

---

## 1. Honest status

Built and **tested offline** (no network was available while developing): all backend logic (SSRF guard, chunking,
retrieval, prompt-injection defences, evidence grounding, the five engines, reporting, token verification) and the
frontend logic (voice-command parser, result renderer, CSV export) have automated tests with fake network objects.

**Not yet exercised against the real services.** The live Supabase calls, Gemini calls, real websites, PyMuPDF and the
browser UI have only been syntax-checked. That is what the two scripts in section 5 are for. Expect to fix small
integration details on the first run; the scripts tell you exactly what is wrong.

## 2. Prerequisites (Windows + VS Code)

- Python **3.11 or 3.12** (python.org; tick "Add Python to PATH")
- A **Supabase** account (free tier is fine) and a **Gemini API key** (https://aistudio.google.com/apikey)
- **Chrome or Edge** (voice input uses the Web Speech API; Firefox has no speech recognition, but typing works everywhere)
- Optional: Node 18+ to run the frontend tests

## 3. Supabase setup (about 5 minutes)

Menu names change occasionally; look for the closest equivalent.

1. Create a new project. Wait until it is ready.
2. **SQL Editor -> New query**, paste all of `supabase/schema.sql`, **Run**. This creates the 13 tables, indexes, triggers,
   Row Level Security policies and the private `civic-documents` storage bucket. It is safe to run twice.
3. **Project Settings -> API**: copy the **Project URL**, the **anon / public** key and the **service_role** key.
   The service_role key bypasses security: it goes only in `backend/.env`, never in frontend code, chat or Git.
4. **Authentication -> URL Configuration**: set Site URL `http://localhost:8000` and add Redirect URLs
   `http://localhost:8000/reset-password` and `http://localhost:8000/login`.
5. For a quick demo, **Authentication -> Providers -> Email -> turn off "Confirm email"**; otherwise new users must click
   an email link before signing in.

## 4. Run it

In a VS Code terminal (PowerShell) from the project root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass     # only if scripts are blocked
.\setup.ps1                                   # creates backend\.venv, installs packages, creates backend\.env
code backend\.env                             # paste your keys
.\run.ps1                                     # checks your setup, opens http://localhost:8000, starts the server
```

Or manually:

```powershell
cd backend
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env      # then edit it
python scripts\check_setup.py
uvicorn app.main:app --reload --port 8000
```

Open http://localhost:8000, **Register**, and you land on the Overview. API docs: http://localhost:8000/api/docs

`backend/.env`:

```
SUPABASE_URL=https://xxxx.supabase.co
SUPABASE_ANON_KEY=...
SUPABASE_SERVICE_ROLE_KEY=...
SUPABASE_JWT_SECRET=            # optional; blank is fine
GEMINI_API_KEY=...
GEMINI_MODEL=gemini-2.0-flash
```

## 5. Verify everything on your machine

```powershell
cd backend
python scripts\check_setup.py     # keys, tables, storage bucket, Gemini: PASS/FAIL with the fix for each
# in a second terminal: uvicorn app.main:app --port 8000
python scripts\e2e_check.py       # creates 2 temp users; tests auth, settings, upload, AccessShadow, reports,
                                  # SSRF blocking, and that user B CANNOT see user A's data (RLS). Cleans up after itself.
pip install pytest ; pytest       # 37 offline backend tests
cd ..\frontend ; npm test         # 37 offline frontend checks (needs: python backend\tests\make_samples.py once)
```

### Manual demo checklist
1. Register, sign in, refresh the page (session persists), sign out, sign back in. Try "Forgot password".
2. **Source Library**: upload a text-based PDF; add a public page by URL. A scanned PDF is rejected with a clear message.
3. **CivicProbe**: audit a government site with 3 pages; open the result, download CSV/Markdown, read aloud.
4. **InfoConflict**: select two sources about the same scheme; **RuleStress**: ask a situation; **PromiseTrace**: pick a budget speech or progress report.
5. **AccessShadow**: check a page URL and a PDF.
6. **CivicVoice** (Chrome/Edge): press Alt+V and say "go to reports", "read the latest report", "switch to Kannada". Try typing the same into the dock.
7. Accessibility Settings: high contrast, larger text, blind-friendly mode; reload and confirm they persist.

## 6. Architecture

```
civicscope-ai/
  frontend/                 your Stitch pages (static HTML + Tailwind CDN) + shared JS (no build step)
    pages/*.html            11 app pages + login/register/forgot/reset
    static/js/              shell, header, voice, voice-commands, render, csv, module-common, pages/*
    design/                 original Stitch screenshots and DESIGN.md
    tests/                  frontend checks (npm test)
  backend/
    app/main.py             FastAPI app: security headers, CORS, rate limit, serves frontend
    app/api/                account, civicprobe, infoconflict, accessshadow, rulestress, promisetrace, sources, reports, voice
    app/services/           gemini, fetcher, extract, chunking, retrieval, injection, grounding, the 5 engines, reporting, persist
    app/core/               config, tokens (auth verification), limiter
    app/utils/url_safety.py SSRF protection
    scripts/                check_setup.py, e2e_check.py
    tests/                  37 offline tests
  supabase/schema.sql       tables + RLS + storage (also in migrations/0001_init.sql)
```

The browser talks to Supabase **only for sign-in** (anon key, which is designed to be public). Everything else goes
through the FastAPI backend with the user's token; database reads/writes use a user-scoped client so Postgres RLS applies.

### API summary (full, interactive docs at `/api/docs`)

| Area | Endpoints |
|---|---|
| Account | `GET/PATCH /api/me`, `GET/PATCH /api/settings`, `GET /api/notifications`, `POST /api/notifications/read-all`, `GET /api/dashboard/stats` |
| Sources | `POST /api/sources/upload`, `POST /api/sources/url`, `GET /api/sources`, `GET/DELETE /api/sources/{id}` |
| Modules | `POST /api/civicprobe/analyze`, `POST /api/infoconflict/compare`, `POST /api/accessshadow/analyze`, `POST /api/rulestress/test`, `POST /api/promisetrace/analyze`, plus `GET` result lists |
| Reports | `GET /api/reports`, `GET/DELETE /api/reports/{id}`, `GET /api/reports/{id}/markdown`, `GET /api/reports/{id}/speakable` |
| Voice | `POST /api/voice/ask`, `POST /api/voice/translate` |
| Health | `GET /api/health` |

## 7. How the "never fabricate" rules are enforced (in code, not just prompts)

- Every AI quote is checked against the real source text; anything not found is dropped and counted in `ai_status.dropped_ungrounded`.
- Page numbers come from the source chunks, never from the AI.
- InfoConflict keeps a conflict only if two different sources still support different values after verification.
- RuleStress downgrades a definitive verdict with no verified evidence to "not addressed".
- PromiseTrace refuses on-track/delayed/completed without a verified progress quote; dates must be real calendar dates.
- Gemini-dependent modules return an error, not fake output, when no key is configured. CivicProbe and AccessShadow still run their automated checks.
- Website and document text is wrapped in a per-request random boundary, scanned for instruction-like text, and the system prompt tells the model it is data.

## 8. Security notes

SSRF guard on every fetch and redirect hop (blocks private, loopback, link-local, metadata and CGNAT ranges, odd ports, credentials in URLs);
file type + magic-byte + size checks; per-user storage folders; RLS on every table; rate limits; sanitised error messages;
secrets only in `backend/.env`; CSV export escapes formula injection; scraped text is rendered with `textContent`.
Not included: a Content-Security-Policy header (the Stitch pages rely on inline scripts and CDNs), DNS-rebinding pinning, and a CAPTCHA.

## 9. Known limitations

- Scanned PDFs (no text layer) are rejected; there is no OCR.
- CivicProbe uses plain HTTP fetching, not a headless browser, so JavaScript-rendered content is only partly visible. (Playwright is the upgrade path.)
- Large analyses run inside the request (up to ~150 s) rather than as background jobs.
- Hindi/Kannada: spoken commands cover core keywords; free questions go through Gemini. Recognition quality and installed voices depend on your browser and OS. The language picker sets voice/answer language; it does not translate the interface.
- Module result screens use a shared renderer in your palette, plainer than the original Stitch dashboards.
- Email notifications are not implemented (in-app only). The Overview shows counts from your own data only.

## 10. Troubleshooting

| Symptom | Fix |
|---|---|
| `check_setup` says tables missing | Run `supabase/schema.sql` in the SQL Editor |
| Register works but sign-in says "Email not confirmed" | Turn off "Confirm email" or click the email link |
| Pages show "Supabase is not configured" | `.env` not filled or server not restarted |
| Every API call returns 401 right after login | Check `SUPABASE_URL`/`SUPABASE_ANON_KEY` match the same project |
| `pip install` version conflict | Loosen the pin in `requirements.txt` for the named package |
| Voice mic does nothing | Use Chrome/Edge over `localhost`; allow the microphone; or use the typed box |
| No Hindi/Kannada voice | Install the language's speech voice in Windows Settings -> Time & language -> Speech |
