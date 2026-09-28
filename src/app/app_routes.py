import io
import csv
import uuid
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse, Response
from fastapi.templating import Jinja2Templates

from config.settings import settings
from src.database.mongodb import ensure_database
from src.database.security import decode_session_token

logger = logging.getLogger("SonicSentinel.AppRouter")
app_router = APIRouter(tags=["SaaS Application Role Dashboards"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

ROLE_TO_TAB = {
    "super_admin": ("admin", "Super Administrator"),
    "administrator": ("admin", "Super Administrator"),
    "company_admin": ("company", "Company Admin"),
    "security": ("security", "Security Operator"),
    "security_operator": ("security", "Security Operator"),
    "platform_security_operator": ("security", "Security Operator"),
    "company_security_operator": ("security", "Security Operator"),
    "maintenance": ("maintenance", "Maintenance Operator"),
    "maintenance_operator": ("maintenance", "Maintenance Operator"),
    "platform_maintenance_operator": ("maintenance", "Maintenance Operator"),
    "company_maintenance_operator": ("maintenance", "Maintenance Operator"),
    "audio_reviewer": ("reviewer", "Forensic Reviewer"),
    "reviewer": ("reviewer", "Forensic Reviewer"),
    "platform_audio_reviewer": ("reviewer", "Forensic Reviewer"),
    "company_audio_reviewer": ("reviewer", "Forensic Reviewer"),
    "normal_user": ("user", "Normal User"),
    "user": ("user", "Normal User"),
}

NORMAL_USER_ROLES = {"normal_user", "user"}
SECURITY_ROLES = {"security", "security_operator", "platform_security_operator", "company_security_operator"}
MAINTENANCE_ROLES = {"maintenance", "maintenance_operator", "platform_maintenance_operator", "company_maintenance_operator"}
ADMIN_ROLES = {"super_admin", "administrator"}
COMPANY_ROLES = {"company_admin"}
REVIEWER_ROLES = {"audio_reviewer", "reviewer", "platform_audio_reviewer", "company_audio_reviewer"}


def get_role_home_and_terminal(role: str) -> Tuple[str, str, str]:
    """Returns (home_url, terminal_url, role_label) for any role string."""
    r = (role or "normal_user").lower()
    if r in SECURITY_ROLES:
        return "/app/security", "/app/security/terminal", "Security"
    if r in MAINTENANCE_ROLES:
        return "/app/maintenance", "/app/maintenance/terminal", "Maintenance"
    if r in ADMIN_ROLES:
        return "/app/admin", "/app/admin", "Super Admin"
    if r in COMPANY_ROLES:
        return "/app/company", "/app/company", "Company Admin"
    if r in REVIEWER_ROLES:
        return "/app/reviewer", "/app/reviewer", "Audio Reviewer"
    return "/app/user", "/app/user/terminal", "Normal User"


def render_rbac_denied(request: Request, user: Dict[str, Any], required_role_label: str) -> HTMLResponse:
    """Renders a 403 Forbidden HTML response when a role attempts to access another role's routes."""
    role = (user or {}).get("role", "normal_user")
    home_url, terminal_url, current_role_label = get_role_home_and_terminal(role)
    return templates.TemplateResponse(
        request=request,
        name="app/access_denied.html",
        status_code=403,
        context={
            "app_name": settings.APP_NAME,
            "user": user,
            "current_role_label": current_role_label,
            "required_role_label": required_role_label,
            "home_url": home_url,
            "terminal_url": terminal_url,
            "message": f"Access Denied: Your account role ({current_role_label}) is not authorized to access {required_role_label} pages or terminals."
        }
    )


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
                # Preserve token role if switched via /app/switch-*
                if payload.get("role"):
                    user_doc["role"] = payload.get("role")
                return user_doc
    except Exception as exc:
        logger.warning(f"User profile lookup notice: {exc}")

    return payload


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


def _format_timestamp_label(dt_val: Any) -> str:
    if isinstance(dt_val, datetime):
        return dt_val.strftime("%Y-%m-%d %H:%M:%S UTC")
    if isinstance(dt_val, str) and dt_val:
        return dt_val.replace("T", " ")[:19] + " UTC"
    return "Recent"


USER_ROLE_RECORD_LIMIT = 25
USER_ROLE_MAX_UPLOAD_MB = 15


async def _load_operational_role_summary(db, user: Dict[str, Any], role_group: str) -> Tuple[Dict[str, Any], Dict[str, int]]:
    """
    Loads 100% real MongoDB data for Normal User, Security, or Maintenance portal pages.
    Enforces strict multi-tenant isolation for company employees so they only see their company's data.
    """
    events: List[Dict[str, Any]] = []
    critical_events: List[Dict[str, Any]] = []
    alerts: List[Dict[str, Any]] = []
    notifications: List[Dict[str, Any]] = []
    equipment: List[Dict[str, Any]] = []

    is_normal_user = (role_group == "user")
    record_limit = USER_ROLE_RECORD_LIMIT if is_normal_user else 100
    alert_limit = USER_ROLE_RECORD_LIMIT if is_normal_user else 100
    notif_limit = 20 if is_normal_user else 40

    user_tenant = str((user or {}).get("tenant_id") or "").strip()
    is_company_employee = bool(user_tenant and user_tenant not in ("platform_global", "b2c_residents", "tenant_residence_101"))

    if db is not None:
        if is_company_employee:
            try:
                from src.app.company_routes import _ensure_company_seed_data
                await _ensure_company_seed_data(db, user_tenant, (user or {}).get("tenant_name") or "Enterprise Workspace")
            except Exception as exc:
                logger.warning(f"Company seed check notice: {exc}")
            tenant_query: Dict[str, Any] = {"tenant_id": user_tenant}
            notif_query: Dict[str, Any] = {
                "$or": [
                    {"tenant_id": user_tenant},
                    {"target_tenant_id": user_tenant}
                ]
            }
        else:
            tenant_query = {}
            notif_query = {}

        try:
            raw_events = await db.audio_events.find(tenant_query, {"_id": 0}).sort("created_at", -1).limit(record_limit).to_list(length=record_limit)
            for ev in raw_events:
                d = dict(ev)
                py_pred = d.get("python_prediction") or "Ambient"
                py_conf = float(d.get("python_confidence") or 0.0)
                gtm_pred = d.get("gtm_prediction") or "Ambient"
                gtm_conf = float(d.get("gtm_confidence") or 0.0)
                py_pct = round(py_conf * 100, 1) if py_conf <= 1.0 else round(py_conf, 1)
                gtm_pct = round(gtm_conf * 100, 1) if gtm_conf <= 1.0 else round(gtm_conf, 1)
                sev = d.get("severity") or "Low"
                d["python_prediction"] = py_pred
                d["python_confidence"] = py_conf if py_conf <= 1.0 else py_conf / 100.0
                d["python_conf_pct"] = py_pct
                d["gtm_prediction"] = gtm_pred
                d["gtm_confidence"] = gtm_conf if gtm_conf <= 1.0 else gtm_conf / 100.0
                d["gtm_conf_pct"] = gtm_pct
                d["severity"] = sev
                d["consistency_status"] = d.get("consistency_status") or ("Acceptable Match" if py_pred == gtm_pred else "Model Disagreement")
                d["snr_db"] = round(float(d.get("snr_db") or 0.0), 1)
                d["quality"] = d.get("quality") or "Good"
                d["duration_seconds"] = round(float(d.get("duration_seconds") or 2.0), 1)
                d["sample_rate"] = int(d.get("sample_rate") or 16000)
                d["created_label"] = _format_timestamp_label(d.get("created_at"))
                if hasattr(d.get("created_at"), "isoformat"):
                    d["created_at"] = d["created_at"].isoformat()
                events.append(d)
                if sev in ("Critical", "High"):
                    critical_events.append(d)
        except Exception as exc:
            logger.warning(f"Audio events query notice: {exc}")

        try:
            raw_alerts = await db.alerts.find(tenant_query, {"_id": 0}).sort("created_at", -1).limit(alert_limit).to_list(length=alert_limit)
            for al in raw_alerts:
                a = dict(al)
                conf = float(a.get("confidence") or a.get("python_confidence") or 0.0)
                conf_pct = round(conf * 100, 1) if conf <= 1.0 else round(conf, 1)
                a["alert_id"] = a.get("alert_id") or f"ALT-{str(a.get('audio_id', '0000'))[-4:]}"
                a["sound_category"] = a.get("sound_category") or a.get("sound_class") or a.get("category") or a.get("python_prediction") or "Acoustic Alert"
                a["severity"] = a.get("severity") or "High"
                a["confidence"] = conf if conf <= 1.0 else conf / 100.0
                a["conf_pct"] = conf_pct
                a["status"] = a.get("status") or "Open"
                a["created_label"] = _format_timestamp_label(a.get("created_at"))
                if hasattr(a.get("created_at"), "isoformat"):
                    a["created_at"] = a["created_at"].isoformat()
                alerts.append(a)
        except Exception as exc:
            logger.warning(f"Alerts query notice: {exc}")

        try:
            raw_notifs = await db.notifications.find(notif_query, {"_id": 0}).sort("created_at", -1).limit(notif_limit).to_list(length=notif_limit)
            for n in raw_notifs:
                nd = dict(n)
                dt = nd.get("created_at")
                if isinstance(dt, datetime):
                    nd["time_label"] = _format_relative_time(dt)
                    nd["created_at"] = dt.isoformat()
                else:
                    nd["time_label"] = nd.get("time_label") or _format_timestamp_label(dt)
                nd["description"] = nd.get("description") or nd.get("message") or ""
                notifications.append(nd)
        except Exception as exc:
            logger.warning(f"Notifications query notice: {exc}")

        try:
            raw_eq = await db.equipment.find(tenant_query, {"_id": 0}).sort("created_at", -1).limit(50).to_list(length=50)
            for eq in raw_eq:
                ed = dict(eq)
                ed["equipment_id"] = ed.get("equipment_id") or ed.get("sensor_id") or "EQP-001"
                ed["name"] = ed.get("name") or ed.get("equipment_name") or "Industrial Asset"
                ed["type"] = ed.get("type") or ed.get("machine_type") or ed.get("category") or "Industrial Machinery"
                ed["location"] = ed.get("location") or ed.get("zone") or "Plant Floor"
                ed["snr_threshold_db"] = round(float(ed.get("snr_threshold_db") or 15.0), 1)
                ed["status"] = ed.get("status") or "Online"
                ed["created_label"] = _format_timestamp_label(ed.get("created_at"))
                if hasattr(ed.get("created_at"), "isoformat"):
                    ed["created_at"] = ed["created_at"].isoformat()
                equipment.append(ed)
        except Exception as exc:
            logger.warning(f"Equipment query notice: {exc}")

    total_detections = len(events)
    active_alerts_list = [a for a in alerts if a.get("status") not in ("Resolved", "Closed", "Dismissed")]
    active_alerts_count = len(active_alerts_list)
    critical_count = len(critical_events)

    avg_conf_pct = round(sum(e["python_conf_pct"] for e in events) / total_detections, 1) if total_detections > 0 else 0.0
    avg_gtm_pct = round(sum(e["gtm_conf_pct"] for e in events) / total_detections, 1) if total_detections > 0 else 0.0
    avg_snr_db = round(sum(e["snr_db"] for e in events) / total_detections, 1) if total_detections > 0 else 0.0

    alert_counts = {
        "critical": sum(1 for a in alerts if a.get("severity") == "Critical"),
        "high": sum(1 for a in alerts if a.get("severity") == "High"),
        "medium": sum(1 for a in alerts if a.get("severity") == "Medium"),
        "low": sum(1 for a in alerts if a.get("severity") == "Low"),
        "unacknowledged": sum(1 for a in alerts if a.get("status") in ("New", "Open", "Unacknowledged")),
        "acknowledged": sum(1 for a in alerts if a.get("status") == "Acknowledged"),
        "resolved": sum(1 for a in alerts if a.get("status") == "Resolved"),
    }

    user_settings = (user or {}).get("role_settings") or {
        "min_alert_confidence": 75,
        "sound_enabled": True,
        "privacy_mode": True,
        "snr_threshold_db": 12.0
    }

    # Compute Role Quota & Plan Limits
    from src.security.quotas import get_subscription_usage_summary
    usage_info = await get_subscription_usage_summary(
        db,
        tenant_id=(user or {}).get("tenant_id"),
        user_id=(user or {}).get("user_id"),
        user_role=(user or {}).get("role", "normal_user"),
    )
    plan_obj = usage_info.get("plan") or {}
    credits_limit = int(usage_info.get("credits_limit") or 30000)
    raw_credits_used = int(usage_info.get("credits_used") or 0)
    credits_used = max(raw_credits_used, total_detections * 25)
    credits_pct = min(100.0, round((credits_used / max(1, credits_limit)) * 100, 1))
    records_pct = min(100.0, round((total_detections / max(1, record_limit)) * 100, 1))

    quota = {
        "plan_id": plan_obj.get("plan_id", "ind_starter"),
        "plan_name": plan_obj.get("name", "Personal Starter"),
        "role_label": "Normal User (Individual Tier)" if is_normal_user else role_group.title(),
        "scope_label": "Personal Workspace Scope" if is_normal_user else "Operational Workspace",
        "credits_used": credits_used,
        "credits_limit": credits_limit,
        "credits_remaining": max(0, credits_limit - credits_used),
        "credits_percent": credits_pct,
        "record_limit": record_limit,
        "records_used": total_detections,
        "records_percent": records_pct,
        "alert_limit": alert_limit,
        "max_upload_mb": USER_ROLE_MAX_UPLOAD_MB,
        "max_live_streams": int(plan_obj.get("max_zones") or 1),
        "retention_days": int(plan_obj.get("retention_days") or 30),
        "allowed_classes_count": 10,
        "subscription_status": usage_info.get("subscription_status", "active"),
    }

    # Compute 5-Stage Personal Acoustic Pipeline Metrics
    snr_thresh = float(user_settings.get("snr_threshold_db", 12.0))
    quality_pass_count = sum(1 for e in events if e.get("quality") in ("Good", "Acceptable") or e.get("snr_db", 0) >= snr_thresh)
    quality_pass_pct = round((quality_pass_count / total_detections) * 100, 1) if total_detections > 0 else 100.0
    match_count = sum(1 for e in events if "Match" in str(e.get("consistency_status", "")))
    disagree_count = max(0, total_detections - match_count)
    consensus_rate_pct = round((match_count / total_detections) * 100, 1) if total_detections > 0 else 100.0

    pipeline = {
        "stage_1_capture": {
            "name": "16kHz PCM Capture",
            "captured_count": total_detections,
            "record_limit": record_limit,
            "sample_rate_hz": 16000,
            "window_sec": 2.0,
        },
        "stage_2_gate": {
            "name": "SNR & Signal Gate",
            "pass_count": quality_pass_count,
            "pass_pct": quality_pass_pct,
            "avg_snr_db": avg_snr_db,
            "threshold_db": snr_thresh,
        },
        "stage_3_cnn": {
            "name": "Python 2D-CNN",
            "classified_count": total_detections,
            "avg_conf_pct": avg_conf_pct,
            "latency_ms": 18,
        },
        "stage_4_gtm": {
            "name": "GTM Consensus Verifier",
            "match_count": match_count,
            "disagreement_count": disagree_count,
            "consensus_rate_pct": consensus_rate_pct,
            "avg_gtm_pct": avg_gtm_pct,
        },
        "stage_5_dispatch": {
            "name": "Safety Alert & Vault",
            "alerts_total": len(alerts),
            "unack_alerts": alert_counts["unacknowledged"],
            "min_conf_threshold": int(user_settings.get("min_alert_confidence", 75)),
            "retention_days": quota["retention_days"],
        }
    }

    kpis = {
        "total_detections": total_detections,
        "active_alerts": active_alerts_count,
        "active_faults": active_alerts_count,
        "critical_count": critical_count,
        "avg_confidence_pct": avg_conf_pct,
        "avg_gtm_confidence_pct": avg_gtm_pct,
        "avg_snr_db": avg_snr_db,
        "consensus_rate_pct": consensus_rate_pct,
        "equipment_count": len(equipment)
    }

    nav_badges = {
        "detections_count": total_detections,
        "alerts_count": active_alerts_count,
        "active_alerts_count": active_alerts_count,
        "active_faults_count": active_alerts_count,
        "critical_count": critical_count,
        "critical_faults_count": critical_count,
        "equipment_count": len(equipment),
        "notifications_count": len(notifications)
    }

    summary = {
        "kpis": kpis,
        "events": events,
        "critical_events": critical_events,
        "alerts": alerts,
        "alert_counts": alert_counts,
        "equipment": equipment,
        "notifications": notifications,
        "settings": user_settings,
        "quota": quota,
        "pipeline": pipeline,
    }
    return summary, nav_badges


async def _require_role_group(request: Request, allowed_roles: set, required_label: str):
    """Validates session and strictly enforces RBAC for the target role group."""
    user = await get_authenticated_user(request)
    if not user:
        return None, RedirectResponse(url=f"/app/login?redirect={request.url.path}", status_code=302)
    role = (user.get("role") or "normal_user").lower()
    if role not in allowed_roles:
        return None, render_rbac_denied(request, user, required_label)
    return user, None


# =============================================================================
# ROLE-AWARE TERMINAL & WORKSPACE DISPATCHERS
# =============================================================================

@app_router.get("/app/terminal", response_class=HTMLResponse)
@app_router.get("/terminal", response_class=HTMLResponse)
async def serve_role_terminal_dispatcher(request: Request):
    """Redirects authenticated user to their role-specific existing SonicSentinel AI Terminal."""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    _, terminal_url, _ = get_role_home_and_terminal(user.get("role", "normal_user"))
    return RedirectResponse(url=terminal_url, status_code=302)


@app_router.get("/app/select-role", response_class=HTMLResponse)
async def serve_role_portal_return(request: Request):
    """Used by the Sci-Fi Terminal 'EXIT / ROLES' button to return to the role's Portal Dashboard."""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    home_url, _, _ = get_role_home_and_terminal(user.get("role", "normal_user"))
    return RedirectResponse(url=home_url, status_code=302)


# =============================================================================
# SUPER ADMIN ROOT ENTRY (/app/admin)
# =============================================================================

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
        "portal_name": "Dashboard — SonicSentinel AI",
        "page_heading": "Dashboard",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "dashboard",
        "summary": summary
    })


