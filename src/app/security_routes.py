import re
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Tuple

from fastapi import APIRouter, Request, HTTPException, Query, Path, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from config.settings import settings, load_rules
from src.database.mongodb import ensure_database
from src.app.app_routes import get_authenticated_user
from src.services.security_service import (
    get_security_kpis,
    get_priority_alerts,
    get_live_detection_feed,
    get_sensors_and_zones,
    transition_alert_state,
    get_security_analytics,
    TenantAccessDenied,
    InvalidAlertTransition,
    ALLOWED_ALERT_TRANSITIONS,
    build_tenant_filter,
    _clean_doc
)

logger = logging.getLogger("SonicSentinel.SecurityRoutes")

security_router = APIRouter(tags=["Security Operations Center (SOC)"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

ALLOWED_SECURITY_ROLES = {
    "security_operator",
    "company_security_operator",
    "platform_security_operator",
    "company_admin",
    "super_admin",
    "administrator"
}


async def _require_security_user(request: Request) -> Tuple[Dict[str, Any], str, str]:
    """
    Validates authenticated session, account active status, and security operator role.
    Derives tenant_id strictly from the session.
    """
    user = await get_authenticated_user(request)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required."
        )

    if user.get("is_active") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is suspended or deactivated. Contact your administrator."
        )

    role = user.get("role", "normal_user")
    if role not in ALLOWED_SECURITY_ROLES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Security Operator privileges required."
        )

    tenant_id = user.get("tenant_id", "platform_global")
    return user, tenant_id, role


def _enforce_tenant_boundary(requested_tenant: Optional[str], session_tenant: str, actor_role: str):
    """Prevents cross-tenant parameter tampering."""
    if requested_tenant and requested_tenant != session_tenant:
        if actor_role not in ("super_admin", "administrator"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}
            )


# =============================================================================
# 1. SECURITY HTML DASHBOARDS & OPERATIONAL VIEWS
# =============================================================================

@security_router.get("/app/security", response_class=HTMLResponse)
@security_router.get("/portal/security", response_class=HTMLResponse)
async def serve_security_dashboard(request: Request):
    """
    Security Command Center (SOC) — Main Tactical Dashboard.
    100% connected to MongoDB with dynamic KPIs, Priority Alerts, and Live Detection Feed.
    """
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/login?redirect=/app/security", status_code=302)

    role = user.get("role", "normal_user")
    if role not in ALLOWED_SECURITY_ROLES:
        return RedirectResponse(url="/app/login", status_code=302)

    tenant_id = user.get("tenant_id", "platform_global")
    db = await ensure_database()

    kpis = await get_security_kpis(db, tenant_id, role)
    priority_alerts = await get_priority_alerts(db, tenant_id, role, limit=10)
    live_feed = await get_live_detection_feed(db, tenant_id, role, limit=15)
    sensors, zones = await get_sensors_and_zones(db, tenant_id, role)

    rules = load_rules()

    return templates.TemplateResponse(request=request, name="app/roles/security/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Security Command Center",
        "page_heading": "Security Command Center",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "dashboard",
        "kpis": kpis,
        "priority_alerts": priority_alerts,
        "live_feed": live_feed,
        "sensors": sensors,
        "zones": zones,
        "rules": rules
    })


@security_router.get("/app/security/live", response_class=HTMLResponse)
async def serve_security_live_monitor(request: Request):
    """Live Perimeter Surveillance & Microphone Feed."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    live_feed = await get_live_detection_feed(db, tenant_id, role, limit=30)
    sensors, zones = await get_sensors_and_zones(db, tenant_id, role)
    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/live_monitor.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Live Security Monitor",
        "page_heading": "Live Security Monitor",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "live_monitor",
        "live_feed": live_feed,
        "sensors": sensors,
        "zones": zones,
        "kpis": kpis
    })


@security_router.get("/app/security/alerts", response_class=HTMLResponse)
async def serve_security_alerts(request: Request):
    """Threat Alerts Queue with Action Handlers & State Machine."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    alerts = await get_priority_alerts(db, tenant_id, role, limit=50)
    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/alerts.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Threat Incident Alerts",
        "page_heading": "Threat Incident Alerts",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "alerts",
        "alerts": alerts,
        "kpis": kpis
    })


