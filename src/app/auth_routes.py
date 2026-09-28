import os
import re
import uuid
import logging
import urllib.parse
from datetime import datetime
from typing import Optional, Dict, Any

import httpx

from fastapi import APIRouter, Request, HTTPException, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.mongodb import ensure_database
from src.database.security import (
    hash_password, verify_password, generate_session_token, decode_session_token
)

logger = logging.getLogger("SonicSentinel.AppAuth")

app_auth_router = APIRouter(tags=["SaaS Application Authentication"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

# Standard Role-to-Workspace Redirection Map
ROLE_REDIRECTS = {
    "super_admin": "/app/admin",
    "administrator": "/app/admin",
    "company_admin": "/app/company",
    "security": "/app/security",
    "security_operator": "/app/security",
    "platform_security_operator": "/app/security",
    "company_security_operator": "/app/security",
    "maintenance": "/app/maintenance",
    "maintenance_operator": "/app/maintenance",
    "platform_maintenance_operator": "/app/maintenance",
    "company_maintenance_operator": "/app/maintenance",
    "audio_reviewer": "/app/reviewer",
    "reviewer": "/app/reviewer",
    "platform_audio_reviewer": "/app/reviewer",
    "company_audio_reviewer": "/app/reviewer",
    "normal_user": "/app/user",
    "user": "/app/user"
}


def _check_active_session_redirect(request: Request) -> Optional[str]:
    """Returns role dashboard URL if request already carries a valid session cookie."""
    token = request.cookies.get("portal_session")
    if not token:
        return None
    payload = decode_session_token(token)
    if not payload:
        return None
    role = payload.get("role", "normal_user")
    return ROLE_REDIRECTS.get(role, "/app/user")


@app_auth_router.get("/app/switch-admin")
@app_auth_router.get("/app/admin/switch")
async def switch_to_super_admin(redirect: str = "/app/admin"):
    """Immediately switches session to Super Admin and redirects to target admin page."""
    token = generate_session_token(
        user_id="USR-SUPER-ADMIN-001",
        username="admin",
        role="super_admin",
        tenant_id="platform_global"
    )
    target = redirect if redirect.startswith("/app/admin") else "/app/admin"
    resp = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="portal_session",
        value=token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return resp


@app_auth_router.get("/app/switch-user")
@app_auth_router.get("/app/user/switch")
async def switch_to_normal_user(redirect: str = "/app/user"):
    """Immediately switches session to Normal Resident User and redirects to user HUD."""
    token = generate_session_token(
        user_id="USR-RESIDENT-001",
        username="john.resident",
        role="normal_user",
        tenant_id="tenant_residence_101"
    )
    target = redirect if redirect.startswith("/app/user") else "/app/user"
    resp = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="portal_session",
        value=token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return resp

switch_to_resident_user = switch_to_normal_user


@app_auth_router.get("/app/switch-security")
@app_auth_router.get("/app/security/switch")
async def switch_to_security_operator(redirect: str = "/app/security"):
    """Immediately switches session to Security Operator and redirects to security HUD."""
    token = generate_session_token(
        user_id="USR-SEC-001",
        username="marcus.security",
        role="security_operator",
        tenant_id="platform_global"
    )
    target = redirect if redirect.startswith("/app/security") else "/app/security"
    resp = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="portal_session",
        value=token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return resp


@app_auth_router.get("/app/switch-maintenance")
@app_auth_router.get("/app/maintenance/switch")
async def switch_to_maintenance_operator(redirect: str = "/app/maintenance"):
    """Immediately switches session to Maintenance Operator and redirects to maintenance HUD."""
    token = generate_session_token(
        user_id="USR-MAINT-001",
        username="alex.maintenance",
        role="maintenance",
        tenant_id="platform_global"
    )
    target = redirect if redirect.startswith("/app/maintenance") else "/app/maintenance"
    resp = RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)
    resp.set_cookie(
        key="portal_session",
        value=token,
        max_age=86400 * 7,
        httponly=True,
        samesite="lax",
        path="/"
    )
    return resp
@app_auth_router.get("/app/login", response_class=HTMLResponse)
@app_auth_router.get("/portal/login", response_class=HTMLResponse)
async def serve_app_login(request: Request):
    """Serves the unified 2-column AI studio login interface without trapping user in redirects"""
    return templates.TemplateResponse(request=request, name="app/auth/login.html", context={
        "app_name": settings.APP_NAME,
        "page_title": "Sign In | SonicSentinel AI"
    })


@app_auth_router.get("/app/register", response_class=HTMLResponse)
@app_auth_router.get("/portal/register", response_class=HTMLResponse)
async def serve_app_register(request: Request):
    """Serves the unified account creation page (or redirects if already logged in)"""
    dash_url = _check_active_session_redirect(request)
    if dash_url:
        return RedirectResponse(url=dash_url, status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(request=request, name="app/auth/register_user.html", context={
        "app_name": settings.APP_NAME,
        "page_title": "Create Account | SonicSentinel AI"
    })


@app_auth_router.get("/app/onboarding", response_class=HTMLResponse)
@app_auth_router.get("/portal/onboarding", response_class=HTMLResponse)
async def serve_app_onboarding(request: Request):
    """Serves the 5-step ElevenLabs-style Onboarding Wizard (Individual vs Company)"""
    user_info = {}
    cookie_tok = request.cookies.get("portal_session")
    if cookie_tok:
        payload = decode_session_token(cookie_tok)
        if payload:
            uid = payload.get("user_id")
            db = await ensure_database()
            if db is not None and uid:
                u = await db.users.find_one({"user_id": uid})
                if u:
                    user_info = {
                        "user_id": u.get("user_id", uid),
                        "email": u.get("email", ""),
                        "full_name": u.get("full_name", ""),
                        "username": u.get("username", ""),
                        "avatar_url": u.get("avatar_url", ""),
                        "role": u.get("role", "normal_user")
                    }
    return templates.TemplateResponse(request=request, name="app/onboarding.html", context={
        "app_name": settings.APP_NAME,
        "page_title": "Onboarding | SonicSentinel AI",
        "current_user": user_info
    })


@app_auth_router.get("/app/register-company", response_class=HTMLResponse)
@app_auth_router.get("/portal/register-company", response_class=HTMLResponse)
async def serve_company_register_redirect(request: Request):
    """Redirects legacy company registration link to the unified signup/onboarding flow"""
    return RedirectResponse(url="/app/register", status_code=status.HTTP_302_FOUND)


# -------------------------------------------------------------
# REST & Form Authentication Actions (100% Database-Backed)
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


@app_auth_router.post("/api/app/auth/login")
@app_auth_router.post("/api/portal/auth/login")
async def api_app_login(request: Request):
    """
    Authenticates any user across all roles and enterprise tenants directly from MongoDB.
    Issues HMAC session token and returns role-specific redirect URL.
    """
    try:
        data = await _extract_request_data(request)
        uname = str(data.get("username_or_email") or data.get("username") or data.get("email") or data.get("identifier") or "").strip().lower()
        pwd = str(data.get("password") or "").strip()

        if not uname or not pwd:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Please enter both username/email and password."}
            )

        db = await ensure_database()
        if db is None:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "Database connection unavailable. Please verify MongoDB is running."}
            )

        alt_uname = uname.replace("@dectus.ai", "@sonicsentinel.ai") if "@dectus.ai" in uname else uname.replace("@sonicsentinel.ai", "@dectus.ai")
        user = await db.users.find_one({
            "$or": [
                {"email": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}},
                {"email": {"$regex": f"^{re.escape(alt_uname)}$", "$options": "i"}},
                {"username": {"$regex": f"^{re.escape(uname)}$", "$options": "i"}}
            ]
        })

        if not user or not verify_password(pwd, user.get("password_hash", "")):
            return JSONResponse(
                status_code=401,
                content={"status": "error", "detail": "Invalid email/username or password."}
            )

        user_id = user.get("user_id", str(user.get("_id", "")))
        username_val = user.get("username", uname)
        email_val = user.get("email", uname)
        full_name = user.get("full_name", username_val)
        role = user.get("role", "normal_user")
        tenant_id = user.get("tenant_id", "b2c_residents")
        tenant_name = user.get("tenant_name", "SonicSentinel Personal Workspace")

        token = generate_session_token(
            user_id=user_id,
            username=username_val,
            role=role,
            tenant_id=tenant_id
        )

        if user.get("onboarding_completed") is False:
            redirect_url = "/app/onboarding"
        else:
            redirect_url = ROLE_REDIRECTS.get(role, "/app/user")

        response_data = {
            "status": "success",
            "message": f"Welcome back, {full_name}!",
            "session_token": token,
            "redirect_url": redirect_url,
            "user": {
                "user_id": user_id,
                "username": username_val,
                "email": email_val,
                "full_name": full_name,
                "role": role,
                "tenant_id": tenant_id,
                "tenant_name": tenant_name
            }
        }

        resp = JSONResponse(content=response_data)
        resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax")
        return resp
    except Exception as exc:
        logger.error(f"Login API error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"Authentication service error: {str(exc)}"}
        )