# =============================================================================
# ROLE 1 — NORMAL USER ROUTES (/app/user/*)
# =============================================================================

USER_PAGE_META = {
    "dashboard": ("Overview", "app/roles/user/dashboard.html"),
    "live_monitoring": ("Live Stream", "app/roles/user/live_monitoring.html"),
    "detections": ("Detections", "app/roles/user/detections.html"),
    "alerts": ("Alerts", "app/roles/user/alerts.html"),
    "history": ("History", "app/roles/user/history.html"),
    "analyze": ("Analyze Audio", "app/roles/user/analyze.html"),
    "audio": ("Audio Library", "app/roles/user/audio.html"),
    "notifications": ("Notifications", "app/roles/user/notifications.html"),
    "profile": ("Profile", "app/roles/user/profile.html"),
    "settings": ("Settings", "app/roles/user/settings.html"),
}


async def _render_normal_user_page(request: Request, page_key: str):
    user, denied = await _require_role_group(request, NORMAL_USER_ROLES, "Normal User")
    if denied:
        return denied
    db = await ensure_database()
    summary, nav_badges = await _load_operational_role_summary(db, user, "user")
    heading, tpl_name = USER_PAGE_META.get(page_key, USER_PAGE_META["dashboard"])
    from config.settings import get_mandatory_classes
    return templates.TemplateResponse(request=request, name=tpl_name, context={
        "app_name": settings.APP_NAME,
        "portal_name": f"{heading} — SonicSentinel",
        "page_heading": heading,
        "role_badge": "Personal Plan",
        "user": user,
        "active_tab": "user",
        "user_page": page_key,
        "summary": summary,
        "nav_badges": nav_badges,
        "categories": get_mandatory_classes()
    })


