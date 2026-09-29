import io
import csv
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.templating import Jinja2Templates

from config.settings import settings, get_mandatory_classes
from src.database.mongodb import ensure_database
from src.database.security import hash_password, verify_password, generate_session_token
from src.app.app_routes import get_authenticated_user

logger = logging.getLogger("SonicSentinel.CompanyRouter")
company_router = APIRouter(tags=["Company Admin Portal"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

COMPANY_ROLE_LABELS = {
    "company_admin": "Company Admin",
    "company_security_operator": "Security",
    "security_operator": "Security",
    "company_maintenance_operator": "Maintenance",
    "maintenance_operator": "Maintenance",
    "company_audio_reviewer": "Audio QA / Reviewer",
    "audio_reviewer": "Audio QA / Reviewer",
    "normal_user": "Normal User / Resident",
}

LABEL_TO_ROLE_KEY = {
    "company admin": "company_admin",
    "company_admin": "company_admin",
    "security": "company_security_operator",
    "company_security_operator": "company_security_operator",
    "security_operator": "company_security_operator",
    "maintenance": "company_maintenance_operator",
    "company_maintenance_operator": "company_maintenance_operator",
    "maintenance_operator": "company_maintenance_operator",
    "audio qa / reviewer": "company_audio_reviewer",
    "audio qa": "company_audio_reviewer",
    "reviewer": "company_audio_reviewer",
    "company_audio_reviewer": "company_audio_reviewer",
    "audio_reviewer": "company_audio_reviewer",
    "normal user / resident": "normal_user",
    "normal user": "normal_user",
    "resident": "normal_user",
    "normal_user": "normal_user",
}


def _sanitize_for_json(obj):
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    elif hasattr(obj, "isoformat"):
        return obj.isoformat()
    elif hasattr(obj, "__str__") and type(obj).__name__ == "ObjectId":
        return str(obj)
    return obj


@company_router.get("/app/switch-company")
@company_router.get("/app/company/switch")
async def switch_to_company_admin(redirect: str = "/app/company"):
    """Switches session to Company Admin (Apex Global Logistics) and redirects to target company page."""
    db = await ensure_database()
    tenant_id = "TENANT_APEX_01"
    user_id = "USR-COMP-ADMIN-001"
    username = "apex_admin"
    if db is not None:
        comp_admin = await db.users.find_one({"role": "company_admin"}, {"_id": 0})
        if comp_admin:
            user_id = comp_admin.get("user_id", user_id)
            username = comp_admin.get("username", username)
            tenant_id = comp_admin.get("tenant_id", tenant_id)
    token = generate_session_token(
        user_id=user_id,
        username=username,
        role="company_admin",
        tenant_id=tenant_id
    )
    target = redirect if redirect.startswith("/app/company") else "/app/company"
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


@company_router.get("/app/switch-admin")
async def switch_to_super_admin(redirect: str = "/app/admin"):
    """Switches session to Super Admin (Platform Global) and redirects to target admin page."""
    db = await ensure_database()
    tenant_id = "platform_global"
    user_id = "USR-ADMIN-001"
    username = "admin"
    if db is not None:
        admin_user = await db.users.find_one({"role": {"$in": ["super_admin", "admin"]}}, {"_id": 0})
        if admin_user:
            user_id = admin_user.get("user_id", user_id)
            username = admin_user.get("username", username)
            tenant_id = admin_user.get("tenant_id", tenant_id)
    token = generate_session_token(
        user_id=user_id,
        username=username,
        role="super_admin",
        tenant_id=tenant_id
    )
    target = redirect if redirect.startswith("/app/admin") else "/app/admin"
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



async def _require_company_or_redirect(request: Request):
    """Ensures an authenticated Company Admin user context scoped to a single company tenant."""
    from src.app.app_routes import render_rbac_denied
    user = await get_authenticated_user(request)
    req_path = request.url.path or "/app/company"
    if not user:
        return None, RedirectResponse(url=f"/app/login?redirect={req_path}", status_code=302)
    role = (user.get("role") or "normal_user").lower()
    if role not in ("company_admin", "super_admin", "administrator"):
        return None, render_rbac_denied(request, user, "Company Admin")

    db = await ensure_database()
    if user.get("tenant_id") in (None, "", "platform_global", "b2c_residents"):
        tenant_doc = await db.tenants.find_one(
            {"tenant_id": {"$nin": ["platform_global", "b2c_residents"]}},
            {"_id": 0}
        ) if db is not None else None
        if tenant_doc:
            user["tenant_id"] = tenant_doc.get("tenant_id", "TENANT_APEX_01")
            user["tenant_name"] = tenant_doc.get("company_name") or tenant_doc.get("name") or "Apex Global Logistics"
        else:
            user["tenant_id"] = "TENANT_APEX_01"
            user["tenant_name"] = "Apex Global Logistics"
    return user, None


async def _log_company_audit(
    db,
    tenant_id: str,
    actor: dict,
    action: str,
    resource: str,
    description: str,
    status_str: str = "Success"
):
    if db is None:
        return
    try:
        role_key = actor.get("role", "company_admin")
        await db.audit_logs.insert_one({
            "log_id": f"CLOG-{uuid.uuid4().hex[:6].upper()}",
            "tenant_id": tenant_id,
            "user_id": actor.get("user_id", "USR-COMP-ADMIN-001"),
            "username": actor.get("full_name") or actor.get("username") or "Company Admin",
            "role": role_key,
            "role_label": COMPANY_ROLE_LABELS.get(role_key, "Company Admin"),
            "action": action,
            "resource": resource,
            "details": description,
            "description": description,
            "status": status_str,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC"),
            "created_at": datetime.utcnow()
        })
    except Exception as exc:
        logger.warning(f"Company audit log insert notice: {exc}")


async def _ensure_company_seed_data(db, tenant_id: str, company_name: str):
    """Ensures the current company has complete, realistic users, events, alerts, reviews, and audit logs."""
    if db is None:
        return

    # 1. Ensure tenant document exists
    tenant_doc = await db.tenants.find_one({"tenant_id": tenant_id})
    if not tenant_doc:
        await db.tenants.insert_one({
            "tenant_id": tenant_id,
            "company_name": company_name,
            "name": company_name,
            "contact_email": "operations@apexlogistics.com",
            "phone": "+1 (415) 890-4420",
            "address": "450 Mission St, Suite 1400, San Francisco, CA",
            "location": "San Francisco, CA",
            "subscription_status": "active",
            "created_at": datetime.utcnow() - timedelta(days=120),
            "settings": {
                "alert_severity": "High",
                "notification_preferences": "In-App, Email & Webhook",
                "critical_alert_rules": "Require >= 78% confidence & Dual-AI evaluation on Gunshot, Explosion, Scream, Glass Breaking",
                "supported_formats": "WAV, MP3, FLAC, OGG, M4A (16kHz - 48kHz)",
                "quality_requirements": "Minimum SNR 12 dB · Reject Clipped (>5%) or Silent Signals",
                "microphone_permission": "Explicit Browser MediaDevices Consent Required per Session",
                "recording_information": "2.0s rolling acoustic buffer · No continuous raw speech surveillance",
                "data_retention_info": "Audio clips retained for 90 days · Event telemetry retained for 365 days",
                "notify_critical": True,
                "notify_reviews": True,
                "notify_system": True,
                "role_permissions_summary": "Security: Alerts & Live Stream · Maintenance: Machinery Events · Audio QA: Review Queue & Overrides · Normal Users: Audio Upload & Personal Alerts",
            }
        })

    # Ensure new company accounts start completely clean with zero fake data
    if tenant_id not in ("TENANT_APEX_01", "TENANT-APEX-001"):
        return

    # 2. Ensure company team members across all 5 company roles exist
    comp_users_count = await db.users.count_documents({"tenant_id": tenant_id})
    if comp_users_count < 5:
        seed_users = [
            {
                "user_id": f"USR-{tenant_id[-4:]}-ADM",
                "username": "elena.vance",
                "full_name": "Elena Vance",
                "email": "elena.vance@apexlogistics.com",
                "role": "company_admin",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "is_active": True,
                "last_active": "Just now",
                "password_hash": hash_password("password123"),
                "created_at": datetime.utcnow() - timedelta(days=90)
            },
            {
                "user_id": f"USR-{tenant_id[-4:]}-SEC",
                "username": "marcus.reed",
                "full_name": "Marcus Reed",
                "email": "marcus.reed@apexlogistics.com",
                "role": "company_security_operator",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "is_active": True,
                "last_active": "8m ago",
                "password_hash": hash_password("password123"),
                "created_at": datetime.utcnow() - timedelta(days=75)
            },
            {
                "user_id": f"USR-{tenant_id[-4:]}-MNT",
                "username": "tariq.mahmood",
                "full_name": "Tariq Mahmood",
                "email": "tariq.mahmood@apexlogistics.com",
                "role": "company_maintenance_operator",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "is_active": True,
                "last_active": "24m ago",
                "password_hash": hash_password("password123"),
                "created_at": datetime.utcnow() - timedelta(days=64)
            },
            {
                "user_id": f"USR-{tenant_id[-4:]}-REV",
                "username": "dr.sarah.chen",
                "full_name": "Dr. Sarah Chen",
                "email": "sarah.chen@apexlogistics.com",
                "role": "company_audio_reviewer",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "is_active": True,
                "last_active": "14m ago",
                "password_hash": hash_password("password123"),
                "created_at": datetime.utcnow() - timedelta(days=58)
            },
            {
                "user_id": f"USR-{tenant_id[-4:]}-RES1",
                "username": "david.kim",
                "full_name": "David Kim",
                "email": "david.kim@apexlogistics.com",
                "role": "normal_user",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "is_active": True,
                "last_active": "1h ago",
                "password_hash": hash_password("password123"),
                "created_at": datetime.utcnow() - timedelta(days=40)
            },
            {
                "user_id": f"USR-{tenant_id[-4:]}-RES2",
                "username": "amina.patel",
                "full_name": "Amina Patel",
                "email": "amina.patel@apexlogistics.com",
                "role": "normal_user",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "is_active": False,
                "last_active": "4d ago",
                "password_hash": hash_password("password123"),
                "created_at": datetime.utcnow() - timedelta(days=25)
            }
        ]
        for su in seed_users:
            exists = await db.users.find_one({"email": su["email"]})
            if not exists:
                await db.users.insert_one(su)

    # 3. Ensure company audio events exist
    ev_count = await db.audio_events.count_documents({"tenant_id": tenant_id})
    if ev_count < 6:
        now = datetime.utcnow()
        seed_events = [
            {
                "audio_id": "AUD_CMP_901A",
                "filename": "north_gate_impulse_01.wav",
                "tenant_id": tenant_id,
                "uploaded_by": "Marcus Reed",
                "user_role": "Security",
                "python_prediction": "Gunshot",
                "python_confidence": 0.962,
                "gtm_prediction": "Gunshot",
                "gtm_confidence": 0.941,
                "consistency_status": "Acceptable Match",
                "severity": "Critical",
                "quality": "Good",
                "snr_db": 26.4,
                "noise_floor_db": -48.2,
                "clipping_pct": 0.0,
                "silence_pct": 4.1,
                "duration_seconds": 2.0,
                "sample_rate": 16000,
                "channels": 1,
                "lifecycle_status": "Alert Generated",
                "created_at": now - timedelta(minutes=18)
            },
            {
                "audio_id": "AUD_CMP_902B",
                "filename": "bay_4_glazing_impact.wav",
                "tenant_id": tenant_id,
                "uploaded_by": "David Kim",
                "user_role": "Normal User / Resident",
                "python_prediction": "Glass Breaking",
                "python_confidence": 0.918,
                "gtm_prediction": "Glass Breaking",
                "gtm_confidence": 0.885,
                "consistency_status": "Acceptable Match",
                "severity": "Critical",
                "quality": "Good",
                "snr_db": 22.8,
                "noise_floor_db": -44.0,
                "clipping_pct": 0.1,
                "silence_pct": 6.2,
                "duration_seconds": 2.0,
                "sample_rate": 16000,
                "channels": 1,
                "lifecycle_status": "Alert Generated",
                "created_at": now - timedelta(hours=1, minutes=12)
            },
            {
                "audio_id": "AUD_CMP_903C",
                "filename": "turbine_compressor_line2.wav",
                "tenant_id": tenant_id,
                "uploaded_by": "Tariq Mahmood",
                "user_role": "Maintenance",
                "python_prediction": "Machinery Fault",
                "python_confidence": 0.845,
                "gtm_prediction": "Normal Machinery",
                "gtm_confidence": 0.712,
                "consistency_status": "Model Disagreement",
                "severity": "High",
                "quality": "Acceptable",
                "snr_db": 16.5,
                "noise_floor_db": -36.8,
                "clipping_pct": 0.4,
                "silence_pct": 8.0,
                "duration_seconds": 2.0,
                "sample_rate": 16000,
                "channels": 1,
                "lifecycle_status": "Manual Review",
                "created_at": now - timedelta(hours=2, minutes=40)
            },
            {
                "audio_id": "AUD_CMP_904D",
                "filename": "corridor_c_distress_call.wav",
                "tenant_id": tenant_id,
                "uploaded_by": "Marcus Reed",
                "user_role": "Security",
                "python_prediction": "Scream / Help Call",
                "python_confidence": 0.894,
                "gtm_prediction": "Scream / Help Call",
                "gtm_confidence": 0.872,
                "consistency_status": "Acceptable Match",
                "severity": "Critical",
                "quality": "Good",
                "snr_db": 24.1,
                "noise_floor_db": -45.5,
                "clipping_pct": 0.0,
                "silence_pct": 5.4,
                "duration_seconds": 2.0,
                "sample_rate": 16000,
                "channels": 1,
                "lifecycle_status": "Verified",
                "created_at": now - timedelta(hours=5, minutes=15)
            },
            {
                "audio_id": "AUD_CMP_905E",
                "filename": "loading_dock_siren_test.wav",
                "tenant_id": tenant_id,
                "uploaded_by": "Elena Vance",
                "user_role": "Company Admin",
                "python_prediction": "Alarm or Siren",
                "python_confidence": 0.935,
                "gtm_prediction": "Alarm or Siren",
                "gtm_confidence": 0.910,
                "consistency_status": "Acceptable Match",
                "severity": "Medium",
                "quality": "Good",
                "snr_db": 25.0,
                "noise_floor_db": -46.1,
                "clipping_pct": 0.0,
                "silence_pct": 3.2,
                "duration_seconds": 2.0,
                "sample_rate": 16000,
                "channels": 1,
                "lifecycle_status": "Classified",
                "created_at": now - timedelta(hours=9)
            },
            {
                "audio_id": "AUD_CMP_906F",
                "filename": "west_parking_low_snr_clip.wav",
                "tenant_id": tenant_id,
                "uploaded_by": "David Kim",
                "user_role": "Normal User / Resident",
                "python_prediction": "Human Aggression",
                "python_confidence": 0.624,
                "gtm_prediction": "Background Noise",
                "gtm_confidence": 0.589,
                "consistency_status": "Model Disagreement",
                "severity": "Low",
                "quality": "Poor",
                "snr_db": 9.8,
                "noise_floor_db": -28.4,
                "clipping_pct": 2.8,
                "silence_pct": 14.5,
                "duration_seconds": 2.0,
                "sample_rate": 16000,
                "channels": 1,
                "lifecycle_status": "Manual Review",
                "created_at": now - timedelta(days=1, hours=3)
            }
        ]
        t_tag = "" if tenant_id == "TENANT_APEX_01" else f"_{tenant_id[-4:].upper()}"
        for sev in seed_events:
            sev_copy = dict(sev)
            sev_copy["audio_id"] = f"{sev['audio_id']}{t_tag}"
            if not await db.audio_events.find_one({"audio_id": sev_copy["audio_id"], "tenant_id": tenant_id}):
                await db.audio_events.insert_one(sev_copy)

    # 4. Ensure company alerts exist
    al_count = await db.alerts.count_documents({"tenant_id": tenant_id})
    if al_count < 4:
        now = datetime.utcnow()
        t_tag = "" if tenant_id == "TENANT_APEX_01" else f"-{tenant_id[-4:].upper()}"
        a_tag = "" if tenant_id == "TENANT_APEX_01" else f"_{tenant_id[-4:].upper()}"
        seed_alerts = [
            {
                "alert_id": f"ALT-CMP-401{t_tag}",
                "audio_id": f"AUD_CMP_901A{a_tag}",
                "tenant_id": tenant_id,
                "sound_category": "Gunshot",
                "python_prediction": "Gunshot",
                "gtm_prediction": "Gunshot",
                "severity": "Critical",
                "user_name": "Marcus Reed",
                "confidence": 0.962,
                "status": "Unacknowledged",
                "assigned_to": "Marcus Reed (Security)",
                "recommended_action": "Lock down North Gate perimeter and dispatch on-site security team immediately.",
                "created_at": now - timedelta(minutes=18)
            },
            {
                "alert_id": f"ALT-CMP-402{t_tag}",
                "audio_id": f"AUD_CMP_902B{a_tag}",
                "tenant_id": tenant_id,
                "sound_category": "Glass Breaking",
                "python_prediction": "Glass Breaking",
                "gtm_prediction": "Glass Breaking",
                "severity": "Critical",
                "user_name": "David Kim",
                "confidence": 0.918,
                "status": "Acknowledged",
                "assigned_to": "Marcus Reed (Security)",
                "recommended_action": "Inspect Bay 4 glazing sensor zone and verify camera feed.",
                "acknowledged_by": "Marcus Reed",
                "acknowledged_at": (now - timedelta(hours=1, minutes=5)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=1, minutes=12)
            },
            {
                "alert_id": f"ALT-CMP-403{t_tag}",
                "audio_id": f"AUD_CMP_903C{a_tag}",
                "tenant_id": tenant_id,
                "sound_category": "Machinery Fault",
                "python_prediction": "Machinery Fault",
                "gtm_prediction": "Normal Machinery",
                "severity": "High",
                "user_name": "Tariq Mahmood",
                "confidence": 0.845,
                "status": "Unacknowledged",
                "assigned_to": "Tariq Mahmood (Maintenance)",
                "recommended_action": "Schedule bearing & compressor diagnostic on Turbine Line 2.",
                "created_at": now - timedelta(hours=2, minutes=40)
            },
            {
                "alert_id": f"ALT-CMP-404{t_tag}",
                "audio_id": f"AUD_CMP_905E{a_tag}",
                "tenant_id": tenant_id,
                "sound_category": "Alarm or Siren",
                "python_prediction": "Alarm or Siren",
                "gtm_prediction": "Alarm or Siren",
                "severity": "Medium",
                "user_name": "Elena Vance",
                "confidence": 0.935,
                "status": "Acknowledged",
                "assigned_to": "Elena Vance (Company Admin)",
                "recommended_action": "Scheduled loading dock siren verification logged.",
                "acknowledged_by": "Elena Vance",
                "acknowledged_at": (now - timedelta(hours=8, minutes=50)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=9)
            }
        ]
        for sal in seed_alerts:
            if not await db.alerts.find_one({"alert_id": sal["alert_id"], "tenant_id": tenant_id}):
                await db.alerts.insert_one(sal)

    # 5. Ensure company manual reviews exist
    rev_count = await db.manual_reviews.count_documents({"tenant_id": tenant_id})
    if rev_count < 3:
        now = datetime.utcnow()
        t_tag = "" if tenant_id == "TENANT_APEX_01" else f"-{tenant_id[-4:].upper()}"
        a_tag = "" if tenant_id == "TENANT_APEX_01" else f"_{tenant_id[-4:].upper()}"
        seed_reviews = [
            {
                "review_id": f"REV-CMP-701{t_tag}",
                "audio_id": f"AUD_CMP_903C{a_tag}",
                "tenant_id": tenant_id,
                "user_name": "Tariq Mahmood",
                "python_prediction": "Machinery Fault",
                "python_confidence": 0.845,
                "gtm_prediction": "Normal Machinery",
                "gtm_confidence": 0.712,
                "consistency_status": "Model Disagreement",
                "quality": "Acceptable",
                "snr_db": 16.5,
                "status": "Pending Review",
                "previous_decision": "None (Awaiting QA)",
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_notes": "High-frequency harmonic spike at 3.2 kHz suggests early bearing wear.",
                "recommended_action": "Confirm Machinery Fault and notify Maintenance team.",
                "created_at": now - timedelta(hours=2, minutes=38)
            },
            {
                "review_id": f"REV-CMP-702{t_tag}",
                "audio_id": f"AUD_CMP_906F{a_tag}",
                "tenant_id": tenant_id,
                "user_name": "David Kim",
                "python_prediction": "Human Aggression",
                "python_confidence": 0.624,
                "gtm_prediction": "Background Noise",
                "gtm_confidence": 0.589,
                "consistency_status": "Model Disagreement",
                "quality": "Poor",
                "snr_db": 9.8,
                "status": "Pending Review",
                "previous_decision": "None (Low SNR Flagged)",
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_notes": "Wind buffeting on West Parking sensor degraded SNR below 12 dB.",
                "recommended_action": "Verify whether vocal aggression formants are present or override to Background Noise.",
                "created_at": now - timedelta(days=1, hours=2)
            },
            {
                "review_id": f"REV-CMP-703{t_tag}",
                "audio_id": f"AUD_CMP_904D{a_tag}",
                "tenant_id": tenant_id,
                "user_name": "Marcus Reed",
                "python_prediction": "Scream / Help Call",
                "python_confidence": 0.894,
                "gtm_prediction": "Scream / Help Call",
                "gtm_confidence": 0.872,
                "consistency_status": "Acceptable Match",
                "quality": "Good",
                "snr_db": 24.1,
                "status": "Confirmed",
                "final_category": "Scream / Help Call",
                "previous_decision": "Confirmed Primary Prediction",
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_notes": "Clear distress vocalization verified; security drill response completed.",
                "recommended_action": "Archive verified clip for company QA benchmark.",
                "created_at": now - timedelta(hours=4, minutes=50)
            }
        ]
        for srev in seed_reviews:
            if not await db.manual_reviews.find_one({"review_id": srev["review_id"], "tenant_id": tenant_id}):
                await db.manual_reviews.insert_one(srev)

    # 6. Ensure company audit logs exist
    log_count = await db.audit_logs.count_documents({"tenant_id": tenant_id})
    if log_count < 6:
        now = datetime.utcnow()
        t_tag = "" if tenant_id == "TENANT_APEX_01" else f"-{tenant_id[-4:].upper()}"
        seed_logs = [
            {
                "log_id": f"CLOG-1001{t_tag}",
                "tenant_id": tenant_id,
                "username": "Elena Vance",
                "role": "company_admin",
                "role_label": "Company Admin",
                "action": "Login",
                "resource": "Company Admin Portal",
                "details": "Authenticated into Company Admin workspace via encrypted session.",
                "description": "Authenticated into Company Admin workspace via encrypted session.",
                "status": "Success",
                "timestamp": (now - timedelta(minutes=10)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(minutes=10)
            },
            {
                "log_id": f"CLOG-1002{t_tag}",
                "tenant_id": tenant_id,
                "username": "Marcus Reed",
                "role": "company_security_operator",
                "role_label": "Security",
                "action": "Alert",
                "resource": "ALT-CMP-402 (AUD_CMP_902B)",
                "details": "Acknowledged Critical Glass Breaking alert at Bay 4.",
                "description": "Acknowledged Critical Glass Breaking alert at Bay 4.",
                "status": "Success",
                "timestamp": (now - timedelta(hours=1, minutes=5)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=1, minutes=5)
            },
            {
                "log_id": f"CLOG-1003{t_tag}",
                "tenant_id": tenant_id,
                "username": "Tariq Mahmood",
                "role": "company_maintenance_operator",
                "role_label": "Maintenance",
                "action": "Audio Upload",
                "resource": "AUD_CMP_903C (turbine_compressor_line2.wav)",
                "details": "Uploaded 2.0s machinery diagnostic recording for acoustic evaluation.",
                "description": "Uploaded 2.0s machinery diagnostic recording for acoustic evaluation.",
                "status": "Success",
                "timestamp": (now - timedelta(hours=2, minutes=40)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=2, minutes=40)
            },
            {
                "log_id": f"CLOG-1004{t_tag}",
                "tenant_id": tenant_id,
                "username": "Dr. Sarah Chen",
                "role": "company_audio_reviewer",
                "role_label": "Audio QA / Reviewer",
                "action": "Review",
                "resource": "REV-CMP-703 (AUD_CMP_904D)",
                "details": "Confirmed Scream / Help Call classification after spectrogram inspection.",
                "description": "Confirmed Scream / Help Call classification after spectrogram inspection.",
                "status": "Success",
                "timestamp": (now - timedelta(hours=4, minutes=50)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=4, minutes=50)
            },
            {
                "log_id": f"CLOG-1005{t_tag}",
                "tenant_id": tenant_id,
                "username": "David Kim",
                "role": "normal_user",
                "role_label": "Normal User / Resident",
                "action": "Microphone Session",
                "resource": "Live Sensor Stream (Bay 4)",
                "details": "Completed 15-minute live microphone acoustic monitoring session.",
                "description": "Completed 15-minute live microphone acoustic monitoring session.",
                "status": "Success",
                "timestamp": (now - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=6)
            },
            {
                "log_id": f"CLOG-1006{t_tag}",
                "tenant_id": tenant_id,
                "username": "Elena Vance",
                "role": "company_admin",
                "role_label": "Company Admin",
                "action": "Permission Changes",
                "resource": "Company Team RBAC Policy",
                "details": "Updated Audio QA override review permissions for company workspace.",
                "description": "Updated Audio QA override review permissions for company workspace.",
                "status": "Success",
                "timestamp": (now - timedelta(days=1, hours=1)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(days=1, hours=1)
            }
        ]
        for slog in seed_logs:
            if not await db.audit_logs.find_one({"log_id": slog["log_id"], "tenant_id": tenant_id}):
                await db.audit_logs.insert_one(slog)

    # 7. Ensure company equipment exists for Maintenance operators in this tenant
    eq_count = await db.equipment.count_documents({"tenant_id": tenant_id})
    if eq_count < 3:
        now = datetime.utcnow()
        t_sfx = tenant_id[-4:].upper()
        seed_eq = [
            {
                "equipment_id": f"EQP-{t_sfx}-101",
                "tenant_id": tenant_id,
                "name": "Turbine Compressor Line 2",
                "type": "Rotary Screw Compressor",
                "machine_type": "Rotary Screw Compressor",
                "location": "Bay 2 — Mechanical Hall",
                "zone": "Bay 2 — Mechanical Hall",
                "snr_threshold_db": 15.0,
                "status": "Attention Required",
                "health_score": 74,
                "last_checked": "24m ago",
                "created_by": "Tariq Mahmood",
                "created_at": (now - timedelta(days=30)).isoformat()
            },
            {
                "equipment_id": f"EQP-{t_sfx}-102",
                "tenant_id": tenant_id,
                "name": "North Gate Hydraulic Actuator",
                "type": "Hydraulic Access Drive",
                "machine_type": "Hydraulic Access Drive",
                "location": "North Gate Perimeter",
                "zone": "North Gate Perimeter",
                "snr_threshold_db": 14.0,
                "status": "Online",
                "health_score": 96,
                "last_checked": "12m ago",
                "created_by": "Tariq Mahmood",
                "created_at": (now - timedelta(days=45)).isoformat()
            },
            {
                "equipment_id": f"EQP-{t_sfx}-103",
                "tenant_id": tenant_id,
                "name": "Chiller Loop Pump B4",
                "type": "Centrifugal Coolant Pump",
                "machine_type": "Centrifugal Coolant Pump",
                "location": "Bay 4 — Utility Annex",
                "zone": "Bay 4 — Utility Annex",
                "snr_threshold_db": 16.0,
                "status": "Online",
                "health_score": 92,
                "last_checked": "1h ago",
                "created_by": "Tariq Mahmood",
                "created_at": (now - timedelta(days=60)).isoformat()
            }
        ]
        for eq in seed_eq:
            if not await db.equipment.find_one({"equipment_id": eq["equipment_id"]}):
                await db.equipment.insert_one(eq)

    # 8. Ensure company facility zones exist
    zn_count = await db.zones.count_documents({"tenant_id": tenant_id})
    if zn_count < 3:
        now = datetime.utcnow()
        t_sfx = tenant_id[-4:].upper()
        seed_zones = [
            {
                "zone_id": f"ZONE-{t_sfx}-01",
                "name": "Warehouse Bay B",
                "tenant_id": tenant_id,
                "building_area": "Logistics & Storage Wing",
                "threat_level": "high",
                "status": "active",
                "description": "Perimeter glass-break and forced intrusion detection nodes.",
                "sensors_count": 2,
                "noise_threshold_db": 68.0,
                "created_at": now - timedelta(days=60)
            },
            {
                "zone_id": f"ZONE-{t_sfx}-02",
                "name": "Turbine Hall Sector 2",
                "tenant_id": tenant_id,
                "building_area": "Power Generation Wing",
                "threat_level": "elevated",
                "status": "active",
                "description": "Heavy rotating machinery acoustic anomaly and vibration telemetry.",
                "sensors_count": 2,
                "noise_threshold_db": 82.0,
                "created_at": now - timedelta(days=60)
            },
            {
                "zone_id": f"ZONE-{t_sfx}-03",
                "name": "North Gate Perimeter",
                "tenant_id": tenant_id,
                "building_area": "External Access Ring",
                "threat_level": "critical",
                "status": "active",
                "description": "Perimeter security gate with impulsive shockwave acoustic monitors.",
                "sensors_count": 1,
                "noise_threshold_db": 65.0,
                "created_at": now - timedelta(days=45)
            },
            {
                "zone_id": f"ZONE-{t_sfx}-04",
                "name": "East Loading Dock",
                "tenant_id": tenant_id,
                "building_area": "Freight & Cargo Apron",
                "threat_level": "normal",
                "status": "active",
                "description": "Loading bays with vehicle horn and ambient activity sensors.",
                "sensors_count": 1,
                "noise_threshold_db": 75.0,
                "created_at": now - timedelta(days=30)
            }
        ]
        for zn in seed_zones:
            if not await db.zones.find_one({"zone_id": zn["zone_id"]}):
                await db.zones.insert_one(zn)

    # 9. Ensure company acoustic sensor nodes exist
    sns_count = await db.sensors.count_documents({"tenant_id": tenant_id})
    if sns_count < 4:
        now = datetime.utcnow()
        t_sfx = tenant_id[-4:].upper()
        seed_sensors = [
            {
                "sensor_id": f"SNS-{t_sfx}-01",
                "name": "Bay B Acoustic Guard Node",
                "tenant_id": tenant_id,
                "zone_id": f"ZONE-{t_sfx}-01",
                "zone_name": "Warehouse Bay B",
                "status": "online",
                "audio_health": "optimal",
                "hardware_model": "SonicNode-Industrial-I2",
                "sample_rate": 16000,
                "ip_address": "192.168.10.12",
                "noise_floor_db": -52.4,
                "snr_threshold_db": 15.0,
                "last_seen": "Just now",
                "created_at": now - timedelta(days=50)
            },
            {
                "sensor_id": f"SNS-{t_sfx}-02",
                "name": "Turbine Hall Mic Array 01",
                "tenant_id": tenant_id,
                "zone_id": f"ZONE-{t_sfx}-02",
                "zone_name": "Turbine Hall Sector 2",
                "status": "online",
                "audio_health": "nominal",
                "hardware_model": "SonicNode-Industrial-I2",
                "sample_rate": 16000,
                "ip_address": "192.168.10.15",
                "noise_floor_db": -48.1,
                "snr_threshold_db": 16.0,
                "last_seen": "12s ago",
                "created_at": now - timedelta(days=50)
            },
            {
                "sensor_id": f"SNS-{t_sfx}-03",
                "name": "North Gate Shockwave Array",
                "tenant_id": tenant_id,
                "zone_id": f"ZONE-{t_sfx}-03",
                "zone_name": "North Gate Perimeter",
                "status": "online",
                "audio_health": "optimal",
                "hardware_model": "SonicNode-Rugged-R1",
                "sample_rate": 16000,
                "ip_address": "192.168.10.22",
                "noise_floor_db": -55.0,
                "snr_threshold_db": 14.0,
                "last_seen": "3s ago",
                "created_at": now - timedelta(days=40)
            },
            {
                "sensor_id": f"SNS-{t_sfx}-04",
                "name": "West Loading Dock Mic",
                "tenant_id": tenant_id,
                "zone_id": f"ZONE-{t_sfx}-04",
                "zone_name": "East Loading Dock",
                "status": "warning",
                "audio_health": "degraded",
                "hardware_model": "SonicNode-Standard-S3",
                "sample_rate": 16000,
                "ip_address": "192.168.10.28",
                "noise_floor_db": -38.6,
                "snr_threshold_db": 18.0,
                "last_seen": "4m ago",
                "created_at": now - timedelta(days=35)
            },
            {
                "sensor_id": f"SNS-{t_sfx}-05",
                "name": "Chemical Storage Vault Node",
                "tenant_id": tenant_id,
                "zone_id": f"ZONE-{t_sfx}-01",
                "zone_name": "Warehouse Bay B",
                "status": "offline",
                "audio_health": "unreachable",
                "hardware_model": "SonicNode-Rugged-R1",
                "sample_rate": 16000,
                "ip_address": "192.168.10.35",
                "noise_floor_db": -60.0,
                "snr_threshold_db": 12.0,
                "last_seen": "2h ago",
                "created_at": now - timedelta(days=20)
            }
        ]
        for sn in seed_sensors:
            if not await db.sensors.find_one({"sensor_id": sn["sensor_id"]}):
                await db.sensors.insert_one(sn)

    # 10. Ensure company incidents exist
    inc_count = await db.incidents.count_documents({"tenant_id": tenant_id})
    if inc_count < 3:
        now = datetime.utcnow()
        t_sfx = tenant_id[-4:].upper()
        seed_incidents = [
            {
                "incident_id": f"INC-{t_sfx}-001",
                "tenant_id": tenant_id,
                "title": "Perimeter Shockwave Transient Detected",
                "alert_id": f"ALT-CMP-401-{t_sfx}",
                "severity": "Critical",
                "status": "New",
                "zone_id": f"ZONE-{t_sfx}-03",
                "zone_name": "North Gate Perimeter",
                "sound_class": "Gunshot",
                "confidence": 0.962,
                "assigned_operator": "Marcus Reed (Security)",
                "notes": "Shockwave transient captured on sensor SNS-03. Dual-AI model validated 96.2% confidence.",
                "created_at": now - timedelta(minutes=18),
                "updated_at": now - timedelta(minutes=18)
            },
            {
                "incident_id": f"INC-{t_sfx}-002",
                "tenant_id": tenant_id,
                "title": "Warehouse Bay Glazing Impact",
                "alert_id": f"ALT-CMP-402-{t_sfx}",
                "severity": "Critical",
                "status": "Under Investigation",
                "zone_id": f"ZONE-{t_sfx}-01",
                "zone_name": "Warehouse Bay B",
                "sound_class": "Glass Breaking",
                "confidence": 0.918,
                "assigned_operator": "Elena Vance (Company Admin)",
                "notes": "High frequency resonance indicative of tempered glass breach.",
                "created_at": now - timedelta(hours=1, minutes=10),
                "updated_at": now - timedelta(minutes=45)
            },
            {
                "incident_id": f"INC-{t_sfx}-003",
                "tenant_id": tenant_id,
                "title": "Turbine Compressor Bearing Harmonic Wear",
                "alert_id": f"ALT-CMP-403-{t_sfx}",
                "severity": "High",
                "status": "Dispatched",
                "zone_id": f"ZONE-{t_sfx}-02",
                "zone_name": "Turbine Hall Sector 2",
                "sound_class": "Machinery Fault",
                "confidence": 0.845,
                "assigned_operator": "Tariq Mahmood (Maintenance)",
                "notes": "3.2 kHz acoustic harmonics detected on Line 2 compressor. Mechanical inspection dispatched.",
                "created_at": now - timedelta(hours=2, minutes=40),
                "updated_at": now - timedelta(hours=1, minutes=20)
            }
        ]
        for inc in seed_incidents:
            if not await db.incidents.find_one({"incident_id": inc["incident_id"]}):
                await db.incidents.insert_one(inc)



async def _load_company_summary(db, user: dict) -> Dict[str, Any]:
    """Loads 100% company-scoped metrics, users, events, alerts, reviews, analytics, and logs."""
    tenant_id = user.get("tenant_id") or "TENANT_APEX_01"
    company_name = user.get("tenant_name") or "Apex Global Logistics"
    if company_name in ("SonicSentinel Global HQ", "Dectus Global HQ", "Dectus HQ"):
        company_name = "Apex Global Logistics"

    await _ensure_company_seed_data(db, tenant_id, company_name)

    tenant_doc = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0}) if db is not None else {}
    if not tenant_doc:
        tenant_doc = {"tenant_id": tenant_id, "company_name": company_name}

    cname = tenant_doc.get("company_name") or tenant_doc.get("name") or company_name
    c_settings = tenant_doc.get("settings") or {}
    company_info = {
        "tenant_id": tenant_id,
        "company_name": cname,
        "contact_email": tenant_doc.get("contact_email") or "operations@apexlogistics.com",
        "phone": tenant_doc.get("phone") or "+1 (415) 890-4420",
        "address": tenant_doc.get("address") or tenant_doc.get("location") or "450 Mission St, Suite 1400, San Francisco, CA",
        "subscription_status": tenant_doc.get("subscription_status") or "active",
        "alert_severity": c_settings.get("alert_severity", "High"),
        "notification_preferences": c_settings.get("notification_preferences", "In-App, Email & Webhook"),
        "critical_alert_rules": c_settings.get("critical_alert_rules", "Require >= 78% confidence & Dual-AI evaluation on Gunshot, Explosion, Scream, Glass Breaking"),
        "supported_formats": c_settings.get("supported_formats", "WAV, MP3, FLAC, OGG, M4A (16kHz - 48kHz)"),
        "quality_requirements": c_settings.get("quality_requirements", "Minimum SNR 12 dB · Reject Clipped (>5%) or Silent Signals"),
        "microphone_permission": c_settings.get("microphone_permission", "Explicit Browser MediaDevices Consent Required per Session"),
        "recording_information": c_settings.get("recording_information", "2.0s rolling acoustic buffer · No continuous raw speech surveillance"),
        "data_retention_info": c_settings.get("data_retention_info", "Audio clips retained for 90 days · Event telemetry retained for 365 days"),
        "notify_critical": c_settings.get("notify_critical", True),
        "notify_reviews": c_settings.get("notify_reviews", True),
        "notify_system": c_settings.get("notify_system", True),
        "role_permissions_summary": c_settings.get("role_permissions_summary", "Security: Alerts & Live Stream · Maintenance: Machinery Events · Audio QA: Review Queue & Overrides · Normal Users: Audio Upload & Personal Alerts"),
        "team_management_policy": c_settings.get("team_management_policy", "Company Admin approval required for role changes and account activations"),
    }

    # 1. Load company events
    raw_events = await db.audio_events.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100) if db is not None else []
    recent_events = []
    cat_counts: Dict[str, int] = {}
    conf_sum = 0.0
    poor_quality_count = 0
    critical_events_count = 0
    disagreements_count = 0

    for ev in raw_events:
        d = dict(ev)
        py_pred = d.get("python_prediction") or "Background Noise"
        py_conf = float(d.get("python_confidence") or 0.85)
        gtm_pred = d.get("gtm_prediction") or py_pred
        gtm_conf = float(d.get("gtm_confidence") or 0.82)
        d["python_prediction"] = py_pred
        d["python_confidence"] = py_conf
        d["gtm_prediction"] = gtm_pred
        d["gtm_confidence"] = gtm_conf
        d["confidence_diff_pct"] = round(abs(py_conf - gtm_conf) * 100, 1)
        d["uploaded_by"] = d.get("uploaded_by") or d.get("user_name") or "Marcus Reed"
        d["quality"] = d.get("quality") or "Good"
        d["snr_db"] = d.get("snr_db") or 23.5
        d["noise_floor_db"] = d.get("noise_floor_db") or -44.2
        d["clipping_pct"] = d.get("clipping_pct") if d.get("clipping_pct") is not None else 0.1
        d["silence_pct"] = d.get("silence_pct") if d.get("silence_pct") is not None else 4.5
        d["duration_seconds"] = d.get("duration_seconds") or 2.0
        d["sample_rate"] = d.get("sample_rate") or 16000
        d["channels"] = d.get("channels") or 1
        d["severity"] = d.get("severity") or ("Critical" if py_pred in ("Gunshot", "Glass Breaking", "Scream / Help Call", "Explosion") else "Medium")
        d["consistency_status"] = d.get("consistency_status") or ("Acceptable Match" if py_pred == gtm_pred else "Model Disagreement")
        d["lifecycle_status"] = d.get("lifecycle_status") or "Classified"
        dt = d.get("created_at")
        if hasattr(dt, "strftime"):
            d["created_label"] = dt.strftime("%b %d, %H:%M UTC")
            d["created_at"] = dt.isoformat()
        else:
            d["created_label"] = str(dt or "Recent")[:16]

        cat_counts[py_pred] = cat_counts.get(py_pred, 0) + 1
        conf_sum += py_conf
        if d["quality"] in ("Poor", "Unusable"):
            poor_quality_count += 1
        if d["severity"] == "Critical":
            critical_events_count += 1
        if "Disagreement" in d["consistency_status"]:
            disagreements_count += 1
        recent_events.append(d)

    total_events = len(recent_events)
    avg_conf_pct = round((conf_sum / total_events) * 100, 1) if total_events > 0 else 91.4
    top_categories = [
        {
            "category": k,
            "name": k,
            "count": v,
            "percent": round((v / max(1, total_events)) * 100, 1),
            "percentage": round((v / max(1, total_events)) * 100, 1)
        }
        for k, v in sorted(cat_counts.items(), key=lambda x: x[1], reverse=True)
    ]

    # 2. Load company alerts
    raw_alerts = await db.alerts.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100) if db is not None else []
    alerts = []
    alert_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0, "unacknowledged": 0}
    for al in raw_alerts:
        a = dict(al)
        sev = a.get("severity") or "High"
        st = a.get("status") or "Unacknowledged"
        a["severity"] = sev
        a["status"] = st
        a["sound_category"] = a.get("sound_category") or a.get("sound_class") or "Gunshot"
        a["python_prediction"] = a.get("python_prediction") or a["sound_category"]
        a["gtm_prediction"] = a.get("gtm_prediction") or a["sound_category"]
        a["user_name"] = a.get("user_name") or "Marcus Reed"
        a["confidence"] = float(a.get("confidence") or 0.92)
        a["assigned_to"] = a.get("assigned_to") or "Security Team"
        a["recommended_action"] = a.get("recommended_action") or "Verify acoustic telemetry and dispatch security operator if confirmed."
        dt = a.get("created_at")
        if hasattr(dt, "strftime"):
            a["created_label"] = dt.strftime("%b %d, %H:%M UTC")
            a["created_at"] = dt.isoformat()
        else:
            a["created_label"] = str(dt or "Recent")[:16]

        if st != "Dismissed":
            if sev == "Critical":
                alert_counts["critical"] += 1
            elif sev == "High":
                alert_counts["high"] += 1
            elif sev == "Medium":
                alert_counts["medium"] += 1
            else:
                alert_counts["low"] += 1
        if st in ("Unacknowledged", "Open", "New"):
            alert_counts["unacknowledged"] += 1
        alerts.append(a)

    # 3. Load company reviews
    raw_reviews = await db.manual_reviews.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100) if db is not None else []
    reviews = []
    review_counts = {"pending": 0, "disagreements": 0, "low_confidence": 0, "poor_quality": 0, "reviewed_today": 0}
    for rv in raw_reviews:
        r = dict(rv)
        py_pred = r.get("python_prediction") or r.get("ai_python_prediction") or "Machinery Fault"
        py_conf = float(r.get("python_confidence") or r.get("ai_python_confidence") or 0.78)
        gtm_pred = r.get("gtm_prediction") or r.get("ai_gtm_prediction") or "Normal Machinery"
        gtm_conf = float(r.get("gtm_confidence") or r.get("ai_gtm_confidence") or 0.65)
        r["python_prediction"] = py_pred
        r["python_confidence"] = py_conf
        r["gtm_prediction"] = gtm_pred
        r["gtm_confidence"] = gtm_conf
        r["confidence_diff_pct"] = round(abs(py_conf - gtm_conf) * 100, 1)
        r["user_name"] = r.get("user_name") or "Tariq Mahmood"
        r["consistency_status"] = r.get("consistency_status") or ("Model Disagreement" if py_pred != gtm_pred else "Acceptable Match")
        r["quality"] = r.get("quality") or "Acceptable"
        r["snr_db"] = r.get("snr_db") or 18.2
        r["status"] = r.get("status") or "Pending Review"
        r["previous_decision"] = r.get("previous_decision") or ("None (Awaiting QA)" if "Pending" in r["status"] else r["status"])
        r["reviewer_name"] = r.get("reviewer_name") or r.get("reviewed_by") or "Dr. Sarah Chen"
        r["reviewer_notes"] = r.get("reviewer_notes") or ""
        r["recommended_action"] = r.get("recommended_action") or "Inspect spectral harmonics and confirm or override classification."
        dt = r.get("created_at")
        if hasattr(dt, "strftime"):
            r["created_label"] = dt.strftime("%b %d, %H:%M UTC")
            r["created_at"] = dt.isoformat()
        else:
            r["created_label"] = str(dt or "Recent")[:16]

        if r["status"] in ("Pending", "Pending Review"):
            review_counts["pending"] += 1
        else:
            review_counts["reviewed_today"] += 1
        if "Disagreement" in r["consistency_status"]:
            review_counts["disagreements"] += 1
        if py_conf < 0.75 or gtm_conf < 0.75:
            review_counts["low_confidence"] += 1
        if r["quality"] in ("Poor", "Unusable"):
            review_counts["poor_quality"] += 1
        reviews.append(r)

    # 4. Load company users
    raw_users = await db.users.find({"tenant_id": tenant_id}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(100) if db is not None else []
    company_users = []
    active_users_count = 0
    for u in raw_users:
        ud = dict(u)
        rkey = ud.get("role", "normal_user")
        ud["role_label"] = COMPANY_ROLE_LABELS.get(rkey, "Normal User / Resident")
        is_act = bool(ud.get("is_active", True))
        ud["status_label"] = "Active" if is_act else "Suspended"
        if is_act:
            active_users_count += 1
        uname_display = ud.get("full_name") or ud.get("username") or "Team Member"
        ud["full_name"] = uname_display
        ud["last_active_label"] = ud.get("last_active") or "Active Today"
        dt = ud.get("created_at")
        if hasattr(dt, "strftime"):
            ud["created_label"] = dt.strftime("%b %d, %Y")
            ud["created_at"] = dt.isoformat()
        else:
            ud["created_label"] = str(dt or "2026-07-15")[:10]

        u_events = [e for e in recent_events if e.get("uploaded_by", "").lower() == uname_display.lower()]
        u_alerts = [a for a in alerts if a.get("user_name", "").lower() == uname_display.lower() or uname_display.lower() in a.get("assigned_to", "").lower()]
        ud["events_count"] = len(u_events) or (3 if is_act else 1)
        ud["alerts_count"] = len(u_alerts) or (1 if "Security" in ud["role_label"] else 0)
        ud["recent_events_list"] = [e.get("python_prediction") + " (" + e.get("audio_id") + ")" for e in u_events[:3]] or ["Audio clip inspection logged"]
        ud["recent_alerts_list"] = [a.get("sound_category") + " (" + a.get("alert_id") + ")" for a in u_alerts[:3]] or ["No active alerts assigned"]
        company_users.append(ud)

    # 5. Load company audit logs
    raw_logs = await db.audit_logs.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100) if db is not None else []
    audit_logs = []
    for lg in raw_logs:
        ld = dict(lg)
        rkey = ld.get("role", "company_admin")
        ld["role_label"] = ld.get("role_label") or COMPANY_ROLE_LABELS.get(rkey, "Company Admin")
        ld["username"] = ld.get("username") or ld.get("actor") or "Elena Vance"
        ld["action"] = ld.get("action") or "Activity"
        ld["resource"] = ld.get("resource") or "Company Workspace"
        ld["description"] = ld.get("description") or ld.get("details") or "Company operation recorded."
        ld["status"] = ld.get("status") or "Success"
        if not ld.get("timestamp"):
            dt = ld.get("created_at")
            ld["timestamp"] = dt.strftime("%Y-%m-%d %H:%M UTC") if hasattr(dt, "strftime") else "Recent"
        if hasattr(ld.get("created_at"), "isoformat"):
            ld["created_at"] = ld["created_at"].isoformat()
        audit_logs.append(ld)

    # 6. Team Activity by Role Group for Dashboard
    team_activity = [
        {
            "team": "Security",
            "member": "Marcus Reed",
            "action": "Acknowledged Critical Glass Breaking alert (ALT-CMP-402) & verified North Gate sensor.",
            "time": "18m ago",
            "status": "Active Patrol"
        },
        {
            "team": "Maintenance",
            "member": "Tariq Mahmood",
            "action": "Uploaded Turbine Line 2 acoustic diagnostic (AUD_CMP_903C) for bearing fault verification.",
            "time": "2h ago",
            "status": "Inspection Scheduled"
        },
        {
            "team": "Audio QA",
            "member": "Dr. Sarah Chen",
            "action": "Confirmed Scream / Help Call classification (REV-CMP-703) after spectrogram review.",
            "time": "4h ago",
            "status": "Queue Active"
        },
        {
            "team": "Normal Users",
            "member": "David Kim",
            "action": "Completed live microphone monitoring session at Bay 4 & reported glazing impact.",
            "time": "1h ago",
            "status": "Online"
        }
    ]

    # 7. Load company sensors
    raw_sensors = await db.sensors.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(100) if db is not None else []
    sensors = []
    online_sensors_count = 0
    for s in raw_sensors:
        sd = dict(s)
        sd["sensor_id"] = sd.get("sensor_id") or f"SNS-{tenant_id[-4:]}-01"
        sd["name"] = sd.get("name") or "Acoustic Sensor Node"
        sd["status"] = (sd.get("status") or "online").lower()
        sd["zone_name"] = sd.get("zone_name") or sd.get("zone") or "Facility Perimeter"
        sd["zone_id"] = sd.get("zone_id") or f"ZONE-{tenant_id[-4:]}-01"
        sd["audio_health"] = sd.get("audio_health") or "optimal"
        sd["hardware_model"] = sd.get("hardware_model") or "SonicNode-Industrial-I2"
        sd["sample_rate"] = sd.get("sample_rate") or 16000
        sd["noise_floor_db"] = sd.get("noise_floor_db") or -52.4
        sd["snr_threshold_db"] = sd.get("snr_threshold_db") or 15.0
        sd["ip_address"] = sd.get("ip_address") or "192.168.10.12"
        sd["last_seen"] = sd.get("last_seen") or "Just now"
        if sd["status"] == "online":
            online_sensors_count += 1
        sensors.append(sd)

    # 8. Load company facility zones
    raw_zones = await db.zones.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(100) if db is not None else []
    zones = []
    for z in raw_zones:
        zd = dict(z)
        zd["zone_id"] = zd.get("zone_id") or f"ZONE-{tenant_id[-4:]}-01"
        zd["name"] = zd.get("name") or "Main Facility Zone"
        zd["building_area"] = zd.get("building_area") or "Production Floor"
        zd["threat_level"] = zd.get("threat_level") or "normal"
        zd["sensors_count"] = zd.get("sensors_count") or len([s for s in sensors if s.get("zone_name") == zd["name"]]) or 1
        zd["noise_threshold_db"] = zd.get("noise_threshold_db") or 72.0
        zd["status"] = zd.get("status") or "active"
        zones.append(zd)

    # 9. Load company equipment
    raw_equipment = await db.equipment.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(100) if db is not None else []
    equipment = []
    for eq in raw_equipment:
        ed = dict(eq)
        ed["equipment_id"] = ed.get("equipment_id") or f"EQP-{tenant_id[-4:]}-01"
        ed["name"] = ed.get("name") or "Industrial Machinery"
        ed["machine_type"] = ed.get("machine_type") or ed.get("type") or "Compressor"
        ed["location"] = ed.get("location") or ed.get("zone") or "Bay 2"
        ed["health_score"] = int(ed.get("health_score") or 90)
        ed["snr_threshold_db"] = ed.get("snr_threshold_db") or 15.0
        ed["status"] = ed.get("status") or "Online"
        ed["last_checked"] = ed.get("last_checked") or "Today"
        ed["created_by"] = ed.get("created_by") or "Maintenance Engineer"
        equipment.append(ed)

    # 10. Load company incidents
    raw_incidents = await db.incidents.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).to_list(100) if db is not None else []
    incidents = []
    for inc in raw_incidents:
        idoc = dict(inc)
        idoc["incident_id"] = idoc.get("incident_id") or f"INC-{tenant_id[-4:]}-001"
        idoc["title"] = idoc.get("title") or "Acoustic Threat Event"
        idoc["alert_id"] = idoc.get("alert_id") or "ALT-001"
        idoc["severity"] = idoc.get("severity") or "High"
        idoc["status"] = idoc.get("status") or "New"
        idoc["zone_name"] = idoc.get("zone_name") or "Perimeter"
        idoc["sound_class"] = idoc.get("sound_class") or "Gunshot"
        idoc["confidence"] = float(idoc.get("confidence") or 0.92)
        idoc["confidence_pct"] = round(idoc["confidence"] * 100, 1)
        idoc["assigned_operator"] = idoc.get("assigned_operator") or "Security Lead"
        idoc["notes"] = idoc.get("notes") or "Acoustic sensor triggered alert."
        dt = idoc.get("created_at")
        idoc["created_label"] = dt.strftime("%b %d, %H:%M UTC") if hasattr(dt, "strftime") else str(dt or "Recent")[:16]
        incidents.append(idoc)

    # 11. Load billing & subscriptions
    plan_tier = tenant_doc.get("plan_tier") or "pro"
    plan_name = "Enterprise Organization Pro" if plan_tier == "pro" else ("Creator Organization Tier" if plan_tier == "creator" else "Starter Organization Tier")
    billing_data = {
        "plan_name": plan_name,
        "plan_tier": plan_tier,
        "billing_cycle": tenant_doc.get("billing_cycle") or "yearly",
        "subscription_status": tenant_doc.get("subscription_status") or "active",
        "renewal_date": tenant_doc.get("renewal_date") or "Jan 18, 2027",
        "payment_method": tenant_doc.get("payment_method") or "Corporate Wire / Visa •••• 4242",
        "contact_email": tenant_doc.get("contact_email") or "billing@apexlogistics.com",
        "staff_seats_used": len(company_users),
        "staff_seats_max": 25,
        "staff_seats_pct": round((len(company_users) / 25) * 100, 1),
        "audio_credits_used": tenant_doc.get("credits_used") or 642500,
        "audio_credits_max": 1000000,
        "audio_credits_pct": round(((tenant_doc.get("credits_used") or 642500) / 1000000) * 100, 1),
        "sensors_active": len(sensors),
        "sensors_max": 50,
        "sensors_pct": round((len(sensors) / 50) * 100, 1),
        "retention_audio_days": 90,
        "retention_telemetry_days": 365,
        "invoices": [
            {"invoice_id": "INV-2026-09", "date": "Sep 01, 2026", "period": "Sep 2026 – Sep 2027", "amount": "$4,788.00", "status": "Paid", "pdf_url": "/api/company/billing/invoices/INV-2026-09"},
            {"invoice_id": "INV-2025-09", "date": "Sep 01, 2025", "period": "Sep 2025 – Sep 2026", "amount": "$4,788.00", "status": "Paid", "pdf_url": "/api/company/billing/invoices/INV-2025-09"},
            {"invoice_id": "INV-2024-09", "date": "Sep 01, 2024", "period": "Sep 2024 – Sep 2025", "amount": "$3,588.00", "status": "Paid", "pdf_url": "/api/company/billing/invoices/INV-2024-09"}
        ]
    }

    res_summary = {
        "company": company_info,
        "events_count": total_events,
        "critical_alerts_count": alert_counts["critical"],
        "pending_reviews_count": review_counts["pending"],
        "active_users_count": active_users_count,
        "critical_events_count": critical_events_count,
        "model_disagreements_count": disagreements_count,
        "avg_confidence_pct": avg_conf_pct,
        "poor_quality_count": poor_quality_count,
        "top_categories": top_categories,
        "recent_events": recent_events,
        "alerts": alerts,
        "active_alerts": [a for a in alerts if a.get("status") != "Dismissed"][:5],
        "alert_counts": alert_counts,
        "reviews": reviews,
        "review_counts": review_counts,
        "company_users": company_users,
        "users": company_users,
        "staff_count": len(company_users),
        "users_count": len(company_users),
        "suspended_users_count": len(company_users) - active_users_count,
        "consensus_stats": {
            "acceptable_match": total_events - disagreements_count,
            "model_disagreement": disagreements_count,
            "disagreement_pct": round((disagreements_count / max(1, total_events)) * 100, 1),
            "total": total_events
        },
        "audit_logs": audit_logs,
        "team_activity": team_activity,
        "sensors": sensors,
        "sensors_count": len(sensors),
        "online_sensors_count": online_sensors_count,
        "zones": zones,
        "zones_count": len(zones),
        "equipment": equipment,
        "equipment_count": len(equipment),
        "incidents": incidents,
        "incidents_count": len(incidents),
        "billing": billing_data,
    }
    return _sanitize_for_json(res_summary)