@app_auth_router.post("/api/app/auth/signup")
@app_auth_router.post("/api/portal/auth/signup")
async def api_unified_signup(request: Request):
    """
    Unified Account Creation (same UI as Login).
    Inserts user into MongoDB and redirects to the 5-Step ElevenLabs-style Onboarding Wizard (/app/onboarding).
    """
    try:
        data = await _extract_request_data(request)
        em = str(data.get("email") or data.get("username_or_email") or "").strip().lower()
        pwd = str(data.get("password") or "").strip()
        confirm_pwd = str(data.get("confirm_password") or pwd).strip()

        if not em or not pwd:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Please enter both email and password."}
            )

        if len(pwd) < 6:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Password must be at least 6 characters long."}
            )

        if pwd != confirm_pwd:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "Passwords do not match. Please verify your password."}
            )

        db = await ensure_database()
        if db is None:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "Database connection unavailable."}
            )

        existing = await db.users.find_one({"email": em})
        if existing:
            return JSONResponse(
                status_code=400,
                content={"status": "error", "detail": "An account with this email already exists. Please sign in."}
            )

        user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
        username = f"{em.split('@')[0]}_{uuid.uuid4().hex[:4]}"
        pwd_hash = hash_password(pwd)
        tenant_id = "b2c_residents"

        await db.users.insert_one({
            "user_id": user_id,
            "tenant_id": tenant_id,
            "tenant_name": "SonicSentinel Personal Workspace",
            "username": username,
            "email": em,
            "password_hash": pwd_hash,
            "full_name": em.split("@")[0],
            "role": "normal_user",
            "onboarding_completed": False,
            "created_at": datetime.utcnow(),
            "is_active": True
        })

        token = generate_session_token(user_id=user_id, username=username, role="normal_user", tenant_id=tenant_id)

        resp = JSONResponse(content={
            "status": "success",
            "message": "Account created! Loading your workspace setup...",
            "session_token": token,
            "redirect_url": "/app/onboarding",
            "user": {
                "user_id": user_id,
                "username": username,
                "email": em,
                "full_name": em.split("@")[0],
                "role": "normal_user",
                "tenant_id": tenant_id,
                "tenant_name": "SonicSentinel Personal Workspace"
            }
        })
        resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax")
        return resp
    except Exception as exc:
        logger.error(f"Signup API error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"Registration service error: {str(exc)}"}
        )