@security_router.get("/app/security/events", response_class=HTMLResponse)
async def serve_security_events(request: Request):
    """Acoustic Detection Events with Server-Side Search & Filters."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    kpis = await get_security_kpis(db, tenant_id, role)
    sensors, zones = await get_sensors_and_zones(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/events.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Detection Events Archive",
        "page_heading": "Detection Events",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "events",
        "kpis": kpis,
        "zones": zones,
        "sensors": sensors
    })


@security_router.get("/app/security/incidents", response_class=HTMLResponse)
async def serve_security_incidents(request: Request):
    """Incident Queue with Timeline & Investigation Actions."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    t_filter = build_tenant_filter(tenant_id, role)
    incidents = []
    if db is not None:
        incidents = await db.incidents.find(t_filter, {"_id": 0}).sort("created_at", -1).to_list(length=50)
        for inc in incidents:
            if hasattr(inc.get("created_at"), "isoformat"):
                inc["created_at"] = inc["created_at"].isoformat()
            if hasattr(inc.get("updated_at"), "isoformat"):
                inc["updated_at"] = inc["updated_at"].isoformat()

    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/incidents.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Security Incident Queue",
        "page_heading": "Security Incident Queue",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "incidents",
        "incidents": incidents,
        "kpis": kpis
    })


@security_router.get("/app/security/sensors", response_class=HTMLResponse)
async def serve_security_sensors(request: Request):
    """Sensors & Zones Fleet Status."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    sensors, zones = await get_sensors_and_zones(db, tenant_id, role)
    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/sensors.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Perimeter Sensors & Zones",
        "page_heading": "Perimeter Sensors & Zones",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "sensors",
        "sensors": sensors,
        "zones": zones,
        "kpis": kpis
    })


@security_router.get("/app/security/reviews", response_class=HTMLResponse)
async def serve_security_reviews(request: Request):
    """Forensic Review Queue accessible to Security for Escalations."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    t_filter = build_tenant_filter(tenant_id, role)
    reviews = []
    if db is not None:
        reviews = await db.manual_reviews.find(t_filter, {"_id": 0}).sort("created_at", -1).to_list(length=40)
        for r in reviews:
            if hasattr(r.get("created_at"), "isoformat"):
                r["created_at"] = r["created_at"].isoformat()

    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/reviews.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Forensic Review Queue",
        "page_heading": "Forensic Review Queue",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "reviews",
        "reviews": reviews,
        "kpis": kpis
    })


@security_router.get("/app/security/analytics", response_class=HTMLResponse)
async def serve_security_analytics(request: Request):
    """Security Analytics & Acoustic Threat Trends."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    analytics = await get_security_analytics(db, tenant_id, role, time_range="7d")
    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/analytics.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Security Analytics",
        "page_heading": "Security Analytics",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "analytics",
        "analytics": analytics,
        "kpis": kpis
    })


@security_router.get("/app/security/notifications", response_class=HTMLResponse)
async def serve_security_notifications(request: Request):
    """Security Notifications Center."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    t_filter = build_tenant_filter(tenant_id, role)
    notifications = []
    if db is not None:
        q = {
            "$or": [
                {"target_tenant_id": {"$in": ["all", tenant_id]}},
                {"target_roles": {"$in": ["security_operator", "all"]}},
                {"target_role": {"$in": ["security_operator", "all"]}}
            ]
        }
        if t_filter:
            q = {"$and": [q, t_filter]}

        cursor = db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(40)
        notifications = await cursor.to_list(length=40)
        for n in notifications:
            if hasattr(n.get("created_at"), "isoformat"):
                n["created_at"] = n["created_at"].isoformat()

    kpis = await get_security_kpis(db, tenant_id, role)

    return templates.TemplateResponse(request=request, name="app/roles/security/notifications.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Security Notifications",
        "page_heading": "Notifications Center",
        "role_badge": "Security Operator",
        "user": user,
        "active_tab": "security",
        "security_page": "notifications",
        "notifications": notifications,
        "kpis": kpis
    })


# =============================================================================
# 2. SECURITY REST APIS (/api/security/*)
# =============================================================================