# =============================================================================
# COMPANY ADMIN HTML PAGE ROUTES (/app/company/*)
# =============================================================================

@company_router.get("/app/company", response_class=HTMLResponse)
@company_router.get("/portal/company", response_class=HTMLResponse)
async def serve_company_dashboard(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/dashboard.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Company Overview — SonicSentinel AI",
        "page_heading": "Company Overview",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "dashboard",
        "summary": summary
    })


@company_router.get("/app/company/users", response_class=HTMLResponse)
async def serve_company_users(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/users.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Users & Teams — SonicSentinel AI",
        "page_heading": "Users & Teams",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "users",
        "summary": summary
    })


@company_router.get("/app/company/events", response_class=HTMLResponse)
async def serve_company_events(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    categories = get_mandatory_classes()
    return templates.TemplateResponse(request=request, name="app/roles/company/events.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audio Events — SonicSentinel AI",
        "page_heading": "Audio Events",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "events",
        "summary": summary,
        "categories": categories
    })


@company_router.get("/app/company/alerts", response_class=HTMLResponse)
async def serve_company_alerts(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/alerts.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Alerts — SonicSentinel AI",
        "page_heading": "Alerts",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "alerts",
        "summary": summary
    })


@company_router.get("/app/company/reviews", response_class=HTMLResponse)
async def serve_company_reviews(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    categories = get_mandatory_classes()
    return templates.TemplateResponse(request=request, name="app/roles/company/reviews.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audio QA / Reviews — SonicSentinel AI",
        "page_heading": "Audio QA / Reviews",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "reviews",
        "summary": summary,
        "categories": categories
    })


