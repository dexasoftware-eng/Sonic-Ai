import logging
import uuid
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.mongodb import ensure_database
from src.database.security import decode_session_token

logger = logging.getLogger("Dectus.AppRouter")
app_router = APIRouter(tags=["SaaS Application Role Dashboards"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

ROLE_TO_TAB = {
    "super_admin": ("admin", "Super Administrator"),
    "administrator": ("admin", "Super Administrator"),
    "company_admin": ("company", "Company Admin"),
    "security_operator": ("security", "Security Operator"),
    "platform_security_operator": ("security", "Security Operator"),
    "company_security_operator": ("security", "Security Operator"),
    "maintenance_operator": ("maintenance", "Maintenance Operator"),
    "platform_maintenance_operator": ("maintenance", "Maintenance Operator"),
    "company_maintenance_operator": ("maintenance", "Maintenance Operator"),
    "audio_reviewer": ("reviewer", "Forensic Reviewer"),
    "platform_audio_reviewer": ("reviewer", "Forensic Reviewer"),
    "company_audio_reviewer": ("reviewer", "Forensic Reviewer"),
    "normal_user": ("user", "Normal User / Resident"),
}


async def get_authenticated_user(request: Request) -> Optional[dict]:
    """Extracts session token from cookie or header and loads live user record from MongoDB."""
    token = request.cookies.get("portal_session")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]
    if not token:
        return None

    payload = decode_session_token(token)
    if not payload:
        return None

    try:
        db = await ensure_database()
        if db is not None:
            user_doc = await db.users.find_one({"user_id": payload.get("user_id")}, {"_id": 0, "password_hash": 0})
            if user_doc:
                if "dectus.ai" in str(user_doc.get("email", "")):
                    user_doc["email"] = user_doc["email"].replace("@dectus.ai", "@sonicsentinel.ai")
                if user_doc.get("tenant_name") in ["Dectus HQ", "asdasd", None]:
                    user_doc["tenant_name"] = "SonicSentinel Global HQ" if user_doc.get("role") in ["super_admin", "administrator"] else "Apex Enterprise Workspace"
                return user_doc
    except Exception as exc:
        logger.warning(f"User profile lookup notice: {exc}")

    if payload:
        if "dectus.ai" in str(payload.get("email", "")):
            payload["email"] = payload["email"].replace("@dectus.ai", "@sonicsentinel.ai")
    return payload


# -------------------------------------------------------------
# Role-Specific Workspace Endpoints (/app/* and /portal/*)
# -------------------------------------------------------------

@app_router.get("/app/admin", response_class=HTMLResponse)
@app_router.get("/portal/admin", response_class=HTMLResponse)
async def serve_super_admin_app(request: Request):
    """Super Admin Global Command Center"""
    from src.app.admin_routes import _load_admin_summary, _require_admin_or_redirect
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    return templates.TemplateResponse(request=request, name="app/roles/admin/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Platform Command Center",
        "page_heading": "Platform Command Center",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "dashboard",
        "summary": summary
    })


@app_router.get("/app/company", response_class=HTMLResponse)
@app_router.get("/portal/company", response_class=HTMLResponse)
async def serve_company_app(request: Request):
    """Company Executive Dashboard & Staff Manager"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    db = await ensure_database()
    from src.app.admin_routes import _load_admin_summary
    summary = await _load_admin_summary(db)
    return templates.TemplateResponse(request=request, name="app/roles/company/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Company Executive Dashboard",
        "role_badge": "Company Admin",
        "user": user,
        "active_tab": "company",
        "summary": summary
    })


# Security Role routes are comprehensively handled by src.app.security_routes (security_router)


@app_router.get("/app/maintenance", response_class=HTMLResponse)
@app_router.get("/portal/maintenance", response_class=HTMLResponse)
async def serve_maintenance_app(request: Request):
    """Machinery Health Monitor & Inspection Queue"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    return templates.TemplateResponse(request=request, name="app/roles/maintenance/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Machinery Health Monitor",
        "role_badge": "Maintenance Operator",
        "user": user,
        "active_tab": "maintenance"
    })


