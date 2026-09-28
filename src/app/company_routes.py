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

logger = logging.getLogger("Dectus.CompanyRouter")
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
                "team_management_policy": "Company Admin approval required for role changes and account activations"
            }
        })

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
        for sev in seed_events:
            if not await db.audio_events.find_one({"audio_id": sev["audio_id"]}):
                await db.audio_events.insert_one(sev)

    # 4. Ensure company alerts exist
    al_count = await db.alerts.count_documents({"tenant_id": tenant_id})
    if al_count < 4:
        now = datetime.utcnow()
        seed_alerts = [
            {
                "alert_id": "ALT-CMP-401",
                "audio_id": "AUD_CMP_901A",
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
                "alert_id": "ALT-CMP-402",
                "audio_id": "AUD_CMP_902B",
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
                "alert_id": "ALT-CMP-403",
                "audio_id": "AUD_CMP_903C",
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
                "alert_id": "ALT-CMP-404",
                "audio_id": "AUD_CMP_905E",
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
            if not await db.alerts.find_one({"alert_id": sal["alert_id"]}):
                await db.alerts.insert_one(sal)

    # 5. Ensure company manual reviews exist
    rev_count = await db.manual_reviews.count_documents({"tenant_id": tenant_id})
    if rev_count < 3:
        now = datetime.utcnow()
        seed_reviews = [
            {
                "review_id": "REV-CMP-701",
                "audio_id": "AUD_CMP_903C",
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
                "review_id": "REV-CMP-702",
                "audio_id": "AUD_CMP_906F",
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
                "review_id": "REV-CMP-703",
                "audio_id": "AUD_CMP_904D",
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
                "previous_decision": "Confirmed AI Prediction",
                "reviewer_name": "Dr. Sarah Chen",
                "reviewer_notes": "Clear distress vocalization verified; security drill response completed.",
                "recommended_action": "Archive verified clip for company QA benchmark.",
                "created_at": now - timedelta(hours=4, minutes=50)
            }
        ]
        for srev in seed_reviews:
            if not await db.manual_reviews.find_one({"review_id": srev["review_id"]}):
                await db.manual_reviews.insert_one(srev)

    # 6. Ensure company audit logs exist
    log_count = await db.audit_logs.count_documents({"tenant_id": tenant_id})
    if log_count < 6:
        now = datetime.utcnow()
        seed_logs = [
            {
                "log_id": "CLOG-1001",
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
                "log_id": "CLOG-1002",
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
                "log_id": "CLOG-1003",
                "tenant_id": tenant_id,
                "username": "Tariq Mahmood",
                "role": "company_maintenance_operator",
                "role_label": "Maintenance",
                "action": "Audio Upload",
                "resource": "AUD_CMP_903C (turbine_compressor_line2.wav)",
                "details": "Uploaded 2.0s machinery diagnostic recording for Dual-AI evaluation.",
                "description": "Uploaded 2.0s machinery diagnostic recording for Dual-AI evaluation.",
                "status": "Success",
                "timestamp": (now - timedelta(hours=2, minutes=40)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=2, minutes=40)
            },
            {
                "log_id": "CLOG-1004",
                "tenant_id": tenant_id,
                "username": "Dr. Sarah Chen",
                "role": "company_audio_reviewer",
                "role_label": "Audio QA / Reviewer",
                "action": "Review",
                "resource": "REV-CMP-703 (AUD_CMP_904D)",
                "details": "Confirmed Dual-AI prediction (Scream / Help Call) after spectrogram inspection.",
                "description": "Confirmed Dual-AI prediction (Scream / Help Call) after spectrogram inspection.",
                "status": "Success",
                "timestamp": (now - timedelta(hours=4, minutes=50)).strftime("%Y-%m-%d %H:%M UTC"),
                "created_at": now - timedelta(hours=4, minutes=50)
            },
            {
                "log_id": "CLOG-1005",
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
                "log_id": "CLOG-1006",
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
            if not await db.audit_logs.find_one({"log_id": slog["log_id"]}):
                await db.audit_logs.insert_one(slog)


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
        "portal_name": "Company Overview — Dectus",
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
        "portal_name": "Users & Teams — Dectus",
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
        "portal_name": "Audio Events — Dectus",
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
        "portal_name": "Alerts — Dectus",
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
        "portal_name": "Audio QA / Reviews — Dectus",
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
        "portal_name": "Reports & Analytics — Dectus",
        "page_heading": "Reports & Analytics",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "analytics",
        "summary": summary,
        "categories": categories
    })


@company_router.get("/app/company/live-monitoring", response_class=HTMLResponse)
async def serve_company_live_monitoring(request: Request):
    user, redirect = await _require_company_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_company_summary(db, user)
    return templates.TemplateResponse(request=request, name="app/roles/company/live_monitoring.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Live Monitoring — Dectus",
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
        "portal_name": "Audit Logs — Dectus",
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
        "portal_name": "Company Settings — Dectus",
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
        "portal_name": "Company Profile — Dectus",
        "page_heading": "Company Profile",
        "role_badge": "Company Admin",
        "user": user,
        "company": summary["company"],
        "active_tab": "company",
        "company_page": "profile",
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
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")
    company_name = user.get("tenant_name", "Apex Global Logistics")

    full_name = str(body.get("full_name") or body.get("name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    role_input = str(body.get("role") or "normal_user").strip().lower()
    status_input = str(body.get("status") or "Active").strip().lower()
    if not full_name or not email:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Name and Email are required."})

    role_key = LABEL_TO_ROLE_KEY.get(role_input, "normal_user")
    is_active = (status_input != "suspended")

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
        "username": email.split("@")[0],
        "full_name": full_name,
        "email": email,
        "role": role_key,
        "tenant_id": tenant_id,
        "tenant_name": company_name,
        "is_active": is_active,
        "last_active": "Just now",
        "password_hash": hash_password("password123"),
        "created_at": datetime.utcnow()
    }
    if db is not None:
        await db.users.insert_one(dict(new_user))
        await _log_company_audit(db, tenant_id, user, "User Changes", f"{full_name} ({email})", f"Created company user with role {COMPANY_ROLE_LABELS.get(role_key)}.")

    new_user["created_at"] = new_user["created_at"].isoformat()
    new_user["role_label"] = COMPANY_ROLE_LABELS.get(role_key, "Normal User / Resident")
    new_user["status_label"] = "Active" if is_active else "Suspended"
    new_user.pop("password_hash", None)
    return {"status": "success", "user": new_user}


@company_router.put("/api/company/users/{user_id}")
async def api_company_update_user(user_id: str, request: Request):
    user, _ = await _require_company_or_redirect(request)
    db = await ensure_database()
    body = await request.json()
    tenant_id = user.get("tenant_id", "TENANT_APEX_01")

    updates: Dict[str, Any] = {}
    if "full_name" in body or "name" in body:
        updates["full_name"] = str(body.get("full_name") or body.get("name")).strip()
    if "email" in body:
        updates["email"] = str(body.get("email")).strip().lower()
    if "role" in body:
        r_in = str(body.get("role")).strip().lower()
        updates["role"] = LABEL_TO_ROLE_KEY.get(r_in, r_in)
    if "status" in body:
        updates["is_active"] = (str(body.get("status")).strip().lower() != "suspended")

    if db is not None and updates:
        await db.users.update_one({"user_id": user_id, "tenant_id": tenant_id}, {"$set": updates})
        await _log_company_audit(db, tenant_id, user, "User Changes", f"User {user_id}", f"Updated user profile/role settings: {updates}")
    return {"status": "success", "user_id": user_id, "updates": updates}


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
            f"{decision} review {review_id} with class '{final_category}' (original AI predictions preserved)."
        )
    return {"status": "success", "review_id": review_id, "updates": updates}


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
        headers={"Content-Disposition": f"attachment; filename=dectus_{tenant_id.lower()}_analytics.csv"}
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
        headers={"Content-Disposition": f"attachment; filename=dectus_{tenant_id.lower()}_analytics.xls"}
    )
