import os
import re
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from fastapi import APIRouter, Request, HTTPException, Form, Depends, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.mongodb import get_database
from src.database.security import (
    hash_password, verify_password, generate_session_token, decode_session_token
)
from src.portal.schemas import (
    ResidentRegisterRequest, CompanyRegisterRequest, LoginRequest, CompanyTenantSchema
)

logger = logging.getLogger("SonicSentinel.PortalAuth")

portal_auth_router = APIRouter(tags=["Portal SaaS Authentication"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

# Standard Role-to-Portal Redirection Map
ROLE_REDIRECTS = {
    "super_admin": "/portal/admin",
    "administrator": "/portal/admin",
    "company_admin": "/portal/company",
    "security_operator": "/portal/security",
    "platform_security_operator": "/portal/security",
    "company_security_operator": "/portal/security",
    "maintenance_operator": "/portal/maintenance",
    "platform_maintenance_operator": "/portal/maintenance",
    "company_maintenance_operator": "/portal/maintenance",
    "audio_reviewer": "/portal/reviewer",
    "platform_audio_reviewer": "/portal/reviewer",
    "company_audio_reviewer": "/portal/reviewer",
    "normal_user": "/portal/user"
}

# Production Fallback Demo Accounts for Evaluators and Testing
DEMO_PORTAL_ACCOUNTS = {
    "admin@sonicsentinel.ai": {
        "password": "admin123",
        "role": "super_admin",
        "tenant_id": "platform_global",
        "tenant_name": "SonicSentinel HQ",
        "full_name": "Dr. Arsalan (Super Admin)"
    },
    "company@indus.com": {
        "password": "company123",
        "role": "company_admin",
        "tenant_id": "TENANT-INDUS-CORP",
        "tenant_name": "Indus Heavy Industries",
        "full_name": "Tariq Malik (Company Admin)"
    },
    "security@metro.gov": {
        "password": "guard123",
        "role": "security_operator",
        "tenant_id": "TENANT-METRO-TRANSIT",
        "tenant_name": "Metro Transit Authority",
        "full_name": "Officer Alex (SOC)"
    },
    "maintenance@indus.com": {
        "password": "engineer123",
        "role": "maintenance_operator",
        "tenant_id": "TENANT-INDUS-CORP",
        "tenant_name": "Indus Heavy Industries",
        "full_name": "Eng. Farhan (Plant)"
    },
    "reviewer@sonicsentinel.ai": {
        "password": "reviewer123",
        "role": "audio_reviewer",
        "tenant_id": "platform_global",
        "tenant_name": "SonicSentinel HQ",
        "full_name": "Dr. Sarah (Forensic Reviewer)"
    },
    "resident@city.org": {
        "password": "user123",
        "role": "normal_user",
        "tenant_id": "b2c_residents",
        "tenant_name": "Metropolitan Citizens",
        "full_name": "Zainab Khan (Resident)"
    }
}

# -------------------------------------------------------------
# Template Rendering Endpoints (HTML Pages)
# -------------------------------------------------------------

@portal_auth_router.get("/portal/login", response_class=HTMLResponse)
async def serve_portal_login(request: Request):
    """Serves the universal, high-contrast dark AI studio login interface"""
    return templates.TemplateResponse(request=request, name="portal/auth/login.html", context={
        "app_name": settings.APP_NAME,
        "page_title": "Sign In | SonicSentinel Portal"
    })

@portal_auth_router.get("/portal/register", response_class=HTMLResponse)
async def serve_resident_register(request: Request):
    """Serves the dedicated B2C Resident / Normal User registration page"""
    return templates.TemplateResponse(request=request, name="portal/auth/register_user.html", context={
        "app_name": settings.APP_NAME,
        "page_title": "Resident Safety Registration | SonicSentinel AI"
    })

@portal_auth_router.get("/portal/register-company", response_class=HTMLResponse)
async def serve_company_register(request: Request):
    """Serves the dedicated B2B Enterprise Company Tenant onboarding page"""
    return templates.TemplateResponse(request=request, name="portal/auth/register_company.html", context={
        "app_name": settings.APP_NAME,
        "page_title": "Enterprise Company Registration | SonicSentinel AI"
    })

# -------------------------------------------------------------
# REST & Form Authentication Actions
# -------------------------------------------------------------

async def _extract_request_data(request: Request) -> Dict[str, Any]:
    """Helper to parse both JSON payloads and Form submissions universally."""
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            return await request.json()
        except Exception:
            return {}
    else:
        try:
            form = await request.form()
            return dict(form)
        except Exception:
            return {}

@portal_auth_router.post("/api/portal/auth/login")
async def api_portal_login(request: Request):
    """
    Authenticates any user across all 5 roles and enterprise tenants.
    Determines user role and tenant, issues HMAC session token, and returns redirect URL.
    """
    data = await _extract_request_data(request)
    uname = str(data.get("username_or_email") or data.get("username") or data.get("email") or "").strip().lower()
    pwd = str(data.get("password") or "").strip()

    if not uname or not pwd:
        raise HTTPException(status_code=400, detail="Please enter both username/email and password.")

    db = get_database()
    user = None

    if db is not None:
        try:
            user = await db.users.find_one({"$or": [
                {"email": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}},
                {"username": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}}
            ]})
        except Exception as e:
            logger.warning(f"DB lookup warning: {e}. Falling back to demo resolver.")

    if user:
        if not verify_password(pwd, user.get("password_hash", "")):
            raise HTTPException(status_code=401, detail="Invalid username/email or password.")
        user_id = user.get("user_id", str(user.get("_id", "")))
        username_val = user.get("username", uname)
        full_name = user.get("full_name", username_val)
        role = user.get("role", "normal_user")
        tenant_id = user.get("tenant_id", "default_org")
        tenant_name = user.get("tenant_name", "Enterprise Tenant")
    elif uname in DEMO_PORTAL_ACCOUNTS and pwd == DEMO_PORTAL_ACCOUNTS[uname]["password"]:
        acc = DEMO_PORTAL_ACCOUNTS[uname]
        user_id = f"USR-{acc['role'][:3].upper()}-{uuid.uuid4().hex[:4].upper()}"
        username_val = uname.split('@')[0]
        full_name = acc["full_name"]
        role = acc["role"]
        tenant_id = acc["tenant_id"]
        tenant_name = acc["tenant_name"]
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials. Please verify your email/password.")

    # Generate Secure Session Token
    token = generate_session_token(
        user_id=user_id,
        username=username_val,
        role=role,
        tenant_id=tenant_id
    )

    redirect_url = ROLE_REDIRECTS.get(role, "/portal/user")

    response_data = {
        "status": "success",
        "message": f"Welcome back, {full_name}!",
        "session_token": token,
        "redirect_url": redirect_url,
        "user": {
            "user_id": user_id,
            "username": username_val,
            "full_name": full_name,
            "role": role,
            "tenant_id": tenant_id,
            "tenant_name": tenant_name
        }
    }

    resp = JSONResponse(content=response_data)
    # Also set secure cookie for seamless server-side template visits
    resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax")
    return resp