async def _fetch_reviewer_data(user, request: Request):
    """Loads and formats review records and calculates real KPIs for all reviewer modules."""
    db = await ensure_database()
    reviews = []
    if db is not None:
        tenant_id = user.get("tenant_id")
        query = {}
        if tenant_id and tenant_id not in ("platform_global", "super_admin"):
            query["tenant_id"] = tenant_id

        cursor = db.manual_reviews.find(query, {"_id": 0}).sort("created_at", -1).limit(60)
        reviews = await cursor.to_list(length=60)

    formatted_reviews = []
    for r in reviews:
        doc = dict(r)
        py_pred = doc.get("ai_python_prediction") or doc.get("python_prediction") or "Background Noise"
        py_conf = float(doc.get("ai_python_confidence") or doc.get("python_confidence") or 0.65)
        gtm_pred = doc.get("ai_gtm_prediction") or doc.get("gtm_prediction") or "Background Noise"
        gtm_conf = float(doc.get("ai_gtm_confidence") or doc.get("gtm_confidence") or 0.60)
        
        doc["python_prediction"] = py_pred
        doc["python_confidence"] = py_conf
        doc["gtm_prediction"] = gtm_pred
        doc["gtm_confidence"] = gtm_conf
        doc["confidence_gap"] = round(abs(py_conf - gtm_conf), 4)

        if "python_top3" not in doc or not doc["python_top3"]:
            doc["python_top3"] = [
                {"category": py_pred, "confidence": py_conf},
                {"category": "Background Noise" if py_pred != "Background Noise" else "Machinery Fault", "confidence": round(max(0.01, 1.0 - py_conf - 0.05), 4)},
                {"category": "Alarm or Siren" if py_pred != "Alarm or Siren" else "Vehicle Horn", "confidence": 0.04}
            ]
        if "gtm_top3" not in doc or not doc["gtm_top3"]:
            doc["gtm_top3"] = [
                {"category": gtm_pred, "confidence": gtm_conf},
                {"category": "Background Noise" if gtm_pred != "Background Noise" else "Gunshot", "confidence": round(max(0.01, 1.0 - gtm_conf - 0.05), 4)},
                {"category": "Glass Breaking" if gtm_pred != "Glass Breaking" else "Panic Scream", "confidence": 0.03}
            ]
        formatted_reviews.append(doc)

    total_count = len(formatted_reviews)
    pending_count = sum(1 for r in formatted_reviews if r.get("status") in ("Pending", "Pending Review"))
    disagreements_count = sum(1 for r in formatted_reviews if "Disagreement" in str(r.get("consistency_status", "")))
    low_conf_count = sum(1 for r in formatted_reviews if "Low Confidence" in str(r.get("consistency_status", "")) or (float(r.get("python_confidence", 1.0)) < 0.80))
    resolved_count = sum(1 for r in formatted_reviews if r.get("status") not in ("Pending", "Pending Review"))

    from src.models.model_pipeline import LABEL_DISPLAY_MAP
    categories = sorted(list(set(LABEL_DISPLAY_MAP.values())))

    target_id = request.query_params.get("case_id") or request.query_params.get("audio_id")
    active_case = None
    if target_id and formatted_reviews:
        for r in formatted_reviews:
            if r.get("review_id") == target_id or r.get("audio_id") == target_id:
                active_case = r
                break
    if not active_case and formatted_reviews:
        pending_cases = [r for r in formatted_reviews if r.get("status") in ("Pending", "Pending Review")]
        active_case = pending_cases[0] if pending_cases else formatted_reviews[0]

    kpi = {
        "total": total_count,
        "pending": pending_count,
        "disagreements": disagreements_count,
        "low_conf": low_conf_count,
        "resolved": resolved_count
    }
    return formatted_reviews, active_case, categories, kpi


@app_router.get("/app/reviewer", response_class=HTMLResponse)
@app_router.get("/portal/reviewer", response_class=HTMLResponse)
async def serve_reviewer_app(request: Request):
    """Audio Forensic Review Queue & Adjudication Studio"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)

    reviews, active_case, categories, kpi = await _fetch_reviewer_data(user, request)
    return templates.TemplateResponse(request=request, name="app/roles/reviewer/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audio Forensic Review Queue & Adjudication Studio",
        "role_badge": "Forensic Reviewer",
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "queue",
        "reviews": reviews,
        "active_case": active_case,
        "categories": categories,
        "kpi": kpi
    })


@app_router.get("/app/reviewer/workbench", response_class=HTMLResponse)
@app_router.get("/portal/reviewer/workbench", response_class=HTMLResponse)
async def serve_reviewer_workbench(request: Request):
    """Acoustic Oscilloscope, Spectrogram & Adjudication Workbench"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)

    reviews, active_case, categories, kpi = await _fetch_reviewer_data(user, request)
    return templates.TemplateResponse(request=request, name="app/roles/reviewer/workbench.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Acoustic Oscilloscope & Adjudication Workbench",
        "role_badge": "Forensic Reviewer",
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "workbench",
        "reviews": reviews,
        "active_case": active_case,
        "categories": categories,
        "kpi": kpi
    })