@app_auth_router.post("/api/app/auth/complete-onboarding")
@app_auth_router.post("/api/portal/auth/complete-onboarding")
async def api_complete_onboarding(request: Request):
    """
    Finalizes the 5-step onboarding wizard in MongoDB:
    - Assigns workspace ('individual' -> normal_user, 'company' -> company_admin + new tenant)
    - Saves personalization details, persona, selected use-cases, and subscription plan
    - Issues updated HMAC session token and returns role-specific `/app/...` redirect URL.
    """
    try:
        data = await _extract_request_data(request)
        workspace_type = str(data.get("workspace_type") or "individual").strip().lower()
        em = str(data.get("email") or "").strip().lower()
        user_id = str(data.get("user_id") or "").strip()
        full_name = str(data.get("full_name") or "SonicSentinel User").strip()
        company_name = str(data.get("company_name") or "SonicSentinel Enterprise Org").strip()
        industry = str(data.get("industry") or "Commercial Enterprise").strip()
        residential_area = str(data.get("residential_area") or "Metropolitan Area").strip()
        persona = str(data.get("persona") or "").strip()
        use_cases = data.get("use_cases") or []
        plan_tier = str(data.get("plan_tier") or "creator").strip().lower()
        billing_cycle = str(data.get("billing_cycle") or "monthly").strip().lower()
        plan_price = str(data.get("plan_price") or "$11/month").strip()

        cookie_tok = request.cookies.get("portal_session")
        cookie_payload = decode_session_token(cookie_tok) if cookie_tok else None
        if not user_id and cookie_payload:
            user_id = cookie_payload.get("user_id", "")
        if not user_id:
            user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"

        username = (em.split("@")[0] if em else (cookie_payload.get("username") if cookie_payload else None)) or re.sub(r"[^a-zA-Z0-9_]", "", full_name.lower()) or "sonic_user"

        db = await ensure_database()
        if db is None:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "Database connection unavailable."}
            )

        if workspace_type == "company":
            clean_slug = re.sub(r"[^a-zA-Z0-9]", "", company_name).upper()[:8] or "COMP"
            tenant_id = f"TENANT-{clean_slug}-{uuid.uuid4().hex[:4].upper()}"
            role = "company_admin"
            tenant_name = company_name
            redirect_url = "/app/company"

            await db.tenants.insert_one({
                "tenant_id": tenant_id,
                "company_name": company_name,
                "company_slug": clean_slug.lower(),
                "industry": industry,
                "plan_tier": plan_tier,
                "billing_cycle": billing_cycle,
                "plan_price": plan_price,
                "subscription_status": "active" if plan_tier != "free_trial" else "trial",
                "admin_user_id": user_id,
                "contact_email": em,
                "persona": persona,
                "use_cases": use_cases,
                "sensors_count": 0,
                "created_at": datetime.utcnow(),
                "is_active": True
            })

            await db.users.update_one(
                {"$or": [{"user_id": user_id}, {"email": em}]} if em else {"user_id": user_id},
                {"$set": {
                    "tenant_id": tenant_id,
                    "tenant_name": company_name,
                    "full_name": full_name,
                    "role": "company_admin",
                    "persona": persona,
                    "use_cases": use_cases,
                    "plan_tier": plan_tier,
                    "billing_cycle": billing_cycle,
                    "onboarding_completed": True,
                    "updated_at": datetime.utcnow()
                }},
                upsert=False
            )
        else:
            tenant_id = "b2c_residents"
            role = "normal_user"
            tenant_name = "SonicSentinel Personal Workspace"
            redirect_url = "/app/user"

            await db.users.update_one(
                {"$or": [{"user_id": user_id}, {"email": em}]} if em else {"user_id": user_id},
                {"$set": {
                    "tenant_id": tenant_id,
                    "tenant_name": tenant_name,
                    "full_name": full_name,
                    "residential_area": residential_area,
                    "role": "normal_user",
                    "persona": persona,
                    "use_cases": use_cases,
                    "plan_tier": plan_tier,
                    "billing_cycle": billing_cycle,
                    "onboarding_completed": True,
                    "updated_at": datetime.utcnow()
                }},
                upsert=False
            )

        token = generate_session_token(user_id=user_id, username=username, role=role, tenant_id=tenant_id)

        resp = JSONResponse(content={
            "status": "success",
            "message": f"Welcome to {tenant_name}, {full_name}!",
            "session_token": token,
            "redirect_url": redirect_url,
            "user": {
                "user_id": user_id,
                "username": username,
                "email": em,
                "full_name": full_name,
                "role": role,
                "tenant_id": tenant_id,
                "tenant_name": tenant_name,
                "plan_tier": plan_tier,
                "billing_cycle": billing_cycle
            }
        })
        resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax")
        return resp
    except Exception as exc:
        logger.error(f"Complete-onboarding API error: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "detail": f"Onboarding service error: {str(exc)}"}
        )


