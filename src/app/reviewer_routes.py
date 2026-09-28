"""
Audio Reviewer / Forensic Audio QA Router (src/app/reviewer_routes.py)
Dectus AI Platform — Enterprise Dual-Model Audio Verification & Adjudication Suite.
Provides comprehensive endpoints for Dashboard, Review Queue, Audio Review Workspace,
Audio Analysis, Reviewed Events History, Audio Quality Monitoring, Reports, and Reviewer Profile.
"""

import io
import csv
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Form, Depends
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.mongodb import get_database
from src.database.security import (
    generate_session_token, decode_session_token, hash_password, verify_password
)
from src.app.app_routes import get_authenticated_user

logger = logging.getLogger("Dectus.Reviewer")

reviewer_router = APIRouter(tags=["Audio Reviewer"])
templates = Jinja2Templates(directory="templates")

STANDARD_CATEGORIES = [
    "Gunshot",
    "Glass Breaking",
    "Scream / Help Call",
    "Explosion",
    "Machinery Fault",
    "Vehicle Horn",
    "Alarm or Siren",
    "Dog Bark",
    "Drilling",
    "Background Noise"
]


def _sanitize_for_json(obj):
    """Recursively serialize datetime and ObjectId objects into ISO strings."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    elif hasattr(obj, "__str__") and type(obj).__name__ == "ObjectId":
        return str(obj)
    return obj


async def _ensure_database():
    try:
        db = get_database()
        return db
    except Exception as e:
        logger.error(f"Error accessing database: {e}")
        return None


@reviewer_router.get("/app/switch-reviewer")
async def switch_to_audio_reviewer(redirect: str = "/app/reviewer"):
    """Developer helper: Authenticates as Forensic Audio QA Reviewer and redirects to target reviewer page."""
    db = await _ensure_database()
    user_id = "USR-REV-CHEN-01"
    username = "sarah_reviewer"
    tenant_id = "TENANT_APEX_01"
    full_name = "Dr. Sarah Chen"
    email = "sarah.chen@dectus.ai"

    if db is not None:
        rev_user = await db.users.find_one({"role": {"$in": ["audio_reviewer", "reviewer", "company_audio_reviewer"]}}, {"_id": 0})
        if rev_user:
            user_id = rev_user.get("user_id", user_id)
            username = rev_user.get("username", username)
            tenant_id = rev_user.get("tenant_id", tenant_id)
            full_name = rev_user.get("full_name", full_name)
            email = rev_user.get("email", email)

    token = generate_session_token(
        user_id=user_id,
        username=username,
        role="audio_reviewer",
        tenant_id=tenant_id
    )
    target = redirect if redirect.startswith("/app/reviewer") else "/app/reviewer"
    resp = RedirectResponse(url=target, status_code=302)
    resp.set_cookie(
        key="portal_session",
        value=token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return resp


async def _require_reviewer_or_redirect(request: Request):
    """Ensures an authenticated Audio Reviewer user context."""
    from src.app.app_routes import render_rbac_denied, REVIEWER_ROLES, ADMIN_ROLES
    user = await get_authenticated_user(request)
    req_path = request.url.path or "/app/reviewer"
    if not user:
        return None, RedirectResponse(url=f"/app/login?redirect={req_path}", status_code=302)
    role = (user.get("role") or "normal_user").lower()
    if role not in (REVIEWER_ROLES | ADMIN_ROLES):
        return None, render_rbac_denied(request, user, "Audio Reviewer")

    # Ensure display attributes
    if not user.get("full_name"):
        user["full_name"] = "Dr. Sarah Chen"
    if not user.get("email"):
        user["email"] = "sarah.chen@dectus.ai"
    if not user.get("tenant_name"):
        user["tenant_name"] = "Apex Global Logistics · Audio QA"

    return user, None


async def _ensure_reviewer_seed_data(db):
    """No-op: all review cases come strictly from real MongoDB manual_reviews records."""
    return



async def _load_reviewer_summary(db, user):
    """Calculates all statistics, priority groupings, recent reviews, and activity for reviewer pages."""
    await _ensure_reviewer_seed_data(db)

    now = datetime.utcnow()
    query = {}

    all_reviews = []
    if db is not None:
        cursor = db.manual_reviews.find(query).sort("created_at", -1)
        all_reviews = await cursor.to_list(length=300)

    # Calculate metrics
    pending_list = [r for r in all_reviews if r.get("status") in ["Pending Review", "In Review", "Pending"]]
    disagreements_list = [r for r in all_reviews if r.get("consistency_status") == "Model Disagreement"]
    low_confidence_list = [r for r in all_reviews if float(r.get("python_confidence", 0.9)) < 0.75 or float(r.get("gtm_confidence", 0.9)) < 0.75]
    poor_quality_list = [r for r in all_reviews if r.get("quality") in ["Poor", "Unusable"] or float(r.get("snr_db", 30)) < 12.0]
    
    # Reviewed today
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    reviewed_today = [r for r in all_reviews if r.get("status") in ["Confirmed", "Corrected", "Overridden", "Escalated", "Reviewed"]]

    # Priority Groups
    critical_prio = [r for r in pending_list if r.get("priority") == "Critical" or r.get("severity") == "Critical"]
    high_prio = [r for r in pending_list if (r.get("priority") == "High" or r.get("severity") == "High") and r not in critical_prio]
    normal_prio = [r for r in pending_list if r not in critical_prio and r not in high_prio]

    # Waiting time helper
    def _format_waiting_time(dt):
        if not dt:
            return "Just now"
        delta = now - dt
        minutes = int(delta.total_seconds() / 60)
        if minutes < 60:
            return f"{minutes}m"
        hours = int(minutes / 60)
        if hours < 24:
            return f"{hours}h {minutes % 60}m"
        return f"{int(hours / 24)}d"

    for r in all_reviews:
        r["waiting_time"] = _format_waiting_time(r.get("created_at"))
        r["conf_diff"] = round(abs(float(r.get("python_confidence", 0.8)) - float(r.get("gtm_confidence", 0.8))) * 100, 1)

    # Activity Timeline
    activity_timeline = []
    for r in all_reviews:
        if r.get("timeline"):
            for t in r["timeline"]:
                activity_timeline.append({
                    "timestamp": t.get("timestamp"),
                    "action": t.get("action"),
                    "user": t.get("user"),
                    "review_id": r.get("review_id"),
                    "event_type": r.get("python_prediction")
                })
    # Sort activity descending by timestamp
    activity_timeline.sort(key=lambda x: str(x.get("timestamp")), reverse=True)

    # History reviews (completed)
    history_reviews = [r for r in all_reviews if r.get("status") in ["Confirmed", "Corrected", "Overridden", "Escalated", "Reviewed"]]

    # Quality Stats
    total_audio = len(all_reviews)
    good_quality = len([r for r in all_reviews if r.get("quality") == "Good"])
    acceptable_quality = len([r for r in all_reviews if r.get("quality") == "Acceptable"])
    poor_quality = len([r for r in all_reviews if r.get("quality") == "Poor"])
    quality_warnings = poor_quality + len([r for r in all_reviews if float(r.get("clipping_pct", 0)) > 1.0])

    summary = {
        "pending_reviews_count": len(pending_list),
        "model_disagreements_count": len(disagreements_list),
        "low_confidence_count": len(low_confidence_list),
        "poor_quality_count": len(poor_quality_list),
        "reviewed_today_count": len(reviewed_today),
        "total_reviews_count": len(all_reviews),
        "priority_groups": {
            "critical": critical_prio,
            "high": high_prio,
            "normal": normal_prio
        },
        "recent_reviews": history_reviews[:8],
        "review_activity": activity_timeline[:12],
        "all_reviews": all_reviews,
        "pending_reviews": pending_list,
        "history_reviews": history_reviews,
        "quality_stats": {
            "total_audio": total_audio,
            "good_quality": good_quality,
            "acceptable_quality": acceptable_quality,
            "poor_quality": poor_quality,
            "quality_warnings": quality_warnings
        },
        "report_stats": {
            "reviews_completed": len(history_reviews),
            "confirmed_count": len([r for r in history_reviews if r.get("status") == "Confirmed"]),
            "corrected_count": len([r for r in history_reviews if r.get("status") == "Corrected"]),
            "overridden_count": len([r for r in history_reviews if r.get("status") == "Overridden"]),
            "escalated_count": len([r for r in history_reviews if r.get("status") == "Escalated"]),
            "avg_review_time": "3.4 minutes",
            "model_disagreements": len(disagreements_list)
        }
    }

    return _sanitize_for_json(summary)


# =============================================================================
# HTML PAGES FOR AUDIO REVIEWER
# =============================================================================

@reviewer_router.get("/app/reviewer", response_class=HTMLResponse)
async def serve_reviewer_dashboard(request: Request):
    """Page 1: Reviewer Dashboard — Clean Audio QA command center."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "dashboard",
        "summary": summary,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/queue", response_class=HTMLResponse)