@security_router.get("/api/security/overview")
async def api_security_overview(request: Request):
    """Returns overview KPIs, priority alerts, live feed, and zones for the SOC dashboard."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    kpis = await get_security_kpis(db, tenant_id, role)
    alerts = await get_priority_alerts(db, tenant_id, role, limit=10)
    live_feed = await get_live_detection_feed(db, tenant_id, role, limit=15)
    sensors, zones = await get_sensors_and_zones(db, tenant_id, role)

    return {
        "success": True,
        "tenant_id": tenant_id,
        "kpis": kpis,
        "priority_alerts": alerts,
        "live_feed": live_feed,
        "sensors": sensors,
        "zones": zones
    }


@security_router.get("/api/security/live")
async def api_security_live_feed(request: Request, limit: int = 25):
    """Real-time detection feed for polling / streaming."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    limit = min(max(limit, 5), 100)
    feed = await get_live_detection_feed(db, tenant_id, role, limit=limit)
    return {"success": True, "feed": feed, "count": len(feed)}


@security_router.get("/api/security/events")
async def api_security_events(
    request: Request,
    page: int = 1,
    limit: int = 25,
    search: Optional[str] = None,
    severity: Optional[str] = None,
    category: Optional[str] = None,
    zone: Optional[str] = None,
    sensor: Optional[str] = None,
    consistency: Optional[str] = None,
    tenant_id: Optional[str] = None
):
    """Server-side paginated & filtered detection events scoped strictly to tenant."""
    user, session_tenant, role = await _require_security_user(request)
    _enforce_tenant_boundary(tenant_id, session_tenant, role)
    active_tenant = session_tenant

    db = await ensure_database()
    if db is None:
        return {"success": True, "events": [], "total": 0, "page": page, "limit": limit}

    page = max(page, 1)
    limit = min(max(limit, 1), 100)

    query = build_tenant_filter(active_tenant, role)
    if severity and severity not in ("ALL", ""):
        query["severity"] = severity
    if category and category not in ("ALL", ""):
        query["python_prediction"] = category
    if zone and zone not in ("ALL", ""):
        query["zone_name"] = zone
    if sensor and sensor not in ("ALL", ""):
        query["sensor_id"] = sensor
    if consistency and consistency not in ("ALL", ""):
        query["consistency_status"] = consistency

    if search:
        safe_q = re.escape(search.strip())
        query["$or"] = [
            {"audio_id": {"$regex": safe_q, "$options": "i"}},
            {"filename": {"$regex": safe_q, "$options": "i"}},
            {"python_prediction": {"$regex": safe_q, "$options": "i"}},
            {"zone_name": {"$regex": safe_q, "$options": "i"}}
        ]

    total = await db.audio_events.count_documents(query)
    skip = (page - 1) * limit
    events = await db.audio_events.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    for ev in events:
        if hasattr(ev.get("created_at"), "isoformat"):
            ev["created_at"] = ev["created_at"].isoformat()

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit if total > 0 else 1,
        "events": events
    }


@security_router.get("/api/security/events/{audio_id}")
async def api_security_event_detail(audio_id: str, request: Request):
    """Forensic inspection for a single acoustic event with strict tenant ownership validation."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"audio_id": audio_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    event = await db.audio_events.find_one(query, {"_id": 0})
    if not event:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    pred = await db.predictions.find_one({"audio_id": audio_id}, {"_id": 0}) or {}
    alert = await db.alerts.find_one({"audio_id": audio_id}, {"_id": 0}) or {}
    review = await db.manual_reviews.find_one({"audio_id": audio_id}, {"_id": 0}) or {}

    return {
        "success": True,
        "event": _clean_doc(event),
        "prediction": _clean_doc(pred),
        "alert": _clean_doc(alert),
        "review": _clean_doc(review)
    }


@security_router.get("/api/security/alerts")
async def api_security_get_alerts(
    request: Request,
    severity: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    limit: int = 25,
    tenant_id: Optional[str] = None
):
    """Paginated threat alerts scoped strictly to the authenticated tenant."""
    user, session_tenant, role = await _require_security_user(request)
    _enforce_tenant_boundary(tenant_id, session_tenant, role)

    db = await ensure_database()
    if db is None:
        return {"success": True, "alerts": [], "total": 0}

    page = max(page, 1)
    limit = min(max(limit, 1), 100)

    query = build_tenant_filter(session_tenant, role)
    if severity and severity not in ("ALL", ""):
        query["severity"] = severity
    if status and status not in ("ALL", ""):
        query["status"] = status

    total = await db.alerts.count_documents(query)
    skip = (page - 1) * limit
    alerts = await db.alerts.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

    for a in alerts:
        if hasattr(a.get("created_at"), "isoformat"):
            a["created_at"] = a["created_at"].isoformat()

    return {
        "success": True,
        "page": page,
        "limit": limit,
        "total": total,
        "total_pages": (total + limit - 1) // limit if total > 0 else 1,
        "alerts": alerts
    }


@security_router.get("/api/security/alerts/{alert_id}")
async def api_security_get_single_alert(alert_id: str, request: Request):
    """Fetches details for a single alert with tenant boundary validation."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"alert_id": alert_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    alert = await db.alerts.find_one(query, {"_id": 0})
    if not alert:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    return {"success": True, "alert": _clean_doc(alert)}