@app_router.get("/app/user/terminal", response_class=HTMLResponse)
async def serve_normal_user_terminal(request: Request):
    """Serves the untouched Normal User Sci-Fi Terminal (dectus-user)."""
    user, denied = await _require_role_group(request, NORMAL_USER_ROLES, "Normal User")
    if denied:
        return denied
    return templates.TemplateResponse(request=request, name="app/roles/user/terminal.html", context={
        "app_name": settings.APP_NAME,
        "user": user
    })


@app_router.get("/app/user", response_class=HTMLResponse)
@app_router.get("/portal/user", response_class=HTMLResponse)
@app_router.get("/app/user/dashboard", response_class=HTMLResponse)
async def serve_normal_user_dashboard(request: Request):
    return await _render_normal_user_page(request, "dashboard")


@app_router.get("/app/user/live-monitoring", response_class=HTMLResponse)
async def serve_normal_user_live(request: Request):
    return await _render_normal_user_page(request, "live_monitoring")


@app_router.get("/app/user/detections", response_class=HTMLResponse)
async def serve_normal_user_detections(request: Request):
    return await _render_normal_user_page(request, "detections")


@app_router.get("/app/user/alerts", response_class=HTMLResponse)
async def serve_normal_user_alerts(request: Request):
    return await _render_normal_user_page(request, "alerts")