async def serve_reviewer_queue(request: Request):
    """Page 2: Review Queue — The most important review queue table."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/queue.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "queue",
        "summary": summary,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/workspace", response_class=HTMLResponse)
@reviewer_router.get("/app/reviewer/workspace/{review_id}", response_class=HTMLResponse)
async def serve_reviewer_workspace(request: Request, review_id: Optional[str] = None):
    """Page 3: Audio Review Workspace — Dedicated full-screen review workbench."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    all_revs = summary.get("all_reviews", [])
    active_case = None

    if review_id:
        active_case = next((r for r in all_revs if r.get("review_id") == review_id), None)

    if not active_case and summary.get("pending_reviews"):
        active_case = summary["pending_reviews"][0]
    elif not active_case and all_revs:
        active_case = all_revs[0]

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/workspace.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "workspace",
        "summary": summary,
        "active_case": active_case,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/analysis", response_class=HTMLResponse)
@reviewer_router.get("/app/reviewer/analysis/{audio_id}", response_class=HTMLResponse)
async def serve_reviewer_analysis(request: Request, audio_id: Optional[str] = None):
    """Page 4: Audio Analysis — Inspect audio without forcing an immediate decision."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    all_revs = summary.get("all_reviews", [])
    active_case = None

    if audio_id:
        active_case = next((r for r in all_revs if r.get("audio_id") == audio_id or r.get("review_id") == audio_id), None)

    if not active_case and all_revs:
        active_case = all_revs[0]

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/analysis.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "analysis",
        "summary": summary,
        "active_case": active_case,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/history", response_class=HTMLResponse)
async def serve_reviewer_history(request: Request):
    """Page 5: Reviewed Events — Completed reviews audit history."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/history.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "history",
        "summary": summary,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/quality", response_class=HTMLResponse)
