"""Shared persistence helpers for every module. All calls use the user-scoped client, so RLS applies."""
from datetime import datetime, timezone


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def start_analysis(db, user_id: str, module: str, title: str, input_summary: dict) -> str:
    row = db.table("analyses").insert({"user_id": user_id, "module": module, "title": title[:200],
                                       "status": "running", "input_summary": input_summary,
                                       "started_at": _now()}).execute().data[0]
    return row["id"]


def finish_analysis(db, analysis_id: str, ok: bool, error: str | None = None) -> None:
    db.table("analyses").update({"status": "completed" if ok else "failed", "error_message": error,
                                 "completed_at": _now()}).eq("id", analysis_id).execute()


def save_report(db, user_id: str, analysis_id: str, module: str, title: str, summary: str,
                severity_counts: dict, body: dict) -> str:
    row = db.table("reports").insert({"user_id": user_id, "analysis_id": analysis_id, "module": module,
                                      "title": title[:200], "summary": summary, "severity_counts": severity_counts,
                                      "body": body}).execute().data[0]
    return row["id"]


def notify(db, user_id: str, kind: str, title: str, message: str, link: str | None = None) -> None:
    prefs = db.table("user_settings").select("notify_in_app").eq("user_id", user_id).limit(1).execute().data
    if prefs and prefs[0].get("notify_in_app") is False:      # respect the user's notification setting
        return
    db.table("notifications").insert({"user_id": user_id, "kind": kind, "title": title[:200],
                                      "message": message[:500], "link": link}).execute()