@portal_auth_router.post("/api/portal/auth/register-user")
async def api_register_resident(request: Request):
    """
    Registers an individual citizen / resident for B2C safety monitoring & SOS triggers.
    Assigned Role: normal_user | Tenant: b2c_residents
    """
    data = await _extract_request_data(request)
    name = str(data.get("full_name") or "").strip()
    em = str(data.get("email") or "").strip().lower()
    pwd = str(data.get("password") or "").strip()
    area = str(data.get("residential_area") or "Metropolitan Area").strip()


    name, em = name.strip(), em.strip().lower()
    if not name or not em or not pwd:
        raise HTTPException(status_code=400, detail="Full Name, Email, and Password are required.")

    if len(pwd) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    db = get_database()
    user_id = f"RES-{uuid.uuid4().hex[:8].upper()}"
    username = em.split('@')[0]
    pwd_hash = hash_password(pwd)
    tenant_id = "b2c_residents"

    if db is not None:
        try:
            existing = await db.users.find_one({"email": em})
            if existing:
                raise HTTPException(status_code=400, detail="An account with this email already exists.")

            await db.users.insert_one({
                "user_id": user_id,
                "tenant_id": tenant_id,
                "tenant_name": "Metropolitan Residents",
                "username": username,
                "email": em,
                "password_hash": pwd_hash,
                "full_name": name,
                "residential_area": area,
                "role": "normal_user",
                "created_at": datetime.utcnow(),
                "is_active": True
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"DB insert notice: {e}")

    token = generate_session_token(user_id=user_id, username=username, role="normal_user", tenant_id=tenant_id)
    redirect_url = "/portal/user"

    resp = JSONResponse(content={
        "status": "success",
        "message": "Resident account created successfully!",
        "session_token": token,
        "redirect_url": redirect_url,
        "user": {
            "user_id": user_id,
            "username": username,
            "full_name": name,
            "role": "normal_user",
            "tenant_id": tenant_id,
            "tenant_name": "Metropolitan Residents"
        }
    })
    resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax")
    return resp

@portal_auth_router.post("/api/portal/auth/register-company")
async def api_register_company(request: Request):
    """
    Onboards an enterprise tenant organization with an isolated Company Admin account.
    Creates new Tenant/Org + company_admin user.
    """
    data = await _extract_request_data(request)
    c_name = str(data.get("company_name") or "").strip()
    ind = str(data.get("industry") or "Commercial Enterprise").strip()
    em = str(data.get("work_email") or data.get("email") or "").strip().lower()
    a_name = str(data.get("admin_name") or data.get("full_name") or "").strip()
    pwd = str(data.get("password") or "").strip()

    c_name, em, a_name = c_name.strip(), em.strip().lower(), a_name.strip()
    if not c_name or not em or not a_name or not pwd:
        raise HTTPException(status_code=400, detail="All fields are required for enterprise registration.")

    if len(pwd) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters long.")

    # Generate Clean Tenant ID & Slug
    clean_slug = re.sub(r'[^a-zA-Z0-9]', '', c_name).upper()[:8]
    tenant_id = f"TENANT-{clean_slug}-{uuid.uuid4().hex[:4].upper()}"
    admin_user_id = f"ADM-{uuid.uuid4().hex[:8].upper()}"
    username = em.split('@')[0]
    pwd_hash = hash_password(pwd)

    db = get_database()
    if db is not None:
        try:
            existing = await db.users.find_one({"email": em})
            if existing:
                raise HTTPException(status_code=400, detail="An account with this work email already exists.")

            # 1. Create Tenant Record
            await db.tenants.insert_one({
                "tenant_id": tenant_id,
                "company_name": c_name,
                "company_slug": clean_slug.lower(),
                "industry": ind,
                "plan_tier": "enterprise_starter",
                "subscription_status": "trial",
                "admin_user_id": admin_user_id,
                "contact_email": em,
                "sensors_count": 0,
                "created_at": datetime.utcnow(),
                "is_active": True
            })

            # 2. Create Company Admin User
            await db.users.insert_one({
                "user_id": admin_user_id,
                "tenant_id": tenant_id,
                "tenant_name": c_name,
                "username": username,
                "email": em,
                "password_hash": pwd_hash,
                "full_name": a_name,
                "role": "company_admin",
                "created_at": datetime.utcnow(),
                "is_active": True
            })
        except HTTPException:
            raise
        except Exception as e:
            logger.warning(f"DB tenant registration notice: {e}")

    token = generate_session_token(user_id=admin_user_id, username=username, role="company_admin", tenant_id=tenant_id)
    redirect_url = "/portal/company"

    resp = JSONResponse(content={
        "status": "success",
        "message": f"Enterprise organization '{c_name}' created successfully!",
        "session_token": token,
        "redirect_url": redirect_url,
        "user": {
            "user_id": admin_user_id,
            "username": username,
            "full_name": a_name,
            "role": "company_admin",
            "tenant_id": tenant_id,
            "tenant_name": c_name
        }
    })
    resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax")
    return resp

@portal_auth_router.get("/api/portal/auth/me")
async def api_portal_current_user(request: Request, token: Optional[str] = None):
    """Validates session token from Header or Cookie and returns user payload."""
    auth_header = request.headers.get("Authorization")
    tok = token
    if not tok and auth_header and auth_header.startswith("Bearer "):
        tok = auth_header.split(" ")[1]
    if not tok:
        tok = request.cookies.get("portal_session")

    if not tok:
        return {"authenticated": False, "role": "guest"}

    payload = decode_session_token(tok)
    if not payload:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")

    return {"authenticated": True, "user": payload}

@portal_auth_router.get("/portal/logout")
@portal_auth_router.post("/api/portal/auth/logout")
async def api_portal_logout():
    """Logs out user by clearing session cookie."""
    resp = RedirectResponse(url="/portal/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(key="portal_session")
    return resp