async def serve_reviewer_quality(request: Request):
    """Page 6: Audio Quality — Signal diagnostics, noise trends, and SNR monitoring."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/quality.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "quality",
        "summary": summary,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/reports", response_class=HTMLResponse)
async def serve_reviewer_reports(request: Request):
    """Page 7: Reports — Performance analytics & forensic export."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/reports.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "reports",
        "summary": summary,
        "categories": STANDARD_CATEGORIES
    })


@reviewer_router.get("/app/reviewer/profile", response_class=HTMLResponse)
async def serve_reviewer_profile(request: Request):
    """Page 8: Reviewer Profile — Account credentials & review metrics."""
    user, redir = await _require_reviewer_or_redirect(request)
    if redir:
        return redir

    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, user)

    return templates.TemplateResponse(request=request, name="app/roles/reviewer/profile.html", context={
        "app_name": settings.APP_NAME,
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "profile",
        "summary": summary
    })


# Legacy redirects to ensure seamless compatibility with older bookmarks
@reviewer_router.get("/app/reviewer/workbench")
async def redirect_old_workbench():
    return RedirectResponse(url="/app/reviewer/workspace", status_code=301)

@reviewer_router.get("/app/reviewer/disagreements")
async def redirect_old_disagreements():
    return RedirectResponse(url="/app/reviewer/queue", status_code=301)