@app_router.get("/app/reviewer/disagreements", response_class=HTMLResponse)
@app_router.get("/portal/reviewer/disagreements", response_class=HTMLResponse)
async def serve_reviewer_disagreements(request: Request):
    """Dual-AI Model Disagreements & Variance Analysis"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)

    reviews, active_case, categories, kpi = await _fetch_reviewer_data(user, request)
    return templates.TemplateResponse(request=request, name="app/roles/reviewer/disagreements.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Dual-AI Model Disagreements & Variance Analysis",
        "role_badge": "Forensic Reviewer",
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "disagreements",
        "reviews": reviews,
        "active_case": active_case,
        "categories": categories,
        "kpi": kpi
    })


@app_router.get("/app/reviewer/resolved", response_class=HTMLResponse)
@app_router.get("/portal/reviewer/resolved", response_class=HTMLResponse)
async def serve_reviewer_resolved(request: Request):
    """Adjudicated Case History & Model Retraining Pool"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)

    reviews, active_case, categories, kpi = await _fetch_reviewer_data(user, request)
    return templates.TemplateResponse(request=request, name="app/roles/reviewer/resolved.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Adjudicated Case History & Model Retraining Pool",
        "role_badge": "Forensic Reviewer",
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "resolved",
        "reviews": reviews,
        "active_case": active_case,
        "categories": categories,
        "kpi": kpi
    })


@app_router.get("/app/reviewer/diagnostics", response_class=HTMLResponse)
@app_router.get("/portal/reviewer/diagnostics", response_class=HTMLResponse)
async def serve_reviewer_diagnostics(request: Request):
    """Acoustic Signal Diagnostics & Quality Inspector"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)

    reviews, active_case, categories, kpi = await _fetch_reviewer_data(user, request)
    return templates.TemplateResponse(request=request, name="app/roles/reviewer/diagnostics.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Acoustic Signal Diagnostics & Quality Inspector",
        "role_badge": "Forensic Reviewer",
        "user": user,
        "active_tab": "reviewer",
        "reviewer_page": "diagnostics",
        "reviews": reviews,
        "active_case": active_case,
        "categories": categories,
        "kpi": kpi
    })


@app_router.get("/app/user", response_class=HTMLResponse)
@app_router.get("/portal/user", response_class=HTMLResponse)
async def serve_normal_user_app(request: Request):
    """Normal Resident Personal Safety Dashboard & Audio Scanner"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    return templates.TemplateResponse(request=request, name="app/roles/user/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Resident Safety Dashboard",
        "role_badge": "Normal User / Resident",
        "user": user,
        "active_tab": "user"
    })