# --- Alert State Machine Endpoints ---

@security_router.post("/api/security/alerts/{alert_id}/acknowledge")
async def api_security_alert_acknowledge(alert_id: str, request: Request):
    """Acknowledge an alert — transitions to 'Acknowledged' state with audit log."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes")

    try:
        updated = await transition_alert_state(
            db=db,
            alert_id=alert_id,
            tenant_id=tenant_id,
            actor_role=role,
            new_status="Acknowledged",
            actor=user,
            notes=notes
        )
        return {"success": True, "alert": updated, "message": f"Alert {alert_id} acknowledged successfully."}
    except TenantAccessDenied:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )
    except InvalidAlertTransition as e:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}}
        )


@security_router.post("/api/security/alerts/{alert_id}/investigate")
async def api_security_alert_investigate(alert_id: str, request: Request):
    """Mark alert as actively under investigation."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes")

    try:
        updated = await transition_alert_state(
            db=db,
            alert_id=alert_id,
            tenant_id=tenant_id,
            actor_role=role,
            new_status="Investigating",
            actor=user,
            notes=notes
        )
        return {"success": True, "alert": updated, "message": f"Alert {alert_id} moved to Investigating."}
    except TenantAccessDenied:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )
    except InvalidAlertTransition as e:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}}
        )


@security_router.post("/api/security/alerts/{alert_id}/escalate")
async def api_security_alert_escalate(alert_id: str, request: Request):
    """Escalates alert to high-priority tactical response."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes") or "Escalated for immediate on-site tactical response."

    try:
        updated = await transition_alert_state(
            db=db,
            alert_id=alert_id,
            tenant_id=tenant_id,
            actor_role=role,
            new_status="Escalated",
            actor=user,
            notes=notes
        )
        return {"success": True, "alert": updated, "message": f"Alert {alert_id} escalated successfully."}
    except TenantAccessDenied:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )
    except InvalidAlertTransition as e:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}}
        )


@security_router.post("/api/security/alerts/{alert_id}/resolve")
async def api_security_alert_resolve(alert_id: str, request: Request):
    """Resolves alert with operator notes and audit logging."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes") or "Incident cleared and verified safe by Security Operator."
    is_false_pos = bool(body.get("false_positive", False))
    target_status = "False Positive" if is_false_pos else "Resolved"

    try:
        updated = await transition_alert_state(
            db=db,
            alert_id=alert_id,
            tenant_id=tenant_id,
            actor_role=role,
            new_status=target_status,
            actor=user,
            notes=notes
        )
        return {"success": True, "alert": updated, "message": f"Alert {alert_id} marked as {target_status}."}
    except TenantAccessDenied:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )
    except InvalidAlertTransition as e:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}}
        )


@security_router.post("/api/security/alerts/{alert_id}/reopen")
async def api_security_alert_reopen(alert_id: str, request: Request):
    """Reopens a resolved or dismissed alert."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes") or "Alert reopened for additional verification."

    try:
        updated = await transition_alert_state(
            db=db,
            alert_id=alert_id,
            tenant_id=tenant_id,
            actor_role=role,
            new_status="Reopened",
            actor=user,
            notes=notes
        )
        return {"success": True, "alert": updated, "message": f"Alert {alert_id} reopened."}
    except TenantAccessDenied:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )
    except InvalidAlertTransition as e:
        return JSONResponse(
            status_code=422,
            content={"success": False, "error": {"code": "INVALID_STATE_TRANSITION", "message": str(e)}}
        )


@security_router.post("/api/security/alerts/{alert_id}/notes")
async def api_security_alert_add_note(alert_id: str, request: Request):
    """Appends an operational note to an alert."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = await request.json()
    note_text = str(body.get("notes") or body.get("note") or "").strip()
    if not note_text:
        raise HTTPException(status_code=400, detail="Note text cannot be empty.")

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"alert_id": alert_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    alert = await db.alerts.find_one(query)
    if not alert:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    actor_name = user.get("full_name") or user.get("username", "Security Operator")
    now = datetime.utcnow()
    existing_notes = alert.get("notes") or ""
    updated_notes = f"{existing_notes}\n[{now.strftime('%Y-%m-%d %H:%M')}] ({actor_name}): {note_text}".strip()

    await db.alerts.update_one({"alert_id": alert_id}, {"$set": {"notes": updated_notes, "updated_at": now}})

    # Append to linked incident if present
    await db.incidents.update_one(
        {"alert_id": alert_id},
        {
            "$push": {
                "timeline": {
                    "timestamp": now.isoformat(),
                    "actor": actor_name,
                    "action": "Note Added",
                    "note": note_text
                }
            }
        }
    )

    return {"success": True, "alert_id": alert_id, "notes": updated_notes}


