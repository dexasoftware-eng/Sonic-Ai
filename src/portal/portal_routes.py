import logging
from typing import Optional
from fastapi import APIRouter, Request, HTTPException, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.security import decode_session_token

logger = logging.getLogger("SonicSentinel.PortalRouter")
portal_router = APIRouter(tags=["Portal SaaS Dashboards"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

def get_current_user_from_request(request: Request) -> Optional[dict]:
    """Helper to extract and decode session token from cookie or header."""
    token = request.cookies.get("portal_session")
    if not token:
        auth = request.headers.get("Authorization")
        if auth and auth.startswith("Bearer "):
            token = auth.split(" ")[1]
    if not token:
        return None
    return decode_session_token(token)

# -------------------------------------------------------------
# Role-Specific Dashboard Endpoints
# -------------------------------------------------------------

@portal_router.get("/portal/admin", response_class=HTMLResponse)
async def serve_super_admin_portal(request: Request):
    """Super Admin Global Command Center"""
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(request=request, name="portal/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Super Admin Global Command",
        "role_badge": "Super Administrator",
        "user": user or {"username": "Admin", "role": "super_admin", "tenant_name": "SonicSentinel Cloud HQ"},
        "active_tab": "admin"
    })

@portal_router.get("/portal/company", response_class=HTMLResponse)
async def serve_company_portal(request: Request):
    """Company Executive Dashboard & Staff Manager"""
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(request=request, name="portal/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Company Executive Dashboard",
        "role_badge": "Company Admin",
        "user": user or {"username": "Company Admin", "role": "company_admin", "tenant_name": "Enterprise Organization"},
        "active_tab": "company"
    })

@portal_router.get("/portal/security", response_class=HTMLResponse)
async def serve_security_portal(request: Request):
    """Tactical Threat Radar & Emergency Alert Queue"""
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(request=request, name="portal/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Tactical Threat Radar",
        "role_badge": "Security Operator",
        "user": user or {"username": "Security Officer", "role": "security_operator", "tenant_name": "Tactical Operations Center"},
        "active_tab": "security"
    })

@portal_router.get("/portal/maintenance", response_class=HTMLResponse)
async def serve_maintenance_portal(request: Request):
    """Machinery Health Monitor & Inspection Queue"""
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(request=request, name="portal/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Machinery Health Monitor",
        "role_badge": "Maintenance Operator",
        "user": user or {"username": "Plant Engineer", "role": "maintenance_operator", "tenant_name": "Plant Engineering Division"},
        "active_tab": "maintenance"
    })

@portal_router.get("/portal/reviewer", response_class=HTMLResponse)
async def serve_reviewer_portal(request: Request):
    """Audio Forensic Review Queue & Model Disagreement Resolution"""
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(request=request, name="portal/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audio Forensic Review Queue",
        "role_badge": "Forensic Reviewer",
        "user": user or {"username": "Acoustic Specialist", "role": "audio_reviewer", "tenant_name": "Forensic Acoustic QA"},
        "active_tab": "reviewer"
    })

@portal_router.get("/portal/user", response_class=HTMLResponse)
async def serve_normal_user_portal(request: Request):
    """Normal Resident Personal Safety Dashboard & Audio Scanner"""
    user = get_current_user_from_request(request)
    return templates.TemplateResponse(request=request, name="portal/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Resident Safety Dashboard",
        "role_badge": "Normal User / Resident",
        "user": user or {"username": "Resident", "role": "normal_user", "tenant_name": "Metropolitan Citizens"},
        "active_tab": "user"
    })