@app_router.get("/app/user/history", response_class=HTMLResponse)
async def serve_normal_user_history(request: Request):
    return await _render_normal_user_page(request, "history")


@app_router.get("/app/user/analyze", response_class=HTMLResponse)
async def serve_normal_user_analyze(request: Request):
    return await _render_normal_user_page(request, "analyze")


@app_router.get("/app/user/audio", response_class=HTMLResponse)
async def serve_normal_user_audio(request: Request):
    return await _render_normal_user_page(request, "audio")


@app_router.get("/app/user/notifications", response_class=HTMLResponse)
async def serve_normal_user_notifications(request: Request):
    return await _render_normal_user_page(request, "notifications")


@app_router.get("/app/user/profile", response_class=HTMLResponse)
async def serve_normal_user_profile(request: Request):
    return await _render_normal_user_page(request, "profile")


@app_router.get("/app/user/settings", response_class=HTMLResponse)
async def serve_normal_user_settings(request: Request):
    return await _render_normal_user_page(request, "settings")


# =============================================================================
# ROLE 2 — SECURITY ROUTES (/app/security/*)
# =============================================================================

SECURITY_PAGE_META = {
    "dashboard": ("Security Dashboard", "app/roles/security/dashboard.html"),
    "live_monitoring": ("Live Monitoring", "app/roles/security/live_monitoring.html"),
    "alerts": ("Active Alerts", "app/roles/security/alerts.html"),
    "event_monitor": ("Event Monitor", "app/roles/security/event_monitor.html"),
    "detections": ("Detections", "app/roles/security/detections.html"),
    "history": ("Event History", "app/roles/security/history.html"),
    "critical": ("Critical Events", "app/roles/security/critical.html"),
    "analyze": ("Analyze Audio", "app/roles/security/analyze.html"),
    "reports": ("Audio Reports", "app/roles/security/reports.html"),
    "notifications": ("Notifications", "app/roles/security/notifications.html"),
    "profile": ("Profile", "app/roles/security/profile.html"),
    "settings": ("Settings", "app/roles/security/settings.html"),
}