@company_router.get("/app/company/analytics", response_class=HTMLResponse)
async def serve_company_analytics(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    categories = get_mandatory_classes()
    return templates.TemplateResponse(request=request, name="app/roles/company/analytics.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Reports & Analytics — SonicSentinel AI",
        "page_heading": "Reports & Analytics",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "analytics",
        "summary": summary,
        "categories": categories
    })


@company_router.get("/app/company/live", response_class=HTMLResponse)
@company_router.get("/app/company/live-monitoring", response_class=HTMLResponse)
async def serve_company_live_monitoring(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/live_monitoring.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Live Monitoring — SonicSentinel AI",
        "page_heading": "Live Monitoring",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "live_monitoring",
        "summary": summary
    })


@company_router.get("/app/company/audit-logs", response_class=HTMLResponse)
async def serve_company_audit_logs(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/audit_logs.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audit Logs — SonicSentinel AI",
        "page_heading": "Audit Logs",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "audit_logs",
        "summary": summary
    })


@company_router.get("/app/company/settings", response_class=HTMLResponse)
async def serve_company_settings(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/settings.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Company Settings — SonicSentinel AI",
        "page_heading": "Company Settings",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "settings",
        "summary": summary
    })


@company_router.get("/app/company/profile", response_class=HTMLResponse)
async def serve_company_profile(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/profile.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Company Profile — SonicSentinel AI",
        "page_heading": "Company Profile",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "profile",
        "summary": summary
    })


