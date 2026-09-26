import logging
from typing import Optional
from fastapi import APIRouter, Request
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
                return user_doc
    except Exception as exc:
        logger.warning(f"User profile lookup notice: {exc}")

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
        "portal_name": "Overview — Dectus",
        "page_heading": "Overview",
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
    return templates.TemplateResponse(request=request, name="app/roles/company/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Company Executive Dashboard",
        "role_badge": "Company Admin",
        "user": user,
        "active_tab": "company"
    })


@app_router.get("/app/security", response_class=HTMLResponse)
@app_router.get("/portal/security", response_class=HTMLResponse)
async def serve_security_app(request: Request):
    """Tactical Threat Radar & Emergency Alert Queue"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    return templates.TemplateResponse(request=request, name="app/roles/security/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Tactical Threat Radar",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security"
    })


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


@app_router.get("/app/reviewer", response_class=HTMLResponse)
@app_router.get("/portal/reviewer", response_class=HTMLResponse)
async def serve_reviewer_app(request: Request):
    """Audio Forensic Review Queue & Model Disagreement Resolution"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    return templates.TemplateResponse(request=request, name="app/roles/reviewer/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audio Forensic Review Queue",
        "role_badge": "Forensic Reviewer",
        "user": user,
        "active_tab": "reviewer"
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

@app_router.get("/api/app/notifications")
async def get_app_notifications(request: Request):
    """Fetches broadcast notifications and system updates from MongoDB for the notification dropdown."""
    items = []
    try:
        db = await ensure_database()
        if db is not None:
            cursor = db.notifications.find({}, {"_id": 0}).sort("created_at", -1).limit(15)
            items = await cursor.to_list(length=15)
            for item in items:
                if "created_at" in item and hasattr(item["created_at"], "isoformat"):
                    item["created_at"] = item["created_at"].isoformat()
    except Exception as exc:
        logger.warning(f"Notifications fetch notice: {exc}")
    return {"status": "success", "notifications": items}


@app_router.post("/api/app/notifications")
async def create_admin_notification(request: Request):
    """Allows Admin / Company Admin to broadcast a system change or update to all users."""
    user = await get_authenticated_user(request)
    body = await request.json()
    title = str(body.get("title") or "System Configuration Updated").strip()
    description = str(body.get("description") or "An administrator updated acoustic detection rules and thresholds.").strip()
    tag = str(body.get("tag") or "Dectus Update").strip()

    from datetime import datetime
    import uuid
    doc = {
        "notification_id": f"NTF-{uuid.uuid4().hex[:6].upper()}",
        "title": title,
        "description": description,
        "tag": tag,
        "author": (user or {}).get("full_name", "Administrator"),
        "time_label": "Just now",
        "created_at": datetime.utcnow()
    }
    try:
        db = await ensure_database()
        if db is not None:
            await db.notifications.insert_one(dict(doc))
    except Exception as exc:
        logger.warning(f"Notification insert notice: {exc}")
    doc["created_at"] = doc["created_at"].isoformat()
    return {"status": "success", "notification": doc}


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