# --- Incidents Queue APIs ---

@security_router.get("/api/security/incidents")
async def api_security_get_incidents(request: Request, status: Optional[str] = None):
    """Lists incidents scoped strictly to authenticated tenant."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is None:
        return {"success": True, "incidents": []}

    query = build_tenant_filter(tenant_id, role)
    if status and status not in ("ALL", ""):
        query["status"] = status

    incidents = await db.incidents.find(query, {"_id": 0}).sort("created_at", -1).to_list(length=50)
    for inc in incidents:
        if hasattr(inc.get("created_at"), "isoformat"):
            inc["created_at"] = inc["created_at"].isoformat()
        if hasattr(inc.get("updated_at"), "isoformat"):
            inc["updated_at"] = inc["updated_at"].isoformat()

    return {"success": True, "incidents": incidents, "count": len(incidents)}


@security_router.get("/api/security/incidents/{incident_id}")
async def api_security_get_incident_detail(incident_id: str, request: Request):
    """Returns incident detail and chronological timeline with tenant isolation."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is None:
        raise HTTPException(status_code=500, detail="Database offline")

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"incident_id": incident_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    incident = await db.incidents.find_one(query, {"_id": 0})
    if not incident:
        return JSONResponse(
            status_code=404,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    return {"success": True, "incident": _clean_doc(incident)}


@security_router.post("/api/security/incidents/{incident_id}/assign")
async def api_security_incident_assign(incident_id: str, request: Request):
    """Assigns an incident to an operator."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = await request.json()
    operator_name = str(body.get("operator_name") or user.get("full_name") or user.get("username")).strip()

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"incident_id": incident_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    incident = await db.incidents.find_one(query)
    if not incident:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    now = datetime.utcnow()
    await db.incidents.update_one(
        {"incident_id": incident_id},
        {
            "$set": {"assigned_operator": operator_name, "updated_at": now},
            "$push": {
                "timeline": {
                    "timestamp": now.isoformat(),
                    "actor": user.get("full_name") or user.get("username"),
                    "action": "Assigned",
                    "note": f"Assigned to {operator_name}"
                }
            }
        }
    )

    return {"success": True, "incident_id": incident_id, "assigned_operator": operator_name}


@security_router.post("/api/security/incidents/{incident_id}/escalate")
async def api_security_incident_escalate(incident_id: str, request: Request):
    """Escalates an incident."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes") or "Incident escalated by Security Operator."

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"incident_id": incident_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    incident = await db.incidents.find_one(query)
    if not incident:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    now = datetime.utcnow()
    await db.incidents.update_one(
        {"incident_id": incident_id},
        {
            "$set": {"status": "Escalated", "severity": "Critical", "updated_at": now},
            "$push": {
                "timeline": {
                    "timestamp": now.isoformat(),
                    "actor": user.get("full_name") or user.get("username"),
                    "action": "Escalated",
                    "note": notes
                }
            }
        }
    )

    if incident.get("alert_id"):
        await db.alerts.update_one(
            {"alert_id": incident["alert_id"]},
            {"$set": {"status": "Escalated", "severity": "Critical", "updated_at": now}}
        )

    return {"success": True, "incident_id": incident_id, "status": "Escalated"}