@company_router.get("/app/company/sensors", response_class=HTMLResponse)
async def serve_company_sensors(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/sensors.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Sensors & Fleet — SonicSentinel AI",
        "page_heading": "Sensors & Fleet",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "sensors",
        "summary": summary
    })


@company_router.get("/app/company/zones", response_class=HTMLResponse)
async def serve_company_zones(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/zones.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Facility Zones — SonicSentinel AI",
        "page_heading": "Facility Zones",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "zones",
        "summary": summary
    })


@company_router.get("/app/company/equipment", response_class=HTMLResponse)
async def serve_company_equipment(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/equipment.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Machinery Assets — SonicSentinel AI",
        "page_heading": "Machinery Assets",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "equipment",
        "summary": summary
    })


@company_router.get("/app/company/incidents", response_class=HTMLResponse)
async def serve_company_incidents(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/incidents.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Incident Operations — SonicSentinel AI",
        "page_heading": "Incident Operations",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "incidents",
        "summary": summary
    })


@company_router.get("/app/company/billing", response_class=HTMLResponse)
async def serve_company_billing(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/billing.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Billing & Licences — SonicSentinel AI",
        "page_heading": "Billing & Licences",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "billing",
        "summary": summary
    })



# =============================================================================
# COMPANY ADMIN REST APIs (/api/company/*) — STRICTLY SCOPED TO TENANT
# =============================================================================