async def _render_security_page(request: Request, page_key: str):
    user, denied = await _require_role_group(request, SECURITY_ROLES, "Security")
    if denied:
        return denied
    db = await ensure_database()
    summary, nav_badges = await _load_operational_role_summary(db, user, "security")
    heading, tpl_name = SECURITY_PAGE_META.get(page_key, SECURITY_PAGE_META["dashboard"])
    from config.settings import get_mandatory_classes
    return templates.TemplateResponse(request=request, name=tpl_name, context={
        "app_name": settings.APP_NAME,
        "portal_name": f"{heading} — SonicSentinel Security",
        "page_heading": heading,
        "role_badge": "Security",
        "user": user,
        "active_tab": "security",
        "security_page": page_key,
        "summary": summary,
        "nav_badges": nav_badges,
        "categories": get_mandatory_classes()
    })


@app_router.get("/app/security/terminal", response_class=HTMLResponse)
async def serve_security_terminal(request: Request):
    """Serves the untouched Security Sci-Fi Terminal (dectus-security)."""
    user, denied = await _require_role_group(request, SECURITY_ROLES, "Security")
    if denied:
        return denied
    return templates.TemplateResponse(request=request, name="app/roles/security/terminal.html", context={
        "app_name": settings.APP_NAME,
        "user": user
    })


@app_router.get("/app/security", response_class=HTMLResponse)
@app_router.get("/portal/security", response_class=HTMLResponse)
@app_router.get("/app/security/dashboard", response_class=HTMLResponse)
async def serve_security_dashboard_page(request: Request):
    return await _render_security_page(request, "dashboard")


@app_router.get("/app/security/live-monitoring", response_class=HTMLResponse)
@app_router.get("/app/security/live", response_class=HTMLResponse)
async def serve_security_live_page(request: Request):
    return await _render_security_page(request, "live_monitoring")


@app_router.get("/app/security/alerts", response_class=HTMLResponse)
async def serve_security_alerts_page(request: Request):
    return await _render_security_page(request, "alerts")


@app_router.get("/app/security/event-monitor", response_class=HTMLResponse)
async def serve_security_event_monitor_page(request: Request):
    return await _render_security_page(request, "event_monitor")


@app_router.get("/app/security/detections", response_class=HTMLResponse)
@app_router.get("/app/security/events", response_class=HTMLResponse)
async def serve_security_detections_page(request: Request):
    return await _render_security_page(request, "detections")


@app_router.get("/app/security/history", response_class=HTMLResponse)
async def serve_security_history_page(request: Request):
    return await _render_security_page(request, "history")


@app_router.get("/app/security/critical", response_class=HTMLResponse)
async def serve_security_critical_page(request: Request):
    return await _render_security_page(request, "critical")


@app_router.get("/app/security/analyze", response_class=HTMLResponse)
async def serve_security_analyze_page(request: Request):
    return await _render_security_page(request, "analyze")


@app_router.get("/app/security/reports", response_class=HTMLResponse)
@app_router.get("/app/security/analytics", response_class=HTMLResponse)
async def serve_security_reports_page(request: Request):
    return await _render_security_page(request, "reports")


@app_router.get("/app/security/notifications", response_class=HTMLResponse)
async def serve_security_notifications_page(request: Request):
    return await _render_security_page(request, "notifications")


@app_router.get("/app/security/profile", response_class=HTMLResponse)
async def serve_security_profile_page(request: Request):
    return await _render_security_page(request, "profile")


@app_router.get("/app/security/settings", response_class=HTMLResponse)
async def serve_security_settings_page(request: Request):
    return await _render_security_page(request, "settings")


# =============================================================================
# ROLE 3 — MAINTENANCE ROUTES (/app/maintenance/*)
# =============================================================================

MAINTENANCE_PAGE_META = {
    "dashboard": ("Maintenance Dashboard", "app/roles/maintenance/dashboard.html"),
    "live_monitoring": ("Live Monitoring", "app/roles/maintenance/live_monitoring.html"),
    "equipment": ("Equipment Monitor", "app/roles/maintenance/equipment.html"),
    "faults": ("Active Faults", "app/roles/maintenance/faults.html"),
    "detections": ("Detections", "app/roles/maintenance/detections.html"),
    "history": ("Fault History", "app/roles/maintenance/history.html"),
    "critical": ("Critical Faults", "app/roles/maintenance/critical.html"),
    "analyze": ("Analyze Audio", "app/roles/maintenance/analyze.html"),
    "reports": ("Maintenance Reports", "app/roles/maintenance/reports.html"),
    "notifications": ("Notifications", "app/roles/maintenance/notifications.html"),
    "profile": ("Profile", "app/roles/maintenance/profile.html"),
    "settings": ("Settings", "app/roles/maintenance/settings.html"),
}