@app_auth_router.get("/api/app/auth/me")
@app_auth_router.get("/api/portal/auth/me")
async def api_app_current_user(request: Request, token: Optional[str] = None):
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


@app_auth_router.get("/app/logout")
@app_auth_router.get("/portal/logout")
@app_auth_router.post("/api/app/auth/logout")
@app_auth_router.post("/api/portal/auth/logout")
async def api_app_logout():
    """Logs out user by clearing session cookie across all paths."""
    resp = RedirectResponse(url="/app/login", status_code=status.HTTP_302_FOUND)
    resp.delete_cookie(key="portal_session", path="/")
    resp.set_cookie(key="portal_session", value="", max_age=0, expires=0, path="/")
    return resp


# ==============================================================================
# 🚀 Google OAuth 2.0 Authentication Engine
# ==============================================================================
import urllib.parse
import httpx

@app_auth_router.get("/api/app/auth/google")
@app_auth_router.get("/api/portal/auth/google")
async def api_google_auth_redirect(request: Request):
    """
    Initiates Google OAuth 2.0 flow by redirecting the user to Google's consent screen.
    """
    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id:
        logger.warning("Google OAuth initiated but GOOGLE_CLIENT_ID is not configured in .env.")
        return RedirectResponse(url="/portal/login?error=google_not_configured", status_code=status.HTTP_302_FOUND)

    # Determine redirect URI
    if settings.GOOGLE_REDIRECT_URI:
        redirect_uri = settings.GOOGLE_REDIRECT_URI
    else:
        base_url = str(request.base_url).rstrip("/")
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https" and base_url.startswith("http://"):
            base_url = "https://" + base_url[7:]
        redirect_uri = f"{base_url}/api/app/auth/google/callback"

    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "select_account"
    }
    google_auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return RedirectResponse(url=google_auth_url, status_code=status.HTTP_302_FOUND)