@app_router.get("/app/profile", response_class=HTMLResponse)
@app_router.get("/portal/profile", response_class=HTMLResponse)
async def serve_profile_page(request: Request):
    """Dedicated Profile & Account Settings Page"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    role_key = user.get("role", "normal_user")
    active_tab, role_badge = ROLE_TO_TAB.get(role_key, ("user", "Authenticated User"))
    return templates.TemplateResponse(request=request, name="app/profile.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Profile & Account Settings",
        "role_badge": role_badge,
        "user": user,
        "active_tab": active_tab
    })


@app_router.get("/portal/app/{subpath:path}")
async def redirect_legacy_portal_app_subpath(subpath: str):
    """Redirects accidental /portal/app/* paths cleanly to /app/*"""
    return RedirectResponse(url=f"/app/{subpath}", status_code=302)


# -------------------------------------------------------------
# Real-Time Notifications & Profile APIs (MongoDB Backed)
# -------------------------------------------------------------

def _format_relative_time(created_at: datetime) -> str:
    """Calculates human-readable relative time (e.g. Just now, 5m ago, 2h ago)."""
    now = datetime.utcnow()
    diff = (now - created_at).total_seconds()
    if diff < 60:
        return "Just now"
    elif diff < 3600:
        mins = int(diff // 60)
        return f"{mins}m ago"
    elif diff < 86400:
        hours = int(diff // 3600)
        return f"{hours}h ago"
    elif diff < 86400 * 7:
        days = int(diff // 86400)
        return f"{days}d ago"
    else:
        return created_at.strftime("%b %d, %Y")


@app_router.get("/api/app/notifications")
async def get_app_notifications(request: Request):
    """Fetches broadcast notifications and system updates from MongoDB for the notification dropdown."""
    user = await get_authenticated_user(request)
    items = []
    try:
        db = await ensure_database()
        if db is not None:
            user_role = (user or {}).get("role", "normal_user")
            user_tenant = (user or {}).get("tenant_id", "")
            
            # Admins see all notifications; other roles see role-targeted or universal broadcasts
            if user_role in ["super_admin", "administrator"]:
                query = {}
            else:
                query = {
                    "$or": [
                        {"target_role": {"$in": ["all", None, user_role]}},
                        {"target_role": {"$exists": False}}
                    ]
                }
                if user_tenant:
                    query["$and"] = [
                        {"$or": [
                            {"target_tenant_id": {"$in": ["all", None, user_tenant]}},
                            {"target_tenant_id": {"$exists": False}}
                        ]}
                    ]

            cursor = db.notifications.find(query, {"_id": 0}).sort("created_at", -1).limit(30)
            raw_items = await cursor.to_list(length=30)
            for item in raw_items:
                dt = item.get("created_at")
                if isinstance(dt, datetime):
                    item["time_label"] = _format_relative_time(dt)
                    item["created_at"] = dt.isoformat()
                elif isinstance(dt, str):
                    try:
                        clean_dt = dt.replace("Z", "+00:00")
                        parsed = datetime.fromisoformat(clean_dt).replace(tzinfo=None)
                        item["time_label"] = _format_relative_time(parsed)
                    except Exception:
                        item["time_label"] = item.get("time_label", "Recent")
                items.append(item)
    except Exception as exc:
        logger.warning(f"Notifications fetch notice: {exc}")
    return {"status": "success", "notifications": items, "count": len(items)}


@app_router.post("/api/app/notifications")
async def create_admin_notification(request: Request):
    """Allows Admin / Company Admin to broadcast a system directive or announcement to workspaces."""
    user = await get_authenticated_user(request)
    if not user or user.get("role") not in ["super_admin", "administrator", "company_admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized: Only Administrators can broadcast notifications.")
    
    body = await request.json()
    title = str(body.get("title") or "").strip()
    if not title:
        raise HTTPException(status_code=400, detail="Notification title is required.")
        
    description = str(body.get("description") or "").strip()
    category = str(body.get("category") or "announcement").strip().lower()
    priority = str(body.get("priority") or "normal").strip().lower()
    tag = str(body.get("tag") or "Broadcast").strip()
    target_role = str(body.get("target_role") or "all").strip().lower()
    target_tenant_id = str(body.get("target_tenant_id") or "all").strip()
    action_url = str(body.get("action_url") or "").strip()

    now = datetime.utcnow()
    doc = {
        "notification_id": f"NTF-{uuid.uuid4().hex[:6].upper()}",
        "title": title,
        "description": description,
        "category": category,
        "priority": priority,
        "tag": tag,
        "target_role": target_role,
        "target_tenant_id": target_tenant_id,
        "action_url": action_url,
        "author": user.get("full_name") or user.get("username") or "Administrator",
        "author_role": user.get("role"),
        "author_id": user.get("user_id"),
        "time_label": "Just now",
        "created_at": now
    }
    try:
        db = await ensure_database()
        if db is not None:
            await db.notifications.insert_one(dict(doc))
    except Exception as exc:
        logger.warning(f"Notification insert notice: {exc}")
    
    doc["created_at"] = now.isoformat()
    return {"status": "success", "notification": doc}


@app_router.delete("/api/app/notifications/{notification_id}")
async def delete_notification(notification_id: str, request: Request):
    """Allows Admin to remove an active broadcast from MongoDB."""
    user = await get_authenticated_user(request)
    if not user or user.get("role") not in ["super_admin", "administrator", "company_admin"]:
        raise HTTPException(status_code=403, detail="Unauthorized: Only Administrators can delete notifications.")
    
    try:
        db = await ensure_database()
        if db is not None:
            res = await db.notifications.delete_one({"notification_id": notification_id})
            if res.deleted_count > 0:
                return {"status": "success", "deleted_id": notification_id}
    except Exception as exc:
        logger.warning(f"Notification delete error: {exc}")
        
    return {"status": "error", "detail": "Notification not found or already deleted."}



@app_router.post("/api/app/profile")
async def update_user_profile(request: Request):
    """Updates user's full_name or avatar_url in MongoDB."""
    user = await get_authenticated_user(request)
    if not user:
        return {"status": "error", "message": "Not authenticated"}
    body = await request.json()
    full_name = str(body.get("full_name") or user.get("full_name") or "").strip()
    avatar_url = str(body.get("avatar_url") or user.get("avatar_url") or "").strip()

    try:
        db = await ensure_database()
        if db is not None and user.get("user_id"):
            await db.users.update_one(
                {"user_id": user["user_id"]},
                {"$set": {"full_name": full_name, "avatar_url": avatar_url}}
            )
    except Exception as exc:
        logger.warning(f"Profile update notice: {exc}")
    return {"status": "success", "full_name": full_name, "avatar_url": avatar_url}


# =============================================================================
# FORENSIC REVIEWER ADJUDICATION & CASE DETAIL APIs
# =============================================================================

@app_router.get("/api/app/reviewer/case/{review_id}")
async def api_reviewer_get_case_detail(review_id: str, request: Request):
    """Fetches real acoustic payload and Dual-AI outputs for Workbench display."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    db = await ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    rev = await db.manual_reviews.find_one({"review_id": review_id}, {"_id": 0})
    if not rev:
        raise HTTPException(status_code=404, detail="Review case not found.")

    audio_id = rev.get("audio_id") or "AUD-8001"
    ev = await db.audio_events.find_one({"audio_id": audio_id}, {"_id": 0}) if audio_id else None

    py_pred = rev.get("ai_python_prediction") or rev.get("python_prediction") or (ev.get("python_prediction") if ev else "Background Noise")
    py_conf = float(rev.get("ai_python_confidence") or rev.get("python_confidence") or (ev.get("python_confidence") if ev else 0.78))
    gtm_pred = rev.get("ai_gtm_prediction") or rev.get("gtm_prediction") or (ev.get("gtm_prediction") if ev else "Background Noise")
    gtm_conf = float(rev.get("ai_gtm_confidence") or rev.get("gtm_confidence") or (ev.get("gtm_confidence") if ev else 0.64))

    py_top3 = rev.get("python_top3") or (ev.get("python_top3") if ev else None) or [
        {"category": py_pred, "confidence": py_conf},
        {"category": "Background Noise" if py_pred != "Background Noise" else "Machinery Fault", "confidence": round(max(0.01, 1.0 - py_conf - 0.05), 4)},
        {"category": "Alarm or Siren" if py_pred != "Alarm or Siren" else "Vehicle Horn", "confidence": 0.04}
    ]

    gtm_top3 = rev.get("gtm_top3") or (ev.get("gtm_top3") if ev else None) or [
        {"category": gtm_pred, "confidence": gtm_conf},
        {"category": "Background Noise" if gtm_pred != "Background Noise" else "Gunshot", "confidence": round(max(0.01, 1.0 - gtm_conf - 0.05), 4)},
        {"category": "Glass Breaking" if gtm_pred != "Glass Breaking" else "Panic Scream", "confidence": 0.03}
    ]

    return {
        "status": "success",
        "case": {
            "review_id": rev.get("review_id"),
            "audio_id": audio_id,
            "tenant_id": rev.get("tenant_id", "platform_global"),
            "zone": rev.get("zone") or rev.get("zone_name", "North Perimeter Sensor"),
            "status": rev.get("status", "Pending Review"),
            "consistency_status": rev.get("consistency_status", "Model Disagreement"),
            "quality": rev.get("quality", "Good"),
            "snr_db": rev.get("snr_db", 24.5),
            "stream_url": f"/api/app/audio/{audio_id}/stream",
            "python_prediction": py_pred,
            "python_confidence": py_conf,
            "python_top3": py_top3,
            "gtm_prediction": gtm_pred,
            "gtm_confidence": gtm_conf,
            "gtm_top3": gtm_top3,
            "confidence_gap": round(abs(py_conf - gtm_conf), 4),
            "final_label": rev.get("final_label"),
            "reviewer_notes": rev.get("reviewer_notes") or ""
        }
    }


@app_router.post("/api/app/reviewer/adjudicate/{review_id}")
async def api_reviewer_adjudicate_verdict(review_id: str, request: Request):
    """Submits human ground-truth verdict, preserves AI audit trail, and optionally escalates to SOC."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")

    body = await request.json()
    decision_type = str(body.get("action") or body.get("decision_type") or "Confirmed").strip()
    final_label = str(body.get("final_label") or body.get("final_category") or "Gunshot").strip()
    reviewer_notes = str(body.get("notes") or body.get("reviewer_notes") or "").strip()
    escalate_to_soc = bool(body.get("escalate_to_soc", False))
    add_to_retrain = bool(body.get("add_to_retrain", True))

    db = await ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database connection failed.")

    rev_doc = await db.manual_reviews.find_one({"review_id": review_id})
    if not rev_doc:
        raise HTTPException(status_code=404, detail="Review case not found.")

    audio_id = rev_doc.get("audio_id", "")
    reviewer_name = user.get("full_name") or user.get("username", "Dr. Sarah (Forensic Reviewer)")

    # 1. Update manual_reviews document (Immutable AI output preserved)
    update_data = {
        "status": decision_type,
        "final_label": final_label,
        "decision_type": decision_type,
        "reviewer_notes": reviewer_notes,
        "reviewed_by": reviewer_name,
        "reviewed_at": datetime.utcnow().isoformat(),
        "retraining_eligible": add_to_retrain,
        "escalated_to_soc": escalate_to_soc
    }
    await db.manual_reviews.update_one({"review_id": review_id}, {"$set": update_data})

    # 2. Update parent audio_event if exists
    if audio_id:
        await db.audio_events.update_one(
            {"audio_id": audio_id},
            {"$set": {
                "lifecycle_status": f"Adjudicated ({decision_type})",
                "final_category": final_label,
                "forensic_adjudication": {
                    "reviewer": reviewer_name,
                    "decision": decision_type,
                    "final_class": final_label,
                    "notes": reviewer_notes,
                    "timestamp": datetime.utcnow().isoformat()
                }
            }}
        )

    # 3. If Escalated: Dispatch high-priority Tactical Alert for Security Operator
    if escalate_to_soc:
        alert_id = f"ALT-SOC-{uuid.uuid4().hex[:6].upper()}"
        zone = rev_doc.get("zone") or rev_doc.get("zone_name", "Forensic Review Escalation")
        alert_doc = {
            "alert_id": alert_id,
            "audio_id": audio_id,
            "tenant_id": rev_doc.get("tenant_id", user.get("tenant_id", "platform_global")),
            "sound_class": final_label,
            "severity": "Critical",
            "confidence": 1.0,
            "zone": zone,
            "status": "Open",
            "target_role": "security_operator",
            "escalated_by": reviewer_name,
            "escalation_notes": reviewer_notes,
            "created_at": datetime.utcnow()
        }
        await db.alerts.insert_one(alert_doc)

        # Broadcast live chime banner notification
        notif_doc = {
            "notification_id": f"notif_esc_{uuid.uuid4().hex[:8]}",
            "title": f"CRITICAL ESCALATION: {final_label}",
            "message": f"Forensic Reviewer verified {final_label} ({review_id}) at {zone}. Immediate tactical response requested.",
            "category": "security",
            "priority": "critical",
            "target_roles": ["security_operator", "super_admin", "company_admin"],
            "target_tenant": alert_doc["tenant_id"],
            "created_at": datetime.utcnow(),
            "read_by": []
        }
        await db.notifications.insert_one(notif_doc)

    # 4. Log Audit Trail
    await db.audit_logs.insert_one({
        "log_id": f"LOG-{uuid.uuid4().hex[:8].upper()}",
        "action": f"Forensic Adjudication: {decision_type}",
        "actor": reviewer_name,
        "role": user.get("role", "audio_reviewer"),
        "tenant_id": rev_doc.get("tenant_id", "platform_global"),
        "details": f"Review {review_id} (Audio {audio_id}) verified as '{final_label}' by reviewer. Notes: {reviewer_notes}",
        "created_at": datetime.utcnow()
    })

    return {
        "status": "success",
        "review_id": review_id,
        "final_label": final_label,
        "decision_type": decision_type,
        "escalated_to_soc": escalate_to_soc
    }