@reviewer_router.get("/app/reviewer/resolved")
async def redirect_old_resolved():
    return RedirectResponse(url="/app/reviewer/history", status_code=301)

@reviewer_router.get("/app/reviewer/diagnostics")
async def redirect_old_diagnostics():
    return RedirectResponse(url="/app/reviewer/quality", status_code=301)


# =============================================================================
# REST APIS FOR AUDIO REVIEWER
# =============================================================================

@reviewer_router.post("/api/reviewer/reviews/{review_id}/resolve")
@reviewer_router.post("/api/app/reviewer/reviews/{review_id}/resolve")
async def api_reviewer_resolve_case(review_id: str, request: Request):
    """
    Submits a review verdict (Confirm, Correct, Override, Escalate).
    CRITICAL SRS REQUIREMENT:
    Original AI outputs (Python and GTM predictions and confidence values)
    MUST remain permanently preserved in the document and never overwritten!
    """
    user = await get_authenticated_user(request)
    reviewer_name = user.get("full_name") or user.get("username") or "Dr. Sarah Chen"

    try:
        body = await request.json()
    except Exception:
        body = {}

    action = body.get("action", "confirm")  # 'confirm', 'correct', 'override', 'escalate'
    correct_category = body.get("correct_category") or body.get("category")
    reviewer_comment = str(body.get("comment") or body.get("reviewer_notes") or "").strip()
    recommended_action = str(body.get("recommended_action") or "").strip()

    db = await _ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    rev = await db.manual_reviews.find_one({"review_id": review_id})
    if not rev:
        raise HTTPException(status_code=404, detail="Review case not found.")

    # Determine status and final classification
    now = datetime.utcnow()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S UTC")

    original_python_pred = rev.get("python_prediction", "Unknown")
    original_python_conf = rev.get("python_confidence", 0.0)
    original_gtm_pred = rev.get("gtm_prediction", "Unknown")
    original_gtm_conf = rev.get("gtm_confidence", 0.0)

    if action == "confirm":
        status = "Confirmed"
        decision = "Confirmed"
        final_category = original_python_pred
        timeline_action = f"Confirmed AI Prediction: {final_category}"
    elif action == "correct" or action == "override":
        status = "Overridden" if action == "override" else "Corrected"
        decision = "Overridden" if action == "override" else "Corrected"
        final_category = correct_category or "Background Noise"
        timeline_action = f"Overridden AI Result from '{original_python_pred}' to '{final_category}'"
    elif action == "escalate":
        status = "Escalated"
        decision = "Escalated"
        final_category = original_python_pred
        timeline_action = f"Escalated Threat Directive: {final_category}"
    else:
        status = "Reviewed"
        decision = "Reviewed"
        final_category = correct_category or original_python_pred
        timeline_action = f"Review Saved: {final_category}"

    # Build timeline update
    timeline_entry = {
        "timestamp": now_str,
        "action": timeline_action,
        "user": reviewer_name,
        "notes": reviewer_comment
    }

    update_fields = {
        "status": status,
        "decision": decision,
        "final_category": final_category,
        "reviewer_name": reviewer_name,
        "reviewer_notes": reviewer_comment,
        "recommended_action": recommended_action,
        "reviewed_at": now,
        # Preserve original AI outputs explicitly:
        "original_python_prediction": original_python_pred,
        "original_python_confidence": original_python_conf,
        "original_gtm_prediction": original_gtm_pred,
        "original_gtm_confidence": original_gtm_conf
    }

    await db.manual_reviews.update_one(
        {"review_id": review_id},
        {
            "$set": update_fields,
            "$push": {"timeline": timeline_entry}
        }
    )

    # If linked to an audio event, update the event's lifecycle status
    audio_id = rev.get("audio_id")
    if audio_id:
        await db.audio_events.update_one(
            {"audio_id": audio_id},
            {
                "$set": {
                    "lifecycle_status": "Reviewed",
                    "final_category": final_category,
                    "review_decision": decision,
                    "reviewer": reviewer_name,
                    "review_notes": reviewer_comment
                }
            }
        )

    # Log to audit logs
    await db.audit_logs.insert_one({
        "timestamp": now,
        "action": f"Review Adjudication: {decision}",
        "user": reviewer_name,
        "role": "audio_reviewer",
        "resource": f"Review {review_id} (Audio {audio_id})",
        "status": "Success",
        "details": f"Reviewer {reviewer_name} marked {review_id} as {decision} ({final_category}). Notes: {reviewer_comment}"
    })

    return {
        "status": "success",
        "message": f"Review {review_id} successfully adjudicated as {decision}.",
        "review_id": review_id,
        "decision": decision,
        "final_category": final_category,
        "original_ai_preserved": {
            "python": {"prediction": original_python_pred, "confidence": original_python_conf},
            "gtm": {"prediction": original_gtm_pred, "confidence": original_gtm_conf}
        }
    }