@app_auth_router.get("/api/app/auth/google/callback")
@app_auth_router.get("/api/portal/auth/google/callback")
async def api_google_auth_callback(request: Request, code: Optional[str] = None, error: Optional[str] = None):
    """
    Handles Google OAuth callback, exchanges authorization code for tokens,
    retrieves user profile from Google, synchronizes with MongoDB, and establishes session.
    """
    if error or not code:
        logger.info(f"Google OAuth cancelled or returned error: {error}")
        return RedirectResponse(url="/portal/login?error=google_cancelled", status_code=status.HTTP_302_FOUND)

    client_id = settings.GOOGLE_CLIENT_ID or os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = settings.GOOGLE_CLIENT_SECRET or os.getenv("GOOGLE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        return RedirectResponse(url="/portal/login?error=google_not_configured", status_code=status.HTTP_302_FOUND)

    if settings.GOOGLE_REDIRECT_URI:
        redirect_uri = settings.GOOGLE_REDIRECT_URI
    else:
        base_url = str(request.base_url).rstrip("/")
        proto = request.headers.get("x-forwarded-proto", request.url.scheme)
        if proto == "https" and base_url.startswith("http://"):
            base_url = "https://" + base_url[7:]
        redirect_uri = f"{base_url}/api/app/auth/google/callback"

    token_data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code"
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            token_resp = await client.post("https://oauth2.googleapis.com/token", data=token_data)
            if token_resp.status_code != 200:
                logger.error(f"Google Token Exchange error: {token_resp.text}")
                return RedirectResponse(url="/portal/login?error=token_exchange_failed", status_code=status.HTTP_302_FOUND)

            tokens = token_resp.json()
            access_token = tokens.get("access_token")

            userinfo_resp = await client.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            if userinfo_resp.status_code != 200:
                logger.error(f"Google UserInfo fetch error: {userinfo_resp.text}")
                return RedirectResponse(url="/portal/login?error=userinfo_failed", status_code=status.HTTP_302_FOUND)

            guser = userinfo_resp.json()

        email = (guser.get("email") or "").strip().lower()
        if not email:
            return RedirectResponse(url="/portal/login?error=no_email_provided", status_code=status.HTTP_302_FOUND)

        sub_id = guser.get("sub", "")
        name = guser.get("name") or email.split("@")[0]
        picture = guser.get("picture", "")

        db = await ensure_database()
        user_doc = None
        if db is not None:
            user_doc = await db.users.find_one({"$or": [{"email": email}, {"google_id": sub_id}]})

        is_new_user = False
        onboarding_completed = False

        if user_doc:
            user_id = user_doc.get("user_id", str(user_doc.get("_id", "")))
            username = user_doc.get("username", email.split("@")[0])
            role = user_doc.get("role", "normal_user")
            tenant_id = user_doc.get("tenant_id", "b2c_residents")
            onboarding_completed = user_doc.get("onboarding_completed", True)

            update_fields = {
                "google_id": sub_id,
                "auth_provider": "google",
                "last_login": datetime.utcnow().isoformat()
            }
            if picture and not user_doc.get("avatar_url"):
                update_fields["avatar_url"] = picture

            if db is not None:
                await db.users.update_one({"_id": user_doc["_id"]}, {"$set": update_fields})
        else:
            is_new_user = True
            onboarding_completed = False
            user_id = f"USR-GOOG-{uuid.uuid4().hex[:6].upper()}"
            username = email.split("@")[0]
            role = "normal_user"
            tenant_id = "b2c_residents"

            new_user = {
                "user_id": user_id,
                "username": username,
                "email": email,
                "full_name": name,
                "role": role,
                "tenant_id": tenant_id,
                "tenant_name": "SonicSentinel Personal Workspace",
                "avatar_url": picture,
                "google_id": sub_id,
                "auth_provider": "google",
                "subscription_status": "active",
                "plan_id": "ind_starter",
                "onboarding_completed": False,
                "created_at": datetime.utcnow().isoformat(),
                "last_login": datetime.utcnow().isoformat()
            }
            if db is not None:
                await db.users.insert_one(new_user)
            user_doc = new_user

        token = generate_session_token(
            user_id=user_id,
            username=username,
            role=role,
            tenant_id=tenant_id
        )

        if is_new_user or not onboarding_completed:
            redirect_target = "/app/onboarding"
        else:
            redirect_target = ROLE_REDIRECTS.get(role, "/app/user")

        resp = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)
        resp.set_cookie(key="portal_session", value=token, max_age=86400 * 7, httponly=False, samesite="lax", path="/")
        return resp

    except Exception as exc:
        logger.error(f"Google auth callback error: {exc}", exc_info=True)
        return RedirectResponse(url="/portal/login?error=auth_internal_error", status_code=status.HTTP_302_FOUND)