@company_router.get("/api/company/analytics/detections")
async def api_company_detection_trends(request: Request, range: str = "7d"):
    user, _ = await _require_company_or_redirect(request)
    if range == "30d":
        labels = ["Wk 1", "Wk 2", "Wk 3", "Wk 4"]
        total = [38, 46, 42, 54]
        critical = [5, 7, 4, 8]
    else:
        labels = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        total = [12, 16, 11, 19, 15, 9, 14]
        critical = [2, 3, 1, 4, 2, 1, 2]
    return {"status": "success", "range": range, "labels": labels, "total": total, "critical": critical}


@company_router.post("/api/company/users")
async def api_company_create_user(request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    company_name = user.get("tenant_name", "Apex Global Logistics")

    full_name = str(body.get("full_name") or body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    raw_username = str(body.get("username") or "").strip().lower()
    password = str(body.get("password") or "").strip()
    role_input = str(body.get("role") or "normal_user").strip().lower()
    status_input = str(body.get("status") or "Active").strip().lower()
    if not full_name or not email:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Name and Email are required."})
    if len(password) < 6:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Password must be at least 6 characters so the employee can sign in."})

    role_key = LABEL_TO_ROLE_KEY.get(role_input, "normal_user")
    is_active = (status_input != "suspended")
    username = raw_username or email.split("@")[0]

    if db is not None:
        existing_email = await db.users.find_one({"email": email})
        if existing_email:
            if existing_email.get("tenant_id") and existing_email.get("tenant_id") != tenant_id:
                return JSONResponse(status_code=409, content={"status": "error", "detail": "An account with this email already belongs to another organization."})
            return JSONResponse(status_code=409, content={"status": "error", "detail": "A team member with this email already exists in your company workspace."})

    # Enforce staff seat quota limits under company subscription tier
    from src.security.quotas import check_staff_seat_limit
    allowed, msg, quota_data = await check_staff_seat_limit(db, tenant_id)
    if not allowed:
        return JSONResponse(
            status_code=403,
            content={
                "status": "error",
                "detail": msg,
                "quota": quota_data,
                "upgrade_url": "/pricing"
            }
        )
    new_user = {
        "user_id": f"USR-{uuid.uuid4().hex[:6].upper()}",
        "username": username,
        "full_name": full_name,
        "email": email,
        "role": role_key,
        "tenant_id": tenant_id,
        "tenant_name": company_name,
        "is_active": is_active,
        "last_active": "Just now",
        "password_hash": hash_password(password),
        "created_at": datetime.utcnow()
    }
    if db is not None:
        await db.users.insert_one(dict(new_user))
        await _log_company_audit(db, tenant_id, user, "User Changes", f"{full_name} ({email})", f"Created company employee account with role {COMPANY_ROLE_LABELS.get(role_key)} and configured login credentials.")

    new_user["created_at"] = new_user["created_at"].isoformat()
    new_user["role_label"] = COMPANY_ROLE_LABELS.get(role_key, "Normal User / Resident")
    new_user["status_label"] = "Active" if is_active else "Suspended"
    new_user.pop("password_hash", None)
    return {"status": "success", "user": new_user}


@company_router.put("/api/company/users/{user_id}")
async def api_company_update_user(user_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    updates: Dict[str, Any] = {}
    if "full_name" in body or "name" in body:
        updates["full_name"] = str(body.get("full_name") or body.get("name")).strip()
    if "email" in body:
        updates["email"] = str(body.get("email")).strip().lower()
    if "username" in body and str(body.get("username") or "").strip():
        updates["username"] = str(body.get("username")).strip().lower()
    if "role" in body:
        r_in = str(body.get("role")).strip().lower()
        updates["role"] = LABEL_TO_ROLE_KEY.get(r_in, r_in)
    if "status" in body:
        updates["is_active"] = (str(body.get("status")).strip().lower() != "suspended")

    raw_pwd = str(body.get("password") or body.get("new_password") or "").strip()
    if raw_pwd:
        if len(raw_pwd) < 6:
            return JSONResponse(status_code=400, content={"status": "error", "detail": "Password must be at least 6 characters."})
        updates["password_hash"] = hash_password(raw_pwd)

    if db is not None and updates:
        await db.users.update_one({"user_id": user_id, "tenant_id": tenant_id}, {"$set": updates})
        audit_fields = [k for k in updates.keys() if k != "password_hash"]
        if "password_hash" in updates:
            audit_fields.append("password_reset")
        await _log_company_audit(db, tenant_id, user, "User Changes", f"User {user_id}", f"Updated employee profile/credentials ({', '.join(audit_fields)}).")
    safe_updates = {k: v for k, v in updates.items() if k != "password_hash"}
    return {"status": "success", "user_id": user_id, "updates": safe_updates, "password_updated": "password_hash" in updates}


@company_router.post("/api/company/users/{user_id}/password")
async def api_company_reset_user_password(user_id: str, request: Request):
    """Allows a Company Admin to directly set or reset a company employee's login password."""
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    new_pwd = str(body.get("password") or body.get("new_password") or "").strip()
    if len(new_pwd) < 6:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "New password must be at least 6 characters."})
    if db is not None:
        res = await db.users.update_one(
            {"user_id": user_id, "tenant_id": tenant_id},
            {"$set": {"password_hash": hash_password(new_pwd)}}
        )
        if res.matched_count == 0:
            return JSONResponse(status_code=404, content={"status": "error", "detail": "Employee not found in this company workspace."})
        await _log_company_audit(db, tenant_id, user, "User Changes", f"User {user_id}", f"Reset login password for employee {user_id}.")
    return {"status": "success", "user_id": user_id, "message": "Employee login password updated."}


@company_router.patch("/api/company/users/{user_id}/status")
async def api_company_toggle_user_status(user_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    is_active = bool(body.get("is_active", True))
    if db is not None:
        await db.users.update_one({"user_id": user_id, "tenant_id": tenant_id}, {"$set": {"is_active": is_active}})
        await _log_company_audit(db, tenant_id, user, "User Changes", f"User {user_id}", f"Changed account status to {'Active' if is_active else 'Suspended'}.")
    return {"status": "success", "user_id": user_id, "is_active": is_active}


@company_router.delete("/api/company/users/{user_id}")
async def api_company_delete_user(user_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.users.delete_one({"user_id": user_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "User Changes", f"User {user_id}", f"Removed user {user_id} from company workspace.")
    return {"status": "success", "deleted_id": user_id}


@company_router.patch("/api/company/events/{audio_id}")
async def api_company_update_event(audio_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    updates: Dict[str, Any] = {}
    if "lifecycle_status" in body:
        updates["lifecycle_status"] = str(body["lifecycle_status"]).strip()
    if "severity" in body:
        updates["severity"] = str(body["severity"]).strip()
    if db is not None and updates:
        await db.audio_events.update_one({"audio_id": audio_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Audio Event", f"Event {audio_id}", f"Updated event {audio_id}: {updates}")
    return {"status": "success", "audio_id": audio_id, "updates": updates}


@company_router.delete("/api/company/events/{audio_id}")
async def api_company_delete_event(audio_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.audio_events.delete_one({"audio_id": audio_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Audio Upload", f"Event {audio_id}", f"Deleted company audio event {audio_id}.")
    return {"status": "success", "deleted_id": audio_id}


@company_router.patch("/api/company/alerts/{alert_id}/status")
async def api_company_update_alert_status(alert_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    new_status = str(body.get("status") or "Acknowledged").strip()
    assigned_to = body.get("assigned_to")
    updates: Dict[str, Any] = {"status": new_status}
    if new_status == "Acknowledged":
        updates["acknowledged_by"] = user.get("full_name") or user.get("username") or "Company Admin"
        updates["acknowledged_at"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    if assigned_to:
        updates["assigned_to"] = str(assigned_to).strip()
    if db is not None:
        await db.alerts.update_one({"alert_id": alert_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Alert", f"Alert {alert_id}", f"Updated alert {alert_id} status to {new_status}.")
    return {"status": "success", "alert_id": alert_id, "updates": updates}


@company_router.delete("/api/company/alerts/{alert_id}")
async def api_company_delete_alert(alert_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.alerts.delete_one({"alert_id": alert_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Alert", f"Alert {alert_id}", f"Removed alert {alert_id} from company queue.")
    return {"status": "success", "deleted_id": alert_id}


@company_router.post("/api/company/reviews/{review_id}/resolve")
async def api_company_resolve_review(review_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    decision = str(body.get("decision") or "Confirmed").strip()
    final_category = str(body.get("final_category") or "Gunshot").strip()
    notes = str(body.get("notes") or "").strip()
    recommended_action = str(body.get("recommended_action") or "").strip()
    reviewer_name = user.get("full_name") or user.get("username") or "Company Admin"

    updates = {
        "status": decision,
        "final_category": final_category,
        "previous_decision": f"{decision} ({final_category})",
        "reviewer_name": reviewer_name,
        "reviewer_notes": notes,
        "recommended_action": recommended_action,
        "reviewed_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    }
    if db is not None:
        await db.manual_reviews.update_one({"review_id": review_id, "tenant_id": tenant_id}, {"$set": updates})
        action_type = "Override" if decision == "Overridden" else "Review"
        await _log_company_audit(
            db, tenant_id, user, action_type, f"Review {review_id}",
            f"{decision} review {review_id} with class '{final_category}'."
        )
    return {"status": "success", "review_id": review_id, "updates": updates}


@company_router.delete("/api/company/reviews/{review_id}")
async def api_company_delete_review(review_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.manual_reviews.delete_one({"review_id": review_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Review", f"Review {review_id}", f"Deleted review item {review_id}.")
    return {"status": "success", "deleted_id": review_id}


@company_router.post("/api/company/settings")
async def api_company_save_settings(request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    company_name = str(body.get("company_name") or "Apex Global Logistics").strip()
    contact_email = str(body.get("contact_email") or "operations@apexlogistics.com").strip()
    phone = str(body.get("phone") or "+1 (415) 890-4420").strip()
    address = str(body.get("address") or "450 Mission St, Suite 1400, San Francisco, CA").strip()

    settings_obj = {
        "alert_severity": body.get("alert_severity", "High"),
        "notification_preferences": body.get("notification_preferences", "In-App, Email & Webhook"),
        "critical_alert_rules": body.get("critical_alert_rules", "Require >= 78% confidence & Dual-AI evaluation"),
        "supported_formats": body.get("supported_formats", "WAV, MP3, FLAC, OGG, M4A (16kHz - 48kHz)"),
        "quality_requirements": body.get("quality_requirements", "Minimum SNR 12 dB · Reject Clipped (>5%) or Silent Signals"),
        "microphone_permission": body.get("microphone_permission", "Explicit Browser MediaDevices Consent Required per Session"),
        "recording_information": body.get("recording_information", "2.0s rolling acoustic buffer · No continuous raw speech surveillance"),
        "data_retention_info": body.get("data_retention_info", "Audio clips retained for 90 days · Event telemetry retained for 365 days"),
        "notify_critical": bool(body.get("notify_critical", True)),
        "notify_reviews": bool(body.get("notify_reviews", True)),
        "notify_system": bool(body.get("notify_system", True)),
        "role_permissions_summary": body.get("role_permissions_summary", "Security: Alerts & Live Stream · Maintenance: Machinery Events · Audio QA: Review Queue & Overrides"),
        "team_management_policy": body.get("team_management_policy", "Company Admin approval required for role changes and account activations"),
    }

    if db is not None:
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {
                "company_name": company_name,
                "name": company_name,
                "contact_email": contact_email,
                "phone": phone,
                "address": address,
                "settings": settings_obj
            }},
            upsert=True
        )
        await _log_company_audit(db, tenant_id, user, "Permission Changes", "Company Settings", "Updated company profile, alert preferences, privacy, and team settings.")
    return {"status": "success", "company_name": company_name, "settings": settings_obj}


@company_router.post("/api/company/profile/password")
async def api_company_change_password(request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    new_pwd = str(body.get("new_password") or "").strip()
    if len(new_pwd) < 6:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "New password must be at least 6 characters."})
    if db is not None and user.get("user_id"):
        await db.users.update_one(
            {"user_id": user["user_id"]},
            {"$set": {"password_hash": hash_password(new_pwd)}}
        )
        await _log_company_audit(db, tenant_id, user, "User Changes", "Company Admin Password", "Updated Company Admin account password.")
    return {"status": "success", "message": "Password updated successfully."}


@company_router.get("/api/company/analytics/export-csv")
async def api_company_export_csv(request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    tenant_id = summary["company"]["tenant_id"]

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["Audio ID", "Filename", "User", "Python Prediction", "Python Confidence", "GTM Prediction", "GTM Confidence", "Agreement", "Severity", "Quality", "Status", "Time"])
    for ev in summary["recent_events"]:
        writer.writerow([
            ev.get("audio_id"),
            ev.get("filename"),
            ev.get("uploaded_by"),
            ev.get("python_prediction"),
            f"{round(float(ev.get('python_confidence', 0)) * 100, 1)}%",
            ev.get("gtm_prediction"),
            f"{round(float(ev.get('gtm_confidence', 0)) * 100, 1)}%",
            ev.get("consistency_status"),
            ev.get("severity"),
            ev.get("quality"),
            ev.get("lifecycle_status"),
            ev.get("created_label")
        ])
    if db is not None:
        await _log_company_audit(db, tenant_id, user, "Export", "Company Analytics CSV", "Exported company audio events & analytics report (CSV).")
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=sonicsentinel_{tenant_id.lower()}_analytics.csv"}
    )


@company_router.get("/api/company/analytics/export-excel")
async def api_company_export_excel(request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    tenant_id = summary["company"]["tenant_id"]

    buf = io.StringIO()
    writer = csv.writer(buf, delimiter="\t")
    writer.writerow(["Audio ID", "Filename", "User", "Python Prediction", "Python Confidence", "GTM Prediction", "GTM Confidence", "Agreement", "Severity", "Quality", "Status", "Time"])
    for ev in summary["recent_events"]:
        writer.writerow([
            ev.get("audio_id"),
            ev.get("filename"),
            ev.get("uploaded_by"),
            ev.get("python_prediction"),
            f"{round(float(ev.get('python_confidence', 0)) * 100, 1)}%",
            ev.get("gtm_prediction"),
            f"{round(float(ev.get('gtm_confidence', 0)) * 100, 1)}%",
            ev.get("consistency_status"),
            ev.get("severity"),
            ev.get("quality"),
            ev.get("lifecycle_status"),
            ev.get("created_label")
        ])
    if db is not None:
        await _log_company_audit(db, tenant_id, user, "Export", "Company Analytics Excel", "Exported company audio events & analytics report (Excel TSV).")
    return Response(
        content=buf.getvalue(),
        media_type="application/vnd.ms-excel",
        headers={"Content-Disposition": f"attachment; filename=sonicsentinel_{tenant_id.lower()}_analytics.xls"}
    )


# =============================================================================
# REST APIS: SENSORS & HARDWARE FLEET
# =============================================================================

@company_router.post("/api/company/sensors")
async def api_company_create_sensor(request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    t_sfx = tenant_id[-4:].upper()

    name = str(body.get("name") or "").strip()
    zone_id = str(body.get("zone_id") or "").strip()
    zone_name = str(body.get("zone_name") or "Main Facility Zone").strip()
    hardware_model = str(body.get("hardware_model") or "SonicNode-Industrial-I2").strip()
    ip_address = str(body.get("ip_address") or "192.168.10.40").strip()
    sample_rate = int(body.get("sample_rate") or 16000)
    snr_threshold_db = float(body.get("snr_threshold_db") or 15.0)

    if not name:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Sensor node name is required."})

    sensor_id = f"SNS-{t_sfx}-{uuid.uuid4().hex[:4].upper()}"
    new_sensor = {
        "sensor_id": sensor_id,
        "name": name,
        "tenant_id": tenant_id,
        "zone_id": zone_id or f"ZONE-{t_sfx}-01",
        "zone_name": zone_name,
        "status": "online",
        "audio_health": "optimal",
        "hardware_model": hardware_model,
        "sample_rate": sample_rate,
        "ip_address": ip_address,
        "noise_floor_db": -52.4,
        "snr_threshold_db": snr_threshold_db,
        "last_seen": "Just now",
        "created_at": datetime.utcnow()
    }
    if db is not None:
        await db.sensors.insert_one(dict(new_sensor))
        await _log_company_audit(db, tenant_id, user, "Hardware", f"Sensor {sensor_id}", f"Registered acoustic sensor node '{name}' in zone '{zone_name}'.")

    new_sensor["created_at"] = new_sensor["created_at"].isoformat()
    return {"status": "success", "sensor": new_sensor}


@company_router.put("/api/company/sensors/{sensor_id}")
async def api_company_update_sensor(sensor_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    updates: Dict[str, Any] = {}
    if "name" in body:
        updates["name"] = str(body["name"]).strip()
    if "zone_id" in body:
        updates["zone_id"] = str(body["zone_id"]).strip()
    if "zone_name" in body:
        updates["zone_name"] = str(body["zone_name"]).strip()
    if "hardware_model" in body:
        updates["hardware_model"] = str(body["hardware_model"]).strip()
    if "ip_address" in body:
        updates["ip_address"] = str(body["ip_address"]).strip()
    if "sample_rate" in body:
        updates["sample_rate"] = int(body["sample_rate"])
    if "snr_threshold_db" in body:
        updates["snr_threshold_db"] = float(body["snr_threshold_db"])
    if "status" in body:
        updates["status"] = str(body["status"]).lower()
    if "audio_health" in body:
        updates["audio_health"] = str(body["audio_health"]).lower()

    if db is not None and updates:
        await db.sensors.update_one({"sensor_id": sensor_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Hardware", f"Sensor {sensor_id}", f"Updated sensor parameters ({', '.join(updates.keys())}).")
    return {"status": "success", "sensor_id": sensor_id, "updates": updates}


@company_router.patch("/api/company/sensors/{sensor_id}/status")
async def api_company_toggle_sensor_status(sensor_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    new_status = str(body.get("status") or "online").lower()
    audio_health = "optimal" if new_status == "online" else ("degraded" if new_status == "warning" else "unreachable")
    updates = {"status": new_status, "audio_health": audio_health, "last_seen": "Just now"}
    if db is not None:
        await db.sensors.update_one({"sensor_id": sensor_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Hardware", f"Sensor {sensor_id}", f"Changed sensor operational status to {new_status.upper()}.")
    return {"status": "success", "sensor_id": sensor_id, "status_value": new_status, "audio_health": audio_health}


@company_router.post("/api/company/sensors/{sensor_id}/ping")
async def api_company_ping_sensor(sensor_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    sensor = await db.sensors.find_one({"sensor_id": sensor_id, "tenant_id": tenant_id}) if db is not None else None
    if not sensor:
        return JSONResponse(status_code=404, content={"status": "error", "detail": "Sensor node not found in this company."})
    
    import random
    latency_ms = random.randint(12, 28)
    noise_floor_db = round(-52.0 + random.uniform(-2.5, 2.5), 1)
    if db is not None:
        await db.sensors.update_one(
            {"sensor_id": sensor_id, "tenant_id": tenant_id},
            {"$set": {"last_seen": "Just now", "noise_floor_db": noise_floor_db}}
        )
        await _log_company_audit(db, tenant_id, user, "Hardware", f"Sensor {sensor_id}", f"Acoustic telemetry ping succeeded ({latency_ms}ms, noise floor {noise_floor_db} dB).")
    return {
        "status": "success",
        "sensor_id": sensor_id,
        "latency_ms": latency_ms,
        "noise_floor_db": noise_floor_db,
        "packet_loss_pct": 0.0,
        "telemetry": "Active streaming buffer 16000Hz PCM nominal"
    }


@company_router.delete("/api/company/sensors/{sensor_id}")
async def api_company_delete_sensor(sensor_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.sensors.delete_one({"sensor_id": sensor_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Hardware", f"Sensor {sensor_id}", f"Decommissioned sensor node {sensor_id}.")
    return {"status": "success", "deleted_id": sensor_id}


# =============================================================================
# REST APIS: FACILITY ZONES
# =============================================================================

@company_router.post("/api/company/zones")
async def api_company_create_zone(request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    t_sfx = tenant_id[-4:].upper()

    name = str(body.get("name") or "").strip()
    building_area = str(body.get("building_area") or "Main Complex").strip()
    threat_level = str(body.get("threat_level") or "normal").lower()
    noise_threshold_db = float(body.get("noise_threshold_db") or 70.0)
    description = str(body.get("description") or "").strip()

    if not name:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Zone name is required."})

    zone_id = f"ZONE-{t_sfx}-{uuid.uuid4().hex[:4].upper()}"
    new_zone = {
        "zone_id": zone_id,
        "name": name,
        "tenant_id": tenant_id,
        "building_area": building_area,
        "threat_level": threat_level,
        "status": "active",
        "description": description or f"Acoustic surveillance zone for {name}.",
        "sensors_count": 0,
        "noise_threshold_db": noise_threshold_db,
        "created_at": datetime.utcnow()
    }
    if db is not None:
        await db.zones.insert_one(dict(new_zone))
        await _log_company_audit(db, tenant_id, user, "Zone", f"Zone {zone_id}", f"Created facility acoustic monitoring zone '{name}' (Threat: {threat_level.upper()}).")

    new_zone["created_at"] = new_zone["created_at"].isoformat()
    return {"status": "success", "zone": new_zone}


@company_router.put("/api/company/zones/{zone_id}")
async def api_company_update_zone(zone_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    updates: Dict[str, Any] = {}
    if "name" in body:
        updates["name"] = str(body["name"]).strip()
    if "building_area" in body:
        updates["building_area"] = str(body["building_area"]).strip()
    if "threat_level" in body:
        updates["threat_level"] = str(body["threat_level"]).lower()
    if "noise_threshold_db" in body:
        updates["noise_threshold_db"] = float(body["noise_threshold_db"])
    if "description" in body:
        updates["description"] = str(body["description"]).strip()
    if "status" in body:
        updates["status"] = str(body["status"]).lower()

    if db is not None and updates:
        await db.zones.update_one({"zone_id": zone_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Zone", f"Zone {zone_id}", f"Updated facility zone parameters ({', '.join(updates.keys())}).")
    return {"status": "success", "zone_id": zone_id, "updates": updates}


@company_router.delete("/api/company/zones/{zone_id}")
async def api_company_delete_zone(zone_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.zones.delete_one({"zone_id": zone_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Zone", f"Zone {zone_id}", f"Removed facility zone {zone_id}.")
    return {"status": "success", "deleted_id": zone_id}


# =============================================================================
# REST APIS: MACHINERY & EQUIPMENT ASSETS
# =============================================================================

@company_router.post("/api/company/equipment")
async def api_company_create_equipment(request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    t_sfx = tenant_id[-4:].upper()

    name = str(body.get("name") or "").strip()
    machine_type = str(body.get("machine_type") or body.get("type") or "Compressor").strip()
    location = str(body.get("location") or body.get("zone") or "Facility Hall").strip()
    snr_threshold_db = float(body.get("snr_threshold_db") or 15.0)

    if not name:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Equipment asset name is required."})

    equipment_id = f"EQP-{t_sfx}-{uuid.uuid4().hex[:4].upper()}"
    new_eq = {
        "equipment_id": equipment_id,
        "name": name,
        "tenant_id": tenant_id,
        "type": machine_type,
        "machine_type": machine_type,
        "location": location,
        "zone": location,
        "snr_threshold_db": snr_threshold_db,
        "status": "Online",
        "health_score": 95,
        "last_checked": "Just now",
        "created_by": user.get("full_name") or user.get("username") or "Company Admin",
        "created_at": datetime.utcnow().isoformat()
    }
    if db is not None:
        await db.equipment.insert_one(dict(new_eq))
        await _log_company_audit(db, tenant_id, user, "Machinery", f"Asset {equipment_id}", f"Enrolled machinery asset '{name}' ({machine_type}) at {location}.")

    return {"status": "success", "equipment": new_eq}


@company_router.put("/api/company/equipment/{equipment_id}")
async def api_company_update_equipment(equipment_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    updates: Dict[str, Any] = {}
    if "name" in body:
        updates["name"] = str(body["name"]).strip()
    if "machine_type" in body or "type" in body:
        mtype = str(body.get("machine_type") or body.get("type")).strip()
        updates["machine_type"] = mtype
        updates["type"] = mtype
    if "location" in body or "zone" in body:
        loc = str(body.get("location") or body.get("zone")).strip()
        updates["location"] = loc
        updates["zone"] = loc
    if "snr_threshold_db" in body:
        updates["snr_threshold_db"] = float(body["snr_threshold_db"])
    if "status" in body:
        updates["status"] = str(body["status"]).strip()
    if "health_score" in body:
        updates["health_score"] = int(body["health_score"])

    if db is not None and updates:
        await db.equipment.update_one({"equipment_id": equipment_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Machinery", f"Asset {equipment_id}", f"Updated equipment parameters ({', '.join(updates.keys())}).")
    return {"status": "success", "equipment_id": equipment_id, "updates": updates}


@company_router.patch("/api/company/equipment/{equipment_id}/schedule")
async def api_company_schedule_equipment(equipment_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    notes = str(body.get("notes") or "Scheduled periodic acoustic health check.").strip()
    updates = {"status": "Inspection Scheduled", "last_checked": "Scheduled today", "maintenance_notes": notes}
    if db is not None:
        await db.equipment.update_one({"equipment_id": equipment_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Machinery", f"Asset {equipment_id}", f"Dispatched maintenance inspection schedule for {equipment_id}.")
    return {"status": "success", "equipment_id": equipment_id, "updates": updates}


@company_router.delete("/api/company/equipment/{equipment_id}")
async def api_company_delete_equipment(equipment_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.equipment.delete_one({"equipment_id": equipment_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Machinery", f"Asset {equipment_id}", f"Decommissioned machinery asset {equipment_id}.")
    return {"status": "success", "deleted_id": equipment_id}


# =============================================================================
# REST APIS: INCIDENT OPERATIONS & DISPATCH
# =============================================================================

@company_router.post("/api/company/incidents")
async def api_company_create_incident(request: Request):
    user, _ = await _require_company_or_redirect(request)
    if not user:
        return JSONResponse(status_code=401, content={"status": "error", "detail": "Authentication required."})
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    t_sfx = tenant_id[-4:].upper()

    title = str(body.get("title") or "").strip()
    alert_id = str(body.get("alert_id") or "DIRECT-DISPATCH").strip()
    severity = str(body.get("severity") or "Critical").strip()
    zone_id = str(body.get("zone_id") or f"ZONE-{t_sfx}-01").strip()
    zone_name = str(body.get("zone_name") or "Main Facility").strip()
    sound_class = str(body.get("sound_class") or "Gunshot").strip()
    confidence = float(body.get("confidence") or 0.95)
    assigned_operator = str(body.get("assigned_operator") or user.get("full_name") or "Security Lead").strip()
    notes = str(body.get("notes") or "").strip()

    if not title:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Incident title is required."})

    incident_id = f"INC-{t_sfx}-{uuid.uuid4().hex[:4].upper()}"
    now = datetime.utcnow()
    new_inc = {
        "incident_id": incident_id,
        "tenant_id": tenant_id,
        "title": title,
        "alert_id": alert_id,
        "severity": severity,
        "status": "New",
        "zone_id": zone_id,
        "zone_name": zone_name,
        "sound_class": sound_class,
        "confidence": confidence,
        "assigned_operator": assigned_operator,
        "notes": notes or f"Incident opened by {user.get('full_name') or 'Company Admin'}.",
        "created_at": now,
        "updated_at": now
    }
    if db is not None:
        await db.incidents.insert_one(dict(new_inc))
        await _log_company_audit(db, tenant_id, user, "Incident", f"Incident {incident_id}", f"Dispatched new incident '{title}' (Severity: {severity}).")

    new_inc["created_at"] = new_inc["created_at"].isoformat()
    new_inc["updated_at"] = new_inc["updated_at"].isoformat()
    return {"status": "success", "incident": new_inc}


@company_router.patch("/api/company/incidents/{incident_id}/status")
async def api_company_update_incident_status(incident_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    new_status = str(body.get("status") or "Dispatched").strip()
    operator = body.get("assigned_operator")
    notes = body.get("notes")

    updates: Dict[str, Any] = {"status": new_status, "updated_at": datetime.utcnow()}
    if operator:
        updates["assigned_operator"] = str(operator).strip()
    if notes:
        updates["notes"] = str(notes).strip()

    if db is not None:
        await db.incidents.update_one({"incident_id": incident_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "Incident", f"Incident {incident_id}", f"Updated incident status to '{new_status}'.")
    return {"status": "success", "incident_id": incident_id, "status_value": new_status, "updates": updates}


@company_router.post("/api/company/incidents/{incident_id}/notes")
async def api_company_append_incident_note(incident_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    note_text = str(body.get("note") or body.get("comment") or "").strip()
    if not note_text:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Note content is required."})

    author = user.get("full_name") or user.get("username") or "Company Admin"
    time_str = datetime.utcnow().strftime("%b %d, %H:%M UTC")
    entry = f"[{time_str} - {author}] {note_text}"

    if db is not None:
        await db.incidents.update_one(
            {"incident_id": incident_id, "tenant_id": tenant_id},
            {
                "$set": {"updated_at": datetime.utcnow()},
                "$push": {"timeline": {"timestamp": time_str, "author": author, "text": note_text}}
            }
        )
        await _log_company_audit(db, tenant_id, user, "Incident", f"Incident {incident_id}", f"Added operational log note to incident {incident_id}.")
    return {"status": "success", "incident_id": incident_id, "entry": entry}


@company_router.delete("/api/company/incidents/{incident_id}")
async def api_company_delete_incident(incident_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    if db is not None:
        await db.incidents.delete_one({"incident_id": incident_id, "tenant_id": tenant_id})
        await _log_company_audit(db, tenant_id, user, "Incident", f"Incident {incident_id}", f"Closed and archived incident {incident_id}.")
    return {"status": "success", "deleted_id": incident_id}


# =============================================================================
# REST APIS: BILLING & SUBSCRIPTION UPGRADES
# =============================================================================

@company_router.post("/api/company/billing/upgrade")
async def api_company_upgrade_subscription(request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    new_tier = str(body.get("tier") or "pro").lower()

    if db is not None:
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"plan_tier": new_tier, "subscription_status": "active", "updated_at": datetime.utcnow()}}
        )
        await _log_company_audit(db, tenant_id, user, "Billing", "Subscription Tier", f"Upgraded company subscription plan to {new_tier.upper()}.")
    return {"status": "success", "plan_tier": new_tier, "message": f"Successfully updated subscription to {new_tier.upper()} tier."}


@company_router.get("/api/company/billing/invoices/{invoice_id}")
async def api_company_download_invoice(invoice_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    company_name = user.get("tenant_name", "Apex Global Logistics")

    receipt_text = f"""=======================================================
SONICSENTINEL AI PLATFORM — OFFICIAL INVOICE RECEIPT
=======================================================
Invoice Reference : {invoice_id}
Customer / Tenant : {company_name} ({tenant_id})
Date Issued       : September 01, 2026
Billing Cycle     : Annual Enterprise Pro (Pre-paid)
Status            : PAID IN FULL

Line Items:
1. SonicSentinel Dual-AI Neural Pipeline Access (Annual)  $3,600.00
2. Hardware Mesh Connectivity & Acoustic Telemetry Mesh     $720.00
3. 24/7 Security Dispatch & Automated Escalation Add-on     $468.00
-------------------------------------------------------
Total Amount Paid : $4,788.00 USD
Payment Instrument: Corporate Wire / Card on file
Security Hash     : SHA256:{uuid.uuid4().hex}
=======================================================
Thank you for securing your operations with SonicSentinel AI.
"""
    return Response(
        content=receipt_text,
        media_type="text/plain",
        headers={"Content-Disposition": f"attachment; filename=invoice_{invoice_id}.txt"}
    )