async def _render_maintenance_page(request: Request, page_key: str):
    user, denied = await _require_role_group(request, MAINTENANCE_ROLES, "Maintenance")
    if denied:
        return denied
    db = await ensure_database()
    summary, nav_badges = await _load_operational_role_summary(db, user, "maintenance")
    heading, tpl_name = MAINTENANCE_PAGE_META.get(page_key, MAINTENANCE_PAGE_META["dashboard"])
    from config.settings import get_mandatory_classes
    return templates.TemplateResponse(request=request, name=tpl_name, context={
        "app_name": settings.APP_NAME,
        "portal_name": f"{heading} — SonicSentinel Maintenance",
        "page_heading": heading,
        "role_badge": "Maintenance",
        "user": user,
        "active_tab": "maintenance",
        "maintenance_page": page_key,
        "summary": summary,
        "nav_badges": nav_badges,
        "categories": get_mandatory_classes()
    })


@app_router.get("/app/maintenance/terminal", response_class=HTMLResponse)
async def serve_maintenance_terminal(request: Request):
    """Serves the untouched Maintenance Sci-Fi Terminal (dectus-maintenance)."""
    user, denied = await _require_role_group(request, MAINTENANCE_ROLES, "Maintenance")
    if denied:
        return denied
    return templates.TemplateResponse(request=request, name="app/roles/maintenance/terminal.html", context={
        "app_name": settings.APP_NAME,
        "user": user
    })


@app_router.get("/app/maintenance", response_class=HTMLResponse)
@app_router.get("/portal/maintenance", response_class=HTMLResponse)
@app_router.get("/app/maintenance/dashboard", response_class=HTMLResponse)
async def serve_maintenance_dashboard_page(request: Request):
    return await _render_maintenance_page(request, "dashboard")


@app_router.get("/app/maintenance/live-monitoring", response_class=HTMLResponse)
async def serve_maintenance_live_page(request: Request):
    return await _render_maintenance_page(request, "live_monitoring")


@app_router.get("/app/maintenance/equipment", response_class=HTMLResponse)
async def serve_maintenance_equipment_page(request: Request):
    return await _render_maintenance_page(request, "equipment")


@app_router.get("/app/maintenance/faults", response_class=HTMLResponse)
async def serve_maintenance_faults_page(request: Request):
    return await _render_maintenance_page(request, "faults")


@app_router.get("/app/maintenance/detections", response_class=HTMLResponse)
async def serve_maintenance_detections_page(request: Request):
    return await _render_maintenance_page(request, "detections")


@app_router.get("/app/maintenance/history", response_class=HTMLResponse)
async def serve_maintenance_history_page(request: Request):
    return await _render_maintenance_page(request, "history")


@app_router.get("/app/maintenance/critical", response_class=HTMLResponse)
async def serve_maintenance_critical_page(request: Request):
    return await _render_maintenance_page(request, "critical")


@app_router.get("/app/maintenance/analyze", response_class=HTMLResponse)
async def serve_maintenance_analyze_page(request: Request):
    return await _render_maintenance_page(request, "analyze")


@app_router.get("/app/maintenance/reports", response_class=HTMLResponse)
async def serve_maintenance_reports_page(request: Request):
    return await _render_maintenance_page(request, "reports")


@app_router.get("/app/maintenance/notifications", response_class=HTMLResponse)
async def serve_maintenance_notifications_page(request: Request):
    return await _render_maintenance_page(request, "notifications")


@app_router.get("/app/maintenance/profile", response_class=HTMLResponse)
async def serve_maintenance_profile_page(request: Request):
    return await _render_maintenance_page(request, "profile")


@app_router.get("/app/maintenance/settings", response_class=HTMLResponse)
async def serve_maintenance_settings_page(request: Request):
    return await _render_maintenance_page(request, "settings")


# =============================================================================
# SHARED PROFILE, ALERTS, SETTINGS, EQUIPMENT & CSV EXPORT APIS
# =============================================================================



@app_router.post("/api/app/user/sos")
async def api_trigger_resident_sos(request: Request):
    """Dispatches instant emergency SOS beacon for resident."""
    user = await get_authenticated_user(request)
    user_id = user.get("user_id", "USR-RESIDENT-001") if user else "USR-RESIDENT-001"
    user_name = user.get("full_name", "Resident") if user else "Resident"
    tenant_id = user.get("tenant_id", "b2c_residents") if user else "b2c_residents"

    db = await ensure_database()
    alert_id = f"ALT-SOS-{uuid.uuid4().hex[:6].upper()}"
    sos_alert = {
        "alert_id": alert_id,
        "audio_id": f"AUD-SOS-{uuid.uuid4().hex[:6].upper()}",
        "tenant_id": tenant_id,
        "user_id": user_id,
        "user_name": user_name,
        "category": "SOS Distress Beacon",
        "severity": "Critical",
        "status": "Active / Dispatch En Route",
        "decibel_peak": 98.6,
        "location": "Living Space Zone A (Primary Residence)",
        "message": f"EMERGENCY SOS: Resident {user_name} triggered high-priority acoustic distress beacon.",
        "created_at": datetime.utcnow().isoformat()
    }
    if db is not None:
        await db.alerts.insert_one(sos_alert)
        await db.notifications.insert_one({
            "notification_id": f"NOTIF-{uuid.uuid4().hex[:6].upper()}",
            "tenant_id": tenant_id,
            "title": "EMERGENCY SOS DISPATCH ACTIVE",
            "message": f"Distress beacon active for {user_name}. Security team notified.",
            "type": "critical",
            "read": False,
            "created_at": datetime.utcnow().isoformat()
        })
    return {"success": True, "alert_id": alert_id, "message": "Emergency SOS dispatched successfully"}

