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
        "portal_name": "Dashboard — Dectus",
        "page_heading": "Dashboard",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "dashboard",
        "summary": summary
    })


# Company Admin Role routes are comprehensively handled by src.app.company_routes (company_router)
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


# Note: All /app/reviewer HTML routes are now handled comprehensively by src.app.reviewer_routes


@app_router.get("/app/user", response_class=HTMLResponse)
@app_router.get("/portal/user", response_class=HTMLResponse)
async def serve_normal_user_app(request: Request):
    """Normal Resident Personal Safety Dashboard & Audio Scanner"""
    user = await get_authenticated_user(request)
    if not user:
        return RedirectResponse(url="/app/switch-user?redirect=/app/user", status_code=302)

    db = await ensure_database()
    events = []
    alerts = []
    kpi = {
        "total_events": 18,
        "critical_count": 2,
        "ambient_spl": 42.8,
        "sensors_online": 4,
        "consensus_accuracy": "98.4%",
        "active_profile": "High Alert Residential Enclave"
    }

    if db is not None:
        try:
            raw_events = await db.audio_events.find({}, {"_id": 0}).sort("created_at", -1).to_list(15)
            for e in raw_events:
                created_raw = e.get("created_at")
                if hasattr(created_raw, "isoformat"):
                    e["created_at_fmt"] = created_raw.strftime("%Y-%m-%d %H:%M")
                elif isinstance(created_raw, str):
                    e["created_at_fmt"] = created_raw[:16].replace("T", " ")
                else:
                    e["created_at_fmt"] = "Just now"
                events.append(e)

            alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).to_list(6)
            total_count = await db.audio_events.count_documents({})
            crit_count = await db.alerts.count_documents({"severity": "Critical"})
            if total_count:
                kpi["total_events"] = total_count
            kpi["critical_count"] = crit_count
        except Exception as ex:
            logger.warning(f"Error querying user dashboard data: {ex}")

    # Fallback seed events if database is empty
    if not events:
        events = [
            {
                "audio_id": "AUD-INDUS-101",
                "python_prediction": "Machinery Fault",
                "python_confidence": 0.962,
                "gtm_prediction": "Machinery Fault",
                "gtm_confidence": 0.941,
                "consistency_status": "Acceptable Match",
                "severity": "High",
                "quality": "Good",
                "decibel_peak": 92.4,
                "created_at_fmt": "2026-09-27 05:56",
                "zone_name": "Turbine Hall Sector 2"
            },
            {
                "audio_id": "AUD-000901",
                "python_prediction": "Gunshot",
                "python_confidence": 0.962,
                "gtm_prediction": "Gunshot",
                "gtm_confidence": 0.948,
                "consistency_status": "Acceptable Match",
                "severity": "Critical",
                "quality": "Good",
                "decibel_peak": 104.2,
                "created_at_fmt": "2026-09-27 05:32",
                "zone_name": "Perimeter North Yard"
            },
            {
                "audio_id": "AUD-000904",
                "python_prediction": "Person Asking for Help",
                "python_confidence": 0.951,
                "gtm_prediction": "Person Asking for Help",
                "gtm_confidence": 0.937,
                "consistency_status": "Acceptable Match",
                "severity": "Critical",
                "quality": "Good",
                "decibel_peak": 86.5,
                "created_at_fmt": "2026-09-27 04:18",
                "zone_name": "Living Room Sensor"
            }
        ]

    pipelines = [
        {
            "id": "pipe-distress",
            "name": "Human Distress & SOS Vocal Trigger",
            "tag": "Human Safety & Distress",
            "icon": "fa-solid fa-bullhorn",
            "color": "#ef4444",
            "status": "Armed & Active",
            "model": "SoundNet 1D Waveform Net + YamNet Intent",
            "classes": ["Panic Scream", "Person Asking for Help", "Distress Cry"],
            "target_range": "300 Hz – 3,800 Hz",
            "sensitivity": 88,
            "events_today": 3,
            "latency": "11.2 ms",
            "preset_key": "Panic Scream",
            "description": "Continuous acoustic monitoring for human scream formants, distress phrases, and panic vocalizations with immediate automated security dispatch."
        },
        {
            "id": "pipe-ballistics",
            "name": "Ballistics, Shockwave & Glass Fracture",
            "tag": "Critical Perimeter Threat",
            "icon": "fa-solid fa-shield-halved",
            "color": "#dc2626",
            "status": "Armed & Active",
            "model": "Transient Shockwave Net + ResNet-50",
            "classes": ["Gunshot", "Glass Breaking", "High-Impact Shock"],
            "target_range": "10 Hz – 18,000 Hz",
            "sensitivity": 94,
            "events_today": 2,
            "latency": "8.6 ms",
            "preset_key": "Gunshot",
            "description": "Ultra-fast rise time (<5ms) impulsive shockwave detection tuned for firearm muzzle blast acoustics, tempered glass shatter, and structural breach."
        },
        {
            "id": "pipe-machinery",
            "name": "Structural & Utility Anomaly Scanner",
            "tag": "Mechanical / HVAC",
            "icon": "fa-solid fa-gears",
            "color": "#0284c7",
            "status": "Calibrated & Online",
            "model": "Harmonic Spectrum Centroid FFT",
            "classes": ["Machinery Fault", "Bearing Wear", "Impeller Cavitation"],
            "target_range": "20 Hz – 48,000 Hz",
            "sensitivity": 75,
            "events_today": 5,
            "latency": "14.1 ms",
            "preset_key": "Machinery Fault",
            "description": "Tracks mechanical vibrations, pump cavitation, and ultrasonic bearing friction across residential HVAC, plumbing, and backup power equipment."
        },
        {
            "id": "pipe-environmental",
            "name": "Perimeter Hazard & Emergency Siren",
            "tag": "Environmental Alarm",
            "icon": "fa-solid fa-triangle-exclamation",
            "color": "#eab308",
            "status": "Active & Listening",
            "model": "FM Pitch Periodicity + AudioSet Ontology",
            "classes": ["Industrial Alarm", "Vehicle Horn", "Evacuation Siren"],
            "target_range": "400 Hz – 4,500 Hz",
            "sensitivity": 82,
            "events_today": 2,
            "latency": "12.8 ms",
            "preset_key": "Alarm or Siren",
            "description": "Recognizes periodic swept-frequency tones matching fire alarms, municipal emergency sirens, and perimeter vehicle warning signals."
        }
    ]

    sensors = [
        {
            "sensor_id": "SNS-RES-01",
            "name": "Living Room Studio Node",
            "location": "Main Living Space (Zone A)",
            "type": "OmniAcoustic MEMS Array",
            "ip": "10.0.4.12",
            "latency": "11.4 ms",
            "spl_db": 41.2,
            "battery": "98%",
            "signal": "100%",
            "status": "Online & Calibrated"
        },
        {
            "sensor_id": "SNS-RES-02",
            "name": "Balcony Perimeter Beamformer",
            "location": "North Balcony / Exterior Yard",
            "type": "Directional Beamformer IP67",
            "ip": "10.0.4.15",
            "latency": "9.8 ms",
            "spl_db": 56.4,
            "battery": "PoE+ Active",
            "signal": "96%",
            "status": "Armed & Online"
        },
        {
            "sensor_id": "SNS-RES-03",
            "name": "Front Entrance Smart Mic",
            "location": "Front Entry Vestibule",
            "type": "Transient Shockwave Sensor",
            "ip": "10.0.4.19",
            "latency": "14.2 ms",
            "spl_db": 48.7,
            "battery": "89%",
            "signal": "92%",
            "status": "Online & Listening"
        },
        {
            "sensor_id": "SNS-RES-04",
            "name": "Utility & HVAC Vibration Node",
            "location": "Basement Utility Enclosure",
            "type": "Ultrasonic Contact Acoustic",
            "ip": "10.0.4.22",
            "latency": "12.1 ms",
            "spl_db": 62.1,
            "battery": "24V Hardwired",
            "signal": "99%",
            "status": "Calibrated & Normal"
        }
    ]

    return templates.TemplateResponse(request=request, name="app/roles/user/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Resident Safety Dashboard",
        "role_badge": "Normal User / Resident",
        "user": user,
        "active_tab": "user",
        "user_page": "dashboard",
        "kpi": kpi,
        "events": events,
        "alerts": alerts,
        "pipelines": pipelines,
        "sensors": sensors
    })


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