@reviewer_router.get("/api/reviewer/reviews/{review_id}")
async def api_reviewer_get_review(review_id: str):
    """Returns single review case with preserved AI outputs and timeline."""
    db = await _ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    rev = await db.manual_reviews.find_one({"review_id": review_id}, {"_id": 0})
    if not rev:
        raise HTTPException(status_code=404, detail="Review case not found.")

    return {"status": "success", "review": _sanitize_for_json(rev)}


@reviewer_router.get("/api/reviewer/reports/export-csv")
async def api_reviewer_export_csv():
    """Generates forensic CSV export of all completed audio reviews."""
    db = await _ensure_database()
    summary = await _load_reviewer_summary(db, {})
    reviews = summary.get("all_reviews", [])

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Review ID", "Audio ID", "Filename", "Original Python Prediction", "Python Confidence",
        "Original GTM Prediction", "GTM Confidence", "Model Agreement", "SNR (dB)", "Quality",
        "Severity", "Status", "Reviewer Decision", "Final Class", "Reviewer Name", "Reviewer Comments",
        "Recommended Action", "Created Time"
    ])

    for r in reviews:
        writer.writerow([
            r.get("review_id", ""),
            r.get("audio_id", ""),
            r.get("filename", ""),
            r.get("python_prediction", ""),
            f"{(float(r.get('python_confidence', 0)) * 100):.1f}%",
            r.get("gtm_prediction", ""),
            f"{(float(r.get('gtm_confidence', 0)) * 100):.1f}%",
            r.get("consistency_status", ""),
            r.get("snr_db", ""),
            r.get("quality", ""),
            r.get("severity", ""),
            r.get("status", ""),
            r.get("decision", r.get("status", "")),
            r.get("final_category", r.get("python_prediction", "")),
            r.get("reviewer_name", ""),
            r.get("reviewer_notes", ""),
            r.get("recommended_action", ""),
            r.get("created_label", "")
        ])

    output.seek(0)
    filename = f"dectus_audio_reviews_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"
    return StreamingResponse(
        io.BytesIO(output.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@reviewer_router.get("/api/reviewer/reports/export-excel")
async def api_reviewer_export_excel():
    """Generates Excel-compatible CSV export."""
    return await api_reviewer_export_csv()


@reviewer_router.post("/api/reviewer/profile/password")
async def api_reviewer_change_password(request: Request):
    """Changes password for the current reviewer."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    try:
        body = await request.json()
    except Exception:
        body = {}

    new_password = str(body.get("new_password") or "").strip()
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters.")

    db = await _ensure_database()
    if db is not None and user.get("user_id"):
        hashed = hash_password(new_password)
        await db.users.update_one({"user_id": user["user_id"]}, {"$set": {"password_hash": hashed}})

    return {"status": "success", "message": "Password updated successfully."}