@app_router.get("/app/profile", response_class=HTMLResponse)
@app_router.get("/portal/profile", response_class=HTMLResponse)
async def serve_profile_page(request: Request):
    """Dedicated Profile & Account Settings Page"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login", status_code=302)
    role_key = (user.get("role") or "normal_user").lower()
    if role_key in NORMAL_USER_ROLES:
        return RedirectResponse(url="/app/user/profile", status_code=302)
    if role_key in SECURITY_ROLES:
        return RedirectResponse(url="/app/security/profile", status_code=302)
    if role_key in MAINTENANCE_ROLES:
        return RedirectResponse(url="/app/maintenance/profile", status_code=302)
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
    return RedirectResponse(url=f"/app/{subpath}", status_code=302)


def _get_user_tenant_filter(user: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    user_tenant = str((user or {}).get("tenant_id") or "").strip()
    if user_tenant and user_tenant not in ("platform_global", "b2c_residents", "tenant_residence_101"):
        return {"tenant_id": user_tenant}
    return {}


@app_router.patch("/api/app/role/alerts/{alert_id}")
async def api_update_role_alert_status(alert_id: str, request: Request):
    """Updates alert/fault status (Acknowledged, Escalated, Resolved) in MongoDB."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    body = await request.json()
    new_status = str(body.get("status") or "Acknowledged").strip()
    db = await ensure_database()
    if db is not None:
        q = {"alert_id": alert_id, **_get_user_tenant_filter(user)}
        await db.alerts.update_one(
            q,
            {"$set": {
                "status": new_status,
                "acknowledged_by": user.get("full_name") or user.get("username"),
                "updated_at": datetime.utcnow().isoformat()
            }}
        )
    return {"status": "success", "alert_id": alert_id, "new_status": new_status}


@app_router.patch("/api/app/role/events/{audio_id}")
async def api_update_role_event_status(audio_id: str, request: Request):
    """Updates audio event lifecycle_status or severity for operational roles."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    body = await request.json()
    updates: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
    if "status" in body or "lifecycle_status" in body:
        updates["lifecycle_status"] = str(body.get("lifecycle_status") or body.get("status")).strip()
    if "severity" in body:
        updates["severity"] = str(body.get("severity")).strip()
    db = await ensure_database()
    if db is not None:
        q = {"audio_id": audio_id, **_get_user_tenant_filter(user)}
        await db.audio_events.update_one(q, {"$set": updates})
    return {"status": "success", "audio_id": audio_id, "updates": updates}


@app_router.delete("/api/app/role/events/{audio_id}")
async def api_delete_role_event(audio_id: str, request: Request):
    """Allows operational role user to delete an audio event within their tenant scope."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    db = await ensure_database()
    if db is not None:
        q = {"audio_id": audio_id, **_get_user_tenant_filter(user)}
        await db.audio_events.delete_one(q)
    return {"status": "success", "deleted_id": audio_id}


@app_router.post("/api/app/role/settings")
async def api_save_role_settings(request: Request):
    """Persists role-specific settings (min_alert_confidence, sound_enabled, privacy_mode) to MongoDB."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    body = await request.json()
    role_settings = {
        "min_alert_confidence": int(body.get("min_alert_confidence", 75)),
        "sound_enabled": bool(body.get("sound_enabled", True)),
        "privacy_mode": bool(body.get("privacy_mode", False)),
        "snr_threshold_db": float(body.get("snr_threshold_db", 12.0)),
        "updated_at": datetime.utcnow().isoformat()
    }
    db = await ensure_database()
    if db is not None and user.get("user_id"):
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"role_settings": role_settings}},
            upsert=True
        )
    return {"status": "success", "settings": role_settings}


@app_router.post("/api/app/role/equipment")
async def api_register_equipment(request: Request):
    """Allows Maintenance Operator to register real equipment in MongoDB, scoped to company tenant."""
    user, denied = await _require_role_group(request, MAINTENANCE_ROLES | ADMIN_ROLES, "Maintenance")
    if denied:
        raise HTTPException(status_code=403, detail="Maintenance role required.")
    body = await request.json()
    name = str(body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Equipment name is required.")
    eq_type = str(body.get("type") or body.get("machine_type") or "Industrial Asset").strip()
    eq_loc = str(body.get("location") or body.get("zone") or "Plant Floor").strip()
    snr_thresh = float(body.get("snr_threshold_db") or 15.0)
    doc = {
        "equipment_id": f"EQP-{uuid.uuid4().hex[:6].upper()}",
        "tenant_id": (user or {}).get("tenant_id", "platform_global"),
        "name": name,
        "type": eq_type,
        "machine_type": eq_type,
        "location": eq_loc,
        "zone": eq_loc,
        "snr_threshold_db": snr_thresh,
        "status": str(body.get("status") or "Online").strip(),
        "created_by": user.get("full_name") or user.get("username"),
        "created_at": datetime.utcnow().isoformat()
    }
    db = await ensure_database()
    if db is not None:
        await db.equipment.insert_one(dict(doc))
    return {"status": "success", "equipment": doc}


@app_router.patch("/api/app/role/equipment/{equipment_id}")
async def api_update_equipment_status(equipment_id: str, request: Request):
    user, denied = await _require_role_group(request, MAINTENANCE_ROLES | ADMIN_ROLES, "Maintenance")
    if denied:
        raise HTTPException(status_code=403, detail="Maintenance role required.")
    body = await request.json()
    new_status = str(body.get("status") or "Online").strip()
    db = await ensure_database()
    if db is not None:
        q = {"equipment_id": equipment_id, **_get_user_tenant_filter(user)}
        await db.equipment.update_one(
            q,
            {"$set": {"status": new_status, "updated_at": datetime.utcnow().isoformat()}}
        )
    return {"status": "success", "equipment_id": equipment_id, "new_status": new_status}


@app_router.delete("/api/app/role/equipment/{equipment_id}")
async def api_delete_equipment(equipment_id: str, request: Request):
    user, denied = await _require_role_group(request, MAINTENANCE_ROLES | ADMIN_ROLES, "Maintenance")
    if denied:
        raise HTTPException(status_code=403, detail="Maintenance role required.")
    db = await ensure_database()
    if db is not None:
        q = {"equipment_id": equipment_id, **_get_user_tenant_filter(user)}
        await db.equipment.delete_one(q)
    return {"status": "success", "deleted_id": equipment_id}


@app_router.delete("/api/app/user/events/{audio_id}")
async def api_delete_user_audio_event(audio_id: str, request: Request):
    """Allows an authenticated user to remove an audio event record from their history/library."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    db = await ensure_database()
    if db is not None:
        q = {"audio_id": audio_id, **_get_user_tenant_filter(user)}
        await db.audio_events.delete_one(q)
    return {"status": "success", "deleted_id": audio_id}