@security_router.post("/api/security/incidents/{incident_id}/resolve")
async def api_security_incident_resolve(incident_id: str, request: Request):
    """Resolves an incident."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    body = {}
    try:
        body = await request.json()
    except Exception:
        pass
    notes = body.get("notes") or "Incident resolved and cleared."

    t_filter = build_tenant_filter(tenant_id, role)
    query = {"incident_id": incident_id}
    if t_filter:
        query["tenant_id"] = tenant_id

    incident = await db.incidents.find_one(query)
    if not incident:
        return JSONResponse(
            status_code=403,
            content={"success": False, "error": {"code": "TENANT_ACCESS_DENIED", "message": "You do not have access to this resource."}}
        )

    now = datetime.utcnow()
    await db.incidents.update_one(
        {"incident_id": incident_id},
        {
            "$set": {"status": "Resolved", "updated_at": now, "resolved_at": now},
            "$push": {
                "timeline": {
                    "timestamp": now.isoformat(),
                    "actor": user.get("full_name") or user.get("username"),
                    "action": "Resolved",
                    "note": notes
                }
            }
        }
    )

    if incident.get("alert_id"):
        await db.alerts.update_one(
            {"alert_id": incident["alert_id"]},
            {"$set": {"status": "Resolved", "updated_at": now, "resolved_at": now}}
        )

    return {"success": True, "incident_id": incident_id, "status": "Resolved"}


# --- Sensors & Zones APIs ---

@security_router.get("/api/security/sensors")
async def api_security_get_sensors(request: Request):
    """Returns sensors and health metrics for the authenticated tenant."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    sensors, _ = await get_sensors_and_zones(db, tenant_id, role)
    return {"success": True, "sensors": sensors, "count": len(sensors)}


@security_router.get("/api/security/zones")
async def api_security_get_zones(request: Request):
    """Returns zones and calculated threat levels for the authenticated tenant."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    _, zones = await get_sensors_and_zones(db, tenant_id, role)
    return {"success": True, "zones": zones, "count": len(zones)}


# --- Analytics API ---

@security_router.get("/api/security/analytics")
async def api_security_get_analytics(request: Request, range: str = Query("7d")):
    """Returns dynamic time-series and distribution metrics from MongoDB."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()

    analytics = await get_security_analytics(db, tenant_id, role, time_range=range)
    return {"success": True, "analytics": analytics}


# --- Notifications APIs ---

@security_router.get("/api/security/notifications")
async def api_security_get_notifications(request: Request):
    """Returns tenant-scoped security notifications."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is None:
        return {"success": True, "notifications": [], "unread_count": 0}

    q = {
        "$or": [
            {"target_tenant_id": {"$in": ["all", tenant_id]}},
            {"target_roles": {"$in": ["security_operator", "all"]}},
            {"target_role": {"$in": ["security_operator", "all"]}}
        ]
    }
    t_filter = build_tenant_filter(tenant_id, role)
    if t_filter:
        q = {"$and": [q, t_filter]}

    notifications = await db.notifications.find(q, {"_id": 0}).sort("created_at", -1).limit(30).to_list(30)
    for n in notifications:
        if hasattr(n.get("created_at"), "isoformat"):
            n["created_at"] = n["created_at"].isoformat()

    user_id = user.get("user_id", "")
    unread = sum(1 for n in notifications if user_id not in n.get("read_by", []) and not n.get("read", False))

    return {"success": True, "notifications": notifications, "unread_count": unread}


@security_router.patch("/api/security/notifications/{notification_id}/read")
async def api_security_notification_mark_read(notification_id: str, request: Request):
    """Marks a notification as read by the authenticated operator."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is not None:
        user_id = user.get("user_id", "USR-SEC-OP-001")
        await db.notifications.update_one(
            {"notification_id": notification_id},
            {
                "$set": {"read": True},
                "$addToSet": {"read_by": user_id}
            }
        )
        return {"success": True, "notification_id": notification_id}
    return JSONResponse(status_code=500, content={"success": False, "error": "Database offline"})


@security_router.patch("/api/security/notifications/read-all")
async def api_security_notifications_read_all(request: Request):
    """Marks all notifications as read for this user."""
    user, tenant_id, role = await _require_security_user(request)
    db = await ensure_database()
    if db is not None:
        user_id = user.get("user_id", "USR-SEC-OP-001")
        await db.notifications.update_many(
            {},
            {
                "$set": {"read": True},
                "$addToSet": {"read_by": user_id}
            }
        )
        return {"success": True, "message": "All notifications marked as read."}
    return JSONResponse(status_code=500, content={"success": False, "error": "Database offline"})