@app_router.post("/api/app/user/alerts/acknowledge-all")
async def api_acknowledge_all_user_alerts(request: Request):
    """Allows a user to acknowledge all open/unacknowledged alerts in their scope."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    db = await ensure_database()
    updated = 0
    if db is not None:
        q = {"status": {"$in": ["New", "Open", "Unacknowledged"]}, **_get_user_tenant_filter(user)}
        res = await db.alerts.update_many(
            q,
            {"$set": {
                "status": "Acknowledged",
                "acknowledged_by": user.get("full_name") or user.get("username"),
                "updated_at": datetime.utcnow().isoformat()
            }}
        )
        updated = res.modified_count
    return {"status": "success", "updated_count": updated}


@app_router.get("/api/app/role/export-csv")
async def api_export_role_events_csv(request: Request):
    """Exports real MongoDB audio_events to CSV, respecting role-based record limits and company tenant isolation."""
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    role_key = (user.get("role") or "normal_user").lower()
    export_limit = USER_ROLE_RECORD_LIMIT if role_key in NORMAL_USER_ROLES else 300
    db = await ensure_database()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Audio ID", "Filename", "Python Prediction", "Python Confidence", "GTM Prediction", "GTM Confidence", "Agreement", "Severity", "SNR (dB)", "Quality", "Timestamp"])
    if db is not None:
        events = await db.audio_events.find(_get_user_tenant_filter(user), {"_id": 0}).sort("created_at", -1).limit(export_limit).to_list(export_limit)
        for ev in events:
            writer.writerow([
                ev.get("audio_id", ""),
                ev.get("filename", ""),
                ev.get("python_prediction", ""),
                ev.get("python_confidence", ""),
                ev.get("gtm_prediction", ""),
                ev.get("gtm_confidence", ""),
                ev.get("consistency_status", ""),
                ev.get("severity", ""),
                ev.get("snr_db", ""),
                ev.get("quality", ""),
                str(ev.get("created_at", ""))[:19]
            ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sonicsentinel_detections_export.csv"}
    )


# -------------------------------------------------------------
# Real-Time Notifications & Profile APIs (MongoDB Backed)
# -------------------------------------------------------------

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
                {"$set": {"full_name": full_name, "avatar_url": avatar_url}},
                upsert=True
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

    audio_id = rev.get("audio_id") or ""
    ev = await db.audio_events.find_one({"audio_id": audio_id}, {"_id": 0}) if audio_id else None

    py_pred = rev.get("ai_python_prediction") or rev.get("python_prediction") or (ev.get("python_prediction") if ev else "Ambient")
    py_conf = float(rev.get("ai_python_confidence") or rev.get("python_confidence") or (ev.get("python_confidence") if ev else 0.0))
    gtm_pred = rev.get("ai_gtm_prediction") or rev.get("gtm_prediction") or (ev.get("gtm_prediction") if ev else "Ambient")
    gtm_conf = float(rev.get("ai_gtm_confidence") or rev.get("gtm_confidence") or (ev.get("gtm_confidence") if ev else 0.0))

    py_top3 = rev.get("python_top3") or (ev.get("python_top3") if ev else None) or [
        {"category": py_pred, "confidence": py_conf}
    ]
    gtm_top3 = rev.get("gtm_top3") or (ev.get("gtm_top3") if ev else None) or [
        {"category": gtm_pred, "confidence": gtm_conf}
    ]

    return {
        "status": "success",
        "case": {
            "review_id": rev.get("review_id"),
            "audio_id": audio_id,
            "tenant_id": rev.get("tenant_id", "platform_global"),
            "zone": rev.get("zone") or rev.get("zone_name", "Sensor"),
            "status": rev.get("status", "Pending Review"),
            "consistency_status": rev.get("consistency_status", "Model Disagreement"),
            "quality": rev.get("quality", "Good"),
            "snr_db": rev.get("snr_db", 0.0),
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
    final_label = str(body.get("final_label") or body.get("final_category") or "Ambient").strip()
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
    reviewer_name = user.get("full_name") or user.get("username", "Audio Reviewer")

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

    return {
        "status": "success",
        "review_id": review_id,
        "final_label": final_label,
        "decision_type": decision_type,
        "escalated_to_soc": escalate_to_soc
    }
