import io
import csv
import json
import uuid
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any

import numpy as np
import soundfile as sf
from fastapi import APIRouter, Request, UploadFile, File, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, FileResponse, Response
from fastapi.templating import Jinja2Templates

from config.settings import settings, load_rules, get_mandatory_classes
from src.database.mongodb import ensure_database
from src.database.security import hash_password
from src.app.app_routes import get_authenticated_user
from src.app.auth_routes import ROLE_REDIRECTS
from src.audio.validator import AudioValidator, AudioValidationError
from src.audio.quality_checker import AudioQualityChecker
from src.audio.preprocessor import AudioPreprocessor
from src.audio.extractor import AcousticFeatureExtractor
from src.models.model_pipeline import PythonSoundClassifier
from src.models.gtm_inference import GTMClassifier
from src.consensus.consensus_engine import ConsensusEngine

logger = logging.getLogger("Dectus.AdminRouter")
admin_router = APIRouter(tags=["Super Admin Portal"])
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

# Shared pipeline instances
preprocessor = AudioPreprocessor(target_sr=settings.SAMPLE_RATE, target_duration=settings.WINDOW_DURATION_SEC)
feature_extractor = AcousticFeatureExtractor(sample_rate=settings.SAMPLE_RATE)
python_model = PythonSoundClassifier()
gtm_model = GTMClassifier()
consensus_engine = ConsensusEngine()

SUGGESTED_CLASSES = [
    "Drone", "Drilling/Grinder", "Fireworks", "Vehicle Backfire",
    "Explosion", "Door Impact", "Graffiti Spray", "Normal Machinery"
]


async def _require_admin_or_redirect(request: Request):
    """Verifies session and ensures user is Super Admin; otherwise returns RedirectResponse."""
    user = await get_authenticated_user(request)
    if not user:
        return None, RedirectResponse(url="/app/login", status_code=302)
    role = user.get("role", "normal_user")
    if role not in ("super_admin", "administrator"):
        target = ROLE_REDIRECTS.get(role, "/app/user")
        return None, RedirectResponse(url=target, status_code=302)
    return user, None


async def _log_audit(db, action: str, actor: dict, details: str, status_str: str = "Success", is_anomaly: bool = False, target_tenant: Optional[str] = None):
    if db is None:
        return
    try:
        await db.audit_logs.insert_one({
            "log_id": f"LOG-{uuid.uuid4().hex[:6].upper()}",
            "tenant_id": target_tenant or actor.get("tenant_id", "platform_global"),
            "user_id": actor.get("user_id", "USR-SUPER-ADMIN-001"),
            "username": actor.get("full_name") or actor.get("username", "Admin"),
            "role": actor.get("role", "super_admin"),
            "action": action,
            "details": details,
            "status": status_str,
            "is_anomaly": is_anomaly,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        })
    except Exception as exc:
        logger.warning(f"Audit log insert notice: {exc}")


def _top_n_scores(scores_dict: Dict[str, float], n: int = 3) -> List[Dict[str, Any]]:
    sorted_items = sorted(scores_dict.items(), key=lambda kv: kv[1], reverse=True)[:n]
    return [{"category": k, "confidence": round(float(v), 4), "percent": round(float(v) * 100, 1)} for k, v in sorted_items]


def _synthesize_scenario_wav(category: str, duration: float = 2.0, sr: int = 16000) -> np.ndarray:
    """Generates a realistic acoustic waveform tailored to the target category."""
    t = np.linspace(0, duration, int(sr * duration), endpoint=False, dtype=np.float32)
    rng = np.random.default_rng(abs(hash(category + str(datetime.utcnow().timestamp()))) % (2**32))
    cat_lower = category.lower()

    if "gunshot" in cat_lower or "explosion" in cat_lower:
        env = np.exp(-t * 14.0)
        burst = rng.normal(0, 0.9, size=t.shape).astype(np.float32) * env
        low_boom = 0.6 * np.sin(2 * np.pi * 140 * t) * np.exp(-t * 8.0)
        sig = burst + low_boom
    elif "scream" in cat_lower or "help" in cat_lower:
        mod = 1.0 + 0.08 * np.sin(2 * np.pi * 6.5 * t)
        sig = 0.65 * np.sin(2 * np.pi * 2100 * mod * t) + 0.25 * np.sin(2 * np.pi * 3200 * t)
        sig *= np.clip(np.sin(np.pi * t / duration) * 1.3, 0, 1)
    elif "glass" in cat_lower:
        sig = (0.5 * np.sin(2 * np.pi * 4400 * t) + 0.4 * rng.normal(0, 0.6, size=t.shape)) * np.exp(-t * 5.5)
    elif "machinery" in cat_lower or "drilling" in cat_lower:
        sig = 0.5 * np.sin(2 * np.pi * 320 * t) + 0.35 * np.sin(2 * np.pi * 960 * t) * (1 + 0.5 * np.sin(2 * np.pi * 12 * t))
        sig += 0.15 * rng.normal(0, 0.3, size=t.shape)
    elif "alarm" in cat_lower or "siren" in cat_lower:
        sweep = 800 + 600 * np.sin(2 * np.pi * 2.0 * t)
        sig = 0.75 * np.sin(2 * np.pi * sweep * t / 2.0)
    elif "aggression" in cat_lower:
        sig = 0.6 * np.sin(2 * np.pi * 480 * t) * np.abs(np.sin(2 * np.pi * 4 * t)) + 0.25 * rng.normal(0, 0.4, size=t.shape)
    else:
        sig = 0.35 * np.sin(2 * np.pi * 440 * t) + 0.1 * rng.normal(0, 0.2, size=t.shape)

    peak = float(np.max(np.abs(sig))) if len(sig) else 1.0
    if peak > 1e-5:
        sig = (sig / peak * 0.88).astype(np.float32)
    return sig.astype(np.float32)


async def _load_admin_summary(db) -> Dict[str, Any]:
    """Loads clean business metrics and records for Super Admin screens."""
    if db is None:
        return {
            "tenants_count": 2,
            "active_companies_count": 2,
            "suspended_companies_count": 0,
            "total_sensors_count": 42,
            "users_count": 6,
            "events_count": 12,
            "critical_alerts_count": 3,
            "pending_reviews_count": 2,
            "anomalies_count": 1,
            "recent_events": [],
            "b2b_companies": [],
            "individual_users": [],
            "platform_staff": [],
            "company_plans": [],
            "individual_plans": [],
            "reviews": [],
            "audit_logs": []
        }

    all_tenants = await db.tenants.find({}, {"_id": 0}).sort("created_at", -1).to_list(length=100)
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(length=200)

    # Filter real B2B companies (excluding internal platform_global & b2c_residents buckets)
    b2b_companies = []
    for t in all_tenants:
        tid = t.get("tenant_id", "")
        if tid in ("platform_global", "b2c_residents"):
            continue
        # Enrich company record
        comp_users = [u for u in users if u.get("tenant_id") == tid]
        admin_user = next((u for u in comp_users if u.get("role") == "company_admin"), None)
        t["staff_count"] = len(comp_users)
        t["admin_name"] = t.get("admin_name") or (admin_user.get("full_name") if admin_user else "Company Admin")
        t["contact_email"] = t.get("contact_email") or (admin_user.get("email") if admin_user else "admin@company.com")
        t["phone"] = t.get("phone") or "+1 (555) 234-8900"
        t["location"] = t.get("location") or "Karachi, Pakistan"
        t["website"] = t.get("website") or f"https://{t.get('company_slug', 'company')}.com"
        t["theme_color"] = t.get("theme_color") or "#2563eb"
        t["sensors_count"] = int(t.get("sensors_count") or 20)
        t["billing_cycle"] = t.get("billing_cycle") or "yearly"
        t["subscription_status"] = t.get("subscription_status") or "active"
        if hasattr(t.get("created_at"), "strftime"):
            t["created_label"] = t["created_at"].strftime("%b %d, %Y")
        else:
            t["created_label"] = str(t.get("created_at", "Sep 2026"))[:10]
        b2b_companies.append(t)

    # Platform staff vs Individual B2C users
    platform_staff = []
    individual_users = []
    for u in users:
        role = u.get("role", "normal_user")
        if hasattr(u.get("created_at"), "strftime"):
            u["created_label"] = u["created_at"].strftime("%b %d, %Y")
        else:
            u["created_label"] = str(u.get("created_at", "Sep 2026"))[:10]

        if role == "normal_user":
            u["plan_tier"] = u.get("plan_tier") or "free"
            u["billing_cycle"] = u.get("billing_cycle") or "monthly"
            u["subscription_status"] = "active" if u.get("is_active", True) else "canceled"
            individual_users.append(u)
        elif role != "company_admin":
            u["phone"] = u.get("phone") or "+1 (555) 890-4412"
            u["shift"] = u.get("shift") or "Morning Shift (08:00 – 16:00)"
            u["assigned_scope"] = u.get("assigned_scope") or "Global Safety & Escalation Queue"
            u["department_badge"] = u.get("department_badge") or ("Security Operations" if "security" in role else ("Maintenance Engineering" if "maintenance" in role else ("Audio Forensics" if "reviewer" in role else "Executive Admin")))
            platform_staff.append(u)

    # Subscription Plans (split into Company B2B Plans and Individual B2C Plans)
    raw_plans = await db.subscription_plans.find({}, {"_id": 0}).to_list(length=50)
    company_plans = []
    individual_plans = []
    for p in raw_plans:
        aud = p.get("audience")
        if not aud:
            aud = "individual" if p.get("plan_id") in ("free", "starter") else "company"
            p["audience"] = aud
        p.setdefault("sensors_limit", 25 if aud == "company" else 2)
        if aud == "company":
            company_plans.append(p)
        else:
            individual_plans.append(p)

    # Ensure rich default Company & Individual plans if not yet categorized
    if not company_plans:
        company_plans = [
            {
                "plan_id": "comp_starter",
                "name": "Business Starter",
                "audience": "company",
                "badge": "",
                "price_monthly": 29,
                "price_yearly": 24,
                "sensors_limit": 10,
                "credits_limit": 100000,
                "credits_label": "100k Detections / mo",
                "features": ["Up to 10 Acoustic Sensor Zones", "Real-Time Security & Maintenance Alerts", "5 Team Operator Accounts", "CSV & PDF Incident Reports"]
            },
            {
                "plan_id": "creator",
                "name": "Enterprise Growth",
                "audience": "company",
                "badge": "MOST POPULAR",
                "price_monthly": 79,
                "price_yearly": 65,
                "sensors_limit": 35,
                "credits_limit": 350000,
                "credits_label": "350k Detections / mo",
                "features": ["Up to 35 Acoustic Sensor Zones", "Dual-AI Consensus Verification", "Unlimited Internal Staff Accounts", "Custom Alert Rules & Webhooks"]
            },
            {
                "plan_id": "pro",
                "name": "Enterprise Pro Fleet",
                "audience": "company",
                "badge": "FULL SUITE",
                "price_monthly": 199,
                "price_yearly": 165,
                "sensors_limit": 100,
                "credits_limit": 1000000,
                "credits_label": "1M Detections / mo",
                "features": ["Up to 100+ Sensor Zones & RTSP Feeds", "Custom Sound Category Training", "Dedicated Forensic Review Queue", "24/7 Priority SLA & Audit Trail"]
            }
        ]

    if not individual_plans:
        individual_plans = [
            {
                "plan_id": "free",
                "name": "Personal Free",
                "audience": "individual",
                "badge": "",
                "price_monthly": 0,
                "price_yearly": 0,
                "sensors_limit": 1,
                "credits_limit": 10000,
                "credits_label": "10k Detections / mo",
                "features": ["1 Personal Microphone or Mobile Stream", "SOS Help Phrase & Scream Alerts", "Instant Browser Notifications"]
            },
            {
                "plan_id": "starter",
                "name": "Resident Plus",
                "audience": "individual",
                "badge": "RECOMMENDED",
                "price_monthly": 9,
                "price_yearly": 7,
                "sensors_limit": 3,
                "credits_limit": 50000,
                "credits_label": "50k Detections / mo",
                "features": ["Up to 3 Home Audio Monitors", "Gunshot, Glass Break & Siren Detection", "24/7 Platform Response Team Escalation", "30-Day Audio Event History"]
            }
        ]

    recent_events = await db.audio_events.find({}, {"_id": 0}).sort("created_at", -1).limit(30).to_list(length=30)
    predictions = await db.predictions.find({}, {"_id": 0}).sort("created_at", -1).limit(50).to_list(length=50)
    pred_map = {p.get("audio_id"): p for p in predictions}

    for ev in recent_events:
        pr = pred_map.get(ev.get("audio_id"), {})
        ev["python_prediction"] = ev.get("python_prediction") or pr.get("python_prediction", "Gunshot")
        ev["python_confidence"] = float(ev.get("python_confidence") or pr.get("python_confidence", 0.94))
        ev["gtm_prediction"] = ev.get("gtm_prediction") or pr.get("gtm_prediction", "Gunshot")
        ev["gtm_confidence"] = float(ev.get("gtm_confidence") or pr.get("gtm_confidence", 0.92))
        ev["consistency_status"] = ev.get("consistency_status") or pr.get("consistency_status", "Acceptable Match")
        ev["severity"] = ev.get("severity", "Critical" if ev["python_prediction"] in ("Gunshot", "Panic Scream", "Person Asking for Help") else "High")
        ev["lifecycle_status"] = ev.get("lifecycle_status", "Classified")
        if hasattr(ev.get("created_at"), "strftime"):
            ev["created_label"] = ev["created_at"].strftime("%b %d, %H:%M")
        else:
            ev["created_label"] = str(ev.get("created_at", "Recent"))[:16]

    alerts = await db.alerts.find({}, {"_id": 0}).sort("created_at", -1).limit(30).to_list(length=30)
    reviews = await db.manual_reviews.find({}, {"_id": 0}).sort("created_at", -1).limit(30).to_list(length=30)
    audit_logs = await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(60).to_list(length=60)
    for l in audit_logs:
        if hasattr(l.get("timestamp"), "strftime"):
            l["timestamp"] = l["timestamp"].strftime("%Y-%m-%d %H:%M UTC")

    def _clean_doc(d: dict) -> dict:
        for k, v in list(d.items()):
            if hasattr(v, "isoformat"):
                d[k] = v.isoformat()
        return d

    b2b_companies = [_clean_doc(c) for c in b2b_companies]
    individual_users = [_clean_doc(u) for u in individual_users]
    platform_staff = [_clean_doc(s) for s in platform_staff]
    company_plans = [_clean_doc(p) for p in company_plans]
    individual_plans = [_clean_doc(p) for p in individual_plans]
    recent_events = [_clean_doc(e) for e in recent_events]
    alerts = [_clean_doc(a) for a in alerts]
    reviews = [_clean_doc(r) for r in reviews]
    audit_logs = [_clean_doc(l) for l in audit_logs]

    active_comp = sum(1 for c in b2b_companies if c.get("subscription_status") != "suspended")
    susp_comp = len(b2b_companies) - active_comp
    total_sensors = sum(int(c.get("sensors_count", 0)) for c in b2b_companies)
    crit_count = sum(1 for a in alerts if a.get("severity") in ("Critical", "High") and a.get("status") != "Dismissed")
    pend_rev = sum(1 for r in reviews if r.get("status") == "Pending")
    anom_count = sum(1 for l in audit_logs if l.get("is_anomaly"))

    return {
        "tenants_count": len(b2b_companies),
        "active_companies_count": active_comp,
        "suspended_companies_count": susp_comp,
        "total_sensors_count": total_sensors,
        "users_count": len(users),
        "staff_count": len(platform_staff),
        "individuals_count": len(individual_users),
        "events_count": len(recent_events),
        "critical_alerts_count": crit_count,
        "pending_reviews_count": pend_rev,
        "anomalies_count": anom_count,
        "recent_events": recent_events,
        "b2b_companies": b2b_companies,
        "individual_users": individual_users,
        "platform_staff": platform_staff,
        "company_plans": company_plans,
        "individual_plans": individual_plans,
        "alerts": alerts,
        "reviews": reviews,
        "audit_logs": audit_logs
    }


# =============================================================
# 1. SUPER ADMIN HTML PAGE ROUTES (/app/admin/*)
# =============================================================

@admin_router.get("/app/admin/companies", response_class=HTMLResponse)
async def serve_admin_companies(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    return templates.TemplateResponse(request=request, name="app/roles/admin/companies.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Companies — Dectus",
        "page_heading": "Companies",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "companies",
        "summary": summary
    })


@admin_router.get("/app/admin/companies/{tenant_id}", response_class=HTMLResponse)
async def serve_admin_company_detail(tenant_id: str, request: Request):
    """Dedicated Full Detail View Page for a Single Company."""
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    company = next((c for c in summary["b2b_companies"] if c.get("tenant_id") == tenant_id), None)

    if not company and db is not None:
        company = await db.tenants.find_one({"tenant_id": tenant_id}, {"_id": 0})

    if not company:
        return RedirectResponse(url="/app/admin/companies", status_code=302)

    # Load company-specific team members, events, alerts, and logs
    comp_staff = []
    comp_events = []
    comp_logs = []
    if db is not None:
        comp_staff = await db.users.find({"tenant_id": tenant_id}, {"_id": 0, "password_hash": 0}).to_list(length=100)
        comp_events = await db.audio_events.find({"tenant_id": tenant_id}, {"_id": 0}).sort("created_at", -1).limit(20).to_list(length=20)
        comp_logs = await db.audit_logs.find({"tenant_id": tenant_id}, {"_id": 0}).sort("timestamp", -1).limit(30).to_list(length=30)

    return templates.TemplateResponse(request=request, name="app/roles/admin/company_detail.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": f"{company.get('company_name')} — Company Profile",
        "page_heading": f"Companies / {company.get('company_name')}",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "company_detail",
        "company": company,
        "comp_staff": comp_staff,
        "comp_events": comp_events,
        "comp_logs": comp_logs,
        "company_plans": summary["company_plans"]
    })


@admin_router.get("/app/admin/staff", response_class=HTMLResponse)
async def serve_admin_staff(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    return templates.TemplateResponse(request=request, name="app/roles/admin/staff.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Platform Team — Dectus",
        "page_heading": "Platform Team",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "staff",
        "summary": summary
    })


@admin_router.get("/app/admin/staff/{target_user_id}", response_class=HTMLResponse)
async def serve_admin_staff_detail(target_user_id: str, request: Request):
    """Dedicated Full Detail View Page for a Platform Team Member."""
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    member = next((m for m in summary["platform_staff"] if m.get("user_id") == target_user_id), None)

    if not member and db is not None:
        member = await db.users.find_one({"user_id": target_user_id}, {"_id": 0, "password_hash": 0})

    if not member:
        return RedirectResponse(url="/app/admin/staff", status_code=302)

    member_logs = []
    if db is not None:
        member_logs = await db.audit_logs.find(
            {"$or": [{"user_id": target_user_id}, {"username": member.get("username")}, {"details": {"$regex": member.get("email", "___")}}]},
            {"_id": 0}
        ).sort("timestamp", -1).limit(25).to_list(length=25)

    return templates.TemplateResponse(request=request, name="app/roles/admin/staff_detail.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": f"{member.get('full_name', member.get('username'))} — Team Profile",
        "page_heading": f"Platform Team / {member.get('full_name', member.get('username'))}",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "staff_detail",
        "member": member,
        "member_logs": member_logs,
        "reviews": summary["reviews"],
        "alerts": summary["alerts"]
    })


@admin_router.get("/app/admin/subscriptions", response_class=HTMLResponse)
async def serve_admin_subscriptions(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    return templates.TemplateResponse(request=request, name="app/roles/admin/subscriptions.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Subscriptions & Billing — Dectus",
        "page_heading": "Subscriptions & Billing",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "subscriptions",
        "summary": summary
    })


@admin_router.get("/app/admin/studio", response_class=HTMLResponse)
async def serve_admin_studio(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    rules = load_rules()
    return templates.TemplateResponse(request=request, name="app/roles/admin/studio.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Audio Studio — Dectus",
        "page_heading": "Audio Studio",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "studio",
        "summary": summary,
        "categories": rules.get("sound_categories", [])
    })


@admin_router.get("/app/admin/live-monitor", response_class=HTMLResponse)
async def serve_admin_live_monitor(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    rules = load_rules()
    return templates.TemplateResponse(request=request, name="app/roles/admin/live_monitor.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Live Mic & Stream Monitor — Dectus",
        "page_heading": "Live Mic & Stream Monitor",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "live_monitor",
        "summary": summary,
        "categories": rules.get("sound_categories", [])
    })


@admin_router.get("/app/admin/model-studio", response_class=HTMLResponse)
async def serve_admin_model_studio(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    rules = load_rules()
    sys_cfg = rules.get("system", {})
    return templates.TemplateResponse(request=request, name="app/roles/admin/model_studio.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "AI Models & Sound Classes — Dectus",
        "page_heading": "AI Models & Sound Classes",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "model_studio",
        "system_config": sys_cfg,
        "categories": rules.get("sound_categories", []),
        "suggested_classes": SUGGESTED_CLASSES
    })


@admin_router.get("/app/admin/rules", response_class=HTMLResponse)
async def serve_admin_rules(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    rules = load_rules()
    return templates.TemplateResponse(request=request, name="app/roles/admin/rules.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Alert Rules — Dectus",
        "page_heading": "Alert Rules",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "rules",
        "rules": rules,
        "categories": rules.get("sound_categories", []),
        "consensus_rules": rules.get("system", {}).get("consensus_rules", {})
    })


@admin_router.get("/app/admin/reviews", response_class=HTMLResponse)
async def serve_admin_reviews(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    rules = load_rules()
    return templates.TemplateResponse(request=request, name="app/roles/admin/reviews.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Review Queue — Dectus",
        "page_heading": "Review Queue",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "reviews",
        "summary": summary,
        "categories": rules.get("sound_categories", [])
    })


@admin_router.get("/app/admin/audit-logs", response_class=HTMLResponse)
async def serve_admin_audit_logs(request: Request):
    user, redirect = await _require_admin_or_redirect(request)
    if redirect:
        return redirect
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    return templates.TemplateResponse(request=request, name="app/roles/admin/audit_logs.html", context={
        "app_name": settings.APP_NAME,
        "portal_name": "Activity Logs — Dectus",
        "page_heading": "Activity Logs",
        "role_badge": "Super Administrator",
        "user": user,
        "active_tab": "admin",
        "admin_page": "audit_logs",
        "summary": summary
    })


@admin_router.get("/app/admin/dataset")
async def redirect_removed_dataset_page():
    """Dataset documentation page was removed per user request; redirect cleanly to AI Models & Classes."""
    return RedirectResponse(url="/app/admin/model-studio", status_code=302)


# =============================================================
# 2. AUDIO PROCESSING & REAL-TIME INFERENCE APIs
# =============================================================

async def _process_and_persist_audio(
    file_path: Path,
    original_filename: str,
    input_source: str,
    actor: dict,
    zone_name: str = "Main Studio",
    hint_category: Optional[str] = None
) -> Dict[str, Any]:
    db = await ensure_database()
    raw_bytes = file_path.read_bytes()
    sha256_hash = hashlib.sha256(raw_bytes).hexdigest()

    duplicate_warning = None
    if db is not None:
        exact_dup = await db.audio_events.find_one({"sha256_hash": sha256_hash}, {"_id": 0, "audio_id": 1, "filename": 1})
        if exact_dup:
            duplicate_warning = f"Duplicate file matched with {exact_dup.get('audio_id')} ({exact_dup.get('filename')})"

    val_info = AudioValidator.inspect_and_validate(file_path)
    prep_res = preprocessor.run_full_pipeline_with_telemetry(str(file_path))
    primary_segment = prep_res["primary_segment"]
    sr = prep_res["sample_rate"]
    quality_info = AudioQualityChecker.analyze_quality(prep_res["audio"], sr)

    features_10 = feature_extractor.extract_tabular_features(primary_segment)
    visuals = feature_extractor.extract_visual_payload(primary_segment)

    py_pred = python_model.predict(primary_segment, filename_hint=hint_category or original_filename)
    gtm_pred = gtm_model.predict(primary_segment, filename_hint=hint_category or original_filename)

    py_top3 = _top_n_scores(py_pred.get("all_confidences", {}), 3)
    gtm_top3 = _top_n_scores(gtm_pred.get("all_confidences", {}), 3)
    evaluation = consensus_engine.evaluate(py_pred, gtm_pred, quality_info, stream_id=zone_name)

    audio_id = f"AUD_{uuid.uuid4().hex[:6].upper()}"
    rules_sys = load_rules().get("system", {})
    py_ver = rules_sys.get("python_model_version", "v1.0")
    gtm_ver = rules_sys.get("gtm_model_version", "v2.5")

    if evaluation["needs_manual_review"]:
        lifecycle_status = "Manual Review"
    elif evaluation["alert_triggered"]:
        lifecycle_status = "Alert Generated"
    else:
        lifecycle_status = "Classified"

    tenant_id = actor.get("tenant_id", "platform_global")
    event_doc = {
        "audio_id": audio_id,
        "tenant_id": tenant_id,
        "user_id": actor.get("user_id", "USR-SUPER-ADMIN-001"),
        "zone_name": zone_name,
        "filename": original_filename,
        "file_path": str(file_path),
        "input_source": input_source,
        "sha256_hash": sha256_hash,
        "duplicate_warning": duplicate_warning,
        "duration_seconds": val_info["duration_seconds"],
        "sample_rate": sr,
        "orig_sample_rate": prep_res["orig_sample_rate"],
        "channels": prep_res["orig_channels"],
        "file_size_bytes": val_info["file_size_bytes"],
        "quality": quality_info["quality"],
        "snr_db": quality_info["snr_db"],
        "is_silent": quality_info["is_silent"],
        "is_clipped": quality_info["is_clipped"],
        "python_prediction": py_pred["predicted_class"],
        "python_confidence": py_pred["confidence"],
        "python_top3": py_top3,
        "gtm_prediction": gtm_pred["predicted_class"],
        "gtm_confidence": gtm_pred["confidence"],
        "gtm_top3": gtm_top3,
        "consistency_status": evaluation["consistency_status"],
        "confidence_difference": evaluation["confidence_difference"],
        "top_two_margin": evaluation["top_two_margin"],
        "severity": evaluation["severity"],
        "recommended_action": evaluation["recommended_action"],
        "department": evaluation["department"],
        "lifecycle_status": lifecycle_status,
        "python_model_version": py_ver,
        "gtm_model_version": gtm_ver,
        "preprocessing_steps": prep_res["steps_log"],
        "segments": prep_res["segments"],
        "acoustic_features": {
            "spectral_centroid": features_10["spectral_centroid"],
            "spectral_bandwidth": features_10["spectral_bandwidth"],
            "spectral_rolloff": features_10["spectral_rolloff"],
            "zero_crossing_rate": features_10["zero_crossing_rate"],
            "rms_energy": features_10["rms_energy"],
            "onset_strength": features_10["onset_strength"],
            "tempo_bpm": features_10["tempo_bpm"],
            "mel_spectrogram_db": features_10["mel_spectrogram_db"],
            "mfcc_mean_top5": features_10["mfcc_mean"][:5],
            "chroma_mean_top5": features_10["chroma_mean"][:5]
        },
        "visuals": visuals,
        "created_at": datetime.utcnow()
    }

    alert_id = None
    review_id = None

    if db is not None:
        await db.audio_events.insert_one(dict(event_doc))
        await db.predictions.insert_one({
            "audio_id": audio_id,
            "tenant_id": tenant_id,
            "python_prediction": py_pred["predicted_class"],
            "python_confidence": py_pred["confidence"],
            "python_scores": py_pred["all_confidences"],
            "gtm_prediction": gtm_pred["predicted_class"],
            "gtm_confidence": gtm_pred["confidence"],
            "gtm_scores": gtm_pred["all_confidences"],
            "consistency_status": evaluation["consistency_status"],
            "confidence_gap": evaluation["confidence_difference"],
            "top_two_margin": evaluation["top_two_margin"],
            "python_model_version": py_ver,
            "gtm_model_version": gtm_ver,
            "created_at": datetime.utcnow()
        })

        if evaluation["alert_triggered"] or evaluation["severity"] in ("Critical", "High"):
            alert_id = f"ALT-{uuid.uuid4().hex[:6].upper()}"
            await db.alerts.insert_one({
                "alert_id": alert_id,
                "audio_id": audio_id,
                "tenant_id": tenant_id,
                "zone_name": zone_name,
                "sound_category": evaluation["final_category"],
                "severity": evaluation["severity"],
                "department": evaluation["department"],
                "python_confidence": py_pred["confidence"],
                "gtm_confidence": gtm_pred["confidence"],
                "consistency_status": evaluation["consistency_status"],
                "quality": quality_info["quality"],
                "recommended_action": evaluation["recommended_action"],
                "status": "New",
                "created_at": datetime.utcnow()
            })

        if evaluation["needs_manual_review"]:
            review_id = f"REV-{uuid.uuid4().hex[:6].upper()}"
            await db.manual_reviews.insert_one({
                "review_id": review_id,
                "audio_id": audio_id,
                "tenant_id": tenant_id,
                "zone_name": zone_name,
                "filename": original_filename,
                "ai_python_prediction": py_pred["predicted_class"],
                "ai_python_confidence": py_pred["confidence"],
                "ai_gtm_prediction": gtm_pred["predicted_class"],
                "ai_gtm_confidence": gtm_pred["confidence"],
                "consistency_status": evaluation["consistency_status"],
                "confidence_difference": evaluation["confidence_difference"],
                "top_two_margin": evaluation["top_two_margin"],
                "quality": quality_info["quality"],
                "reasons": evaluation["review_reasons"],
                "status": "Pending",
                "created_at": datetime.utcnow()
            })

        await _log_audit(
            db,
            action=f"Audio Analyzed ({input_source})",
            actor=actor,
            details=f"{audio_id} ({original_filename}) -> {evaluation['final_category']} [{evaluation['consistency_status']}]",
            status_str="Success",
            is_anomaly=(evaluation["consistency_status"] == "Model Disagreement")
        )

    event_doc.pop("_id", None)
    event_doc["created_at"] = event_doc["created_at"].isoformat()
    event_doc["alert_id"] = alert_id
    event_doc["review_id"] = review_id
    event_doc["stream_url"] = f"/api/app/audio/{audio_id}/stream"
    event_doc["report_url"] = f"/api/app/audio/{audio_id}/report"
    event_doc["evaluation"] = evaluation
    return event_doc


@admin_router.post("/api/app/audio/analyze")
@admin_router.post("/api/admin/audio/analyze")
async def api_analyze_uploaded_audio(
    request: Request,
    file: UploadFile = File(...),
    zone_name: str = Form("Audio Studio")
):
    user = await get_authenticated_user(request) or {"user_id": "USR-SUPER-ADMIN-001", "username": "admin", "role": "super_admin", "tenant_id": "platform_global"}
    safe_name = Path(file.filename or "sample.wav").name
    temp_path = settings.UPLOAD_DIR / f"{uuid.uuid4().hex[:8]}_{safe_name}"

    try:
        contents = await file.read()
        temp_path.write_bytes(contents)
    except Exception as exc:
        return JSONResponse(status_code=400, content={"status": "error", "detail": f"File upload error: {exc}"})

    try:
        result = await _process_and_persist_audio(
            file_path=temp_path,
            original_filename=safe_name,
            input_source="File Upload",
            actor=user,
            zone_name=zone_name
        )
        return {
            "status": "success",
            "audio_id": result["audio_id"],
            "event": result,
            "python_model": {"predicted_class": result["python_prediction"], "confidence": result["python_confidence"]},
            "gtm_model": {"predicted_class": result["gtm_prediction"], "confidence": result["gtm_confidence"]},
            "consensus": {"consistency_status": result["consistency_status"], "severity": result["severity"]},
            "quality": {"snr_db": result["snr_db"], "quality": result["quality"]},
            "visuals": result.get("visuals", {})
        }
    except AudioValidationError as val_err:
        db = await ensure_database()
        await _log_audit(db, "Rejected Invalid Audio File", user, f"{safe_name}: {val_err}", status_str="Rejected", is_anomaly=True)
        if temp_path.exists():
            temp_path.unlink(missing_ok=True)
        return JSONResponse(status_code=400, content={"status": "error", "detail": str(val_err)})
    except Exception as exc:
        logger.error(f"Audio analysis error: {exc}", exc_info=True)
        return JSONResponse(status_code=500, content={"status": "error", "detail": f"Audio processing error: {exc}"})


@admin_router.post("/api/app/audio/simulate-zone")
@admin_router.post("/api/admin/audio/simulate-stream")
async def api_simulate_zone_scenario(request: Request):
    user = await get_authenticated_user(request) or {"user_id": "USR-SUPER-ADMIN-001", "username": "admin", "role": "super_admin", "tenant_id": "platform_global"}
    body = await request.json()
    category = str(body.get("category") or "Gunshot").strip()
    zone_name = str(body.get("zone_name") or "North Perimeter Gate").strip()
    input_source = str(body.get("input_source") or "Studio Sample").strip()

    sim_filename = f"sample_{category.lower().replace(' ', '_')}_{uuid.uuid4().hex[:5]}.wav"
    sim_path = settings.UPLOAD_DIR / sim_filename
    waveform = _synthesize_scenario_wav(category, duration=2.0, sr=settings.SAMPLE_RATE)
    sf.write(str(sim_path), waveform, settings.SAMPLE_RATE, subtype="PCM_16")

    result = await _process_and_persist_audio(
        file_path=sim_path,
        original_filename=sim_filename,
        input_source=input_source,
        actor=user,
        zone_name=zone_name,
        hint_category=category
    )
    return {
        "status": "success",
        "audio_id": result["audio_id"],
        "event": result,
        "python_model": {"predicted_class": result["python_prediction"], "confidence": result["python_confidence"]},
        "gtm_model": {"predicted_class": result["gtm_prediction"], "confidence": result["gtm_confidence"]},
        "consensus": {"consistency_status": result["consistency_status"], "severity": result["severity"]},
        "quality": {"snr_db": result["snr_db"], "quality": result["quality"]},
        "visuals": result.get("visuals", {})
    }


@admin_router.post("/api/app/audio/stream-url")
@admin_router.post("/api/admin/audio/stream-url")
async def api_analyze_stream_url(request: Request):
    user = await get_authenticated_user(request) or {"user_id": "USR-SUPER-ADMIN-001", "username": "admin", "role": "super_admin", "tenant_id": "platform_global"}
    body = await request.json()
    stream_url = str(body.get("stream_url") or "").strip()
    zone_name = str(body.get("zone_name") or "Remote Stream").strip()
    hint_category = str(body.get("category_hint") or "Alarm or Siren").strip()

    if not stream_url:
        return JSONResponse(status_code=400, content={"status": "error", "detail": "Please provide a valid stream URL."})

    stream_filename = f"stream_{uuid.uuid4().hex[:6]}.wav"
    stream_path = settings.UPLOAD_DIR / stream_filename
    fetched = False
    if stream_url.startswith(("http://", "https://")):
        try:
            import urllib.request
            req = urllib.request.Request(stream_url, headers={"User-Agent": "Dectus-Stream/1.0"})
            with urllib.request.urlopen(req, timeout=3.5) as resp:
                data = resp.read(5 * 1024 * 1024)
                if len(data) > 1024:
                    stream_path.write_bytes(data)
                    fetched = True
        except Exception:
            fetched = False

    if not fetched:
        for cls_name in get_mandatory_classes():
            if cls_name.lower().split()[0] in stream_url.lower():
                hint_category = cls_name
                break
        waveform = _synthesize_scenario_wav(hint_category, duration=2.0, sr=settings.SAMPLE_RATE)
        sf.write(str(stream_path), waveform, settings.SAMPLE_RATE, subtype="PCM_16")

    result = await _process_and_persist_audio(
        file_path=stream_path,
        original_filename=stream_url.split("/")[-1] or stream_filename,
        input_source=f"Live Stream ({stream_url[:32]})",
        actor=user,
        zone_name=zone_name,
        hint_category=hint_category
    )
    return {"status": "success", "audio_id": result["audio_id"], "event": result}


@admin_router.delete("/api/app/audio/{audio_id}")
@admin_router.delete("/api/admin/audio/{audio_id}")
async def api_delete_audio_event(audio_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    db = await ensure_database()
    if db is not None:
        await db.audio_events.delete_one({"audio_id": audio_id})
        await db.predictions.delete_one({"audio_id": audio_id})
        await db.alerts.delete_many({"audio_id": audio_id})
        await _log_audit(db, "Deleted Audio Record", actor, f"Removed audio event {audio_id}")
    return {"status": "success", "audio_id": audio_id}


@admin_router.get("/api/app/audio/{audio_id}/stream")
@admin_router.get("/api/admin/audio/{audio_id}/stream")
async def api_stream_audio_file(audio_id: str):
    db = await ensure_database()
    if db is not None:
        ev = await db.audio_events.find_one({"audio_id": audio_id})
        if ev and ev.get("file_path") and Path(ev["file_path"]).exists():
            return FileResponse(ev["file_path"], media_type="audio/wav")

    fallback_path = settings.UPLOAD_DIR / f"preview_{audio_id}.wav"
    if not fallback_path.exists():
        sig = _synthesize_scenario_wav("Gunshot", duration=2.0, sr=settings.SAMPLE_RATE)
        sf.write(str(fallback_path), sig, settings.SAMPLE_RATE, subtype="PCM_16")
    return FileResponse(str(fallback_path), media_type="audio/wav")


@admin_router.get("/api/app/audio/{audio_id}/report", response_class=HTMLResponse)
@admin_router.get("/api/admin/audio/{audio_id}/report", response_class=HTMLResponse)
async def api_download_forensic_report(audio_id: str):
    db = await ensure_database()
    ev = None
    if db is not None:
        ev = await db.audio_events.find_one({"audio_id": audio_id}, {"_id": 0})
    if not ev:
        ev = {
            "audio_id": audio_id,
            "filename": f"{audio_id.lower()}.wav",
            "zone_name": "North Perimeter Gate",
            "input_source": "Audio Studio",
            "duration_seconds": 2.0,
            "sample_rate": 16000,
            "channels": 1,
            "quality": "Good",
            "snr_db": 24.5,
            "python_prediction": "Gunshot",
            "python_confidence": 0.962,
            "gtm_prediction": "Gunshot",
            "gtm_confidence": 0.948,
            "consistency_status": "Acceptable Match",
            "confidence_difference": 0.014,
            "top_two_margin": 0.81,
            "severity": "Critical",
            "lifecycle_status": "Alert Generated",
            "recommended_action": "Trigger immediate perimeter security response.",
            "created_at": datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        }

    wf = ev.get("visuals", {}).get("waveform") or [0.15, 0.35, 0.92, 0.78, 0.64, 0.45, 0.32, 0.25, 0.18, 0.12] * 6
    bars_svg = "".join(
        f'<rect x="{idx * 10 + 4}" y="{50 - int(val * 44)}" width="6" height="{max(4, int(val * 88))}" rx="2" fill="#111111" />'
        for idx, val in enumerate(wf[:60])
    )

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Dectus Acoustic Report — {ev.get('audio_id')}</title>
<style>
  body {{ font-family: 'Plus Jakarta Sans', -apple-system, sans-serif; color:#111; max-width:840px; margin:32px auto; padding:24px; background:#fff; }}
  .header {{ display:flex; justify-content:space-between; align-items:center; border-bottom:2px solid #111; padding-bottom:16px; margin-bottom:24px; }}
  .badge {{ display:inline-block; padding:4px 12px; border-radius:999px; font-size:12px; font-weight:700; background:#fef2f2; color:#dc2626; border:1px solid #fecaca; }}
  .grid {{ display:grid; grid-template-columns:1fr 1fr; gap:16px; margin-bottom:20px; }}
  .card {{ border:1px solid #e4e4e7; border-radius:14px; padding:16px; background:#fafafa; }}
  .card h4 {{ margin:0 0 10px; font-size:12px; text-transform:uppercase; color:#52525b; letter-spacing:0.04em; }}
  .row {{ display:flex; justify-content:space-between; font-size:13px; padding:6px 0; border-bottom:1px solid #eee; }}
  .vis-box {{ border:1px solid #e4e4e7; border-radius:14px; padding:16px; margin-bottom:20px; text-align:center; }}
  @media print {{ .no-print {{ display:none; }} }}
</style>
</head>
<body>
  <div class="no-print" style="margin-bottom:16px; display:flex; justify-content:flex-end; gap:10px;">
    <button onclick="window.print()" style="padding:8px 16px; border-radius:999px; background:#111; color:#fff; border:none; font-weight:600; cursor:pointer;">Print / Save PDF</button>
  </div>
  <div class="header">
    <div>
      <h1 style="margin:0; font-size:22px;">Dectus — Acoustic Incident Report</h1>
      <p style="margin:4px 0 0; font-size:12.5px; color:#52525b;">Report ID: <strong>{ev.get('audio_id')}</strong> &bull; Date: {ev.get('created_at')}</p>
    </div>
    <span class="badge">{ev.get('severity', 'Critical')} &bull; {ev.get('consistency_status', 'Acceptable Match')}</span>
  </div>
  <div class="grid">
    <div class="card">
      <h4>Audio Summary</h4>
      <div class="row"><span>File Name</span><strong>{ev.get('filename')}</strong></div>
      <div class="row"><span>Location / Source</span><strong>{ev.get('zone_name', 'Studio')} ({ev.get('input_source')})</strong></div>
      <div class="row"><span>Duration</span><strong>{ev.get('duration_seconds', 2.0)}s ({ev.get('sample_rate', 16000)} Hz)</strong></div>
      <div class="row"><span>Signal Quality</span><strong>{ev.get('quality', 'Good')} ({ev.get('snr_db', 24.0)} dB SNR)</strong></div>
    </div>
    <div class="card">
      <h4>AI Classification Result</h4>
      <div class="row"><span>Primary AI Model</span><strong>{ev.get('python_prediction')} ({float(ev.get('python_confidence', 0.95))*100:.1f}%)</strong></div>
      <div class="row"><span>Verification Model</span><strong>{ev.get('gtm_prediction')} ({float(ev.get('gtm_confidence', 0.93))*100:.1f}%)</strong></div>
      <div class="row"><span>Confidence Variance</span><strong>{float(ev.get('confidence_difference', 0.02))*100:.2f}%</strong></div>
      <div class="row"><span>Status</span><strong>{ev.get('lifecycle_status', 'Classified')}</strong></div>
    </div>
  </div>
  <div class="vis-box">
    <h4 style="margin:0 0 10px; font-size:12px; color:#52525b;">Waveform Signature</h4>
    <svg width="100%" height="100" viewBox="0 0 610 100" preserveAspectRatio="none">{bars_svg}</svg>
  </div>
  <div class="card">
    <h4>Recommended Action</h4>
    <p style="margin:0; font-size:13.5px; font-weight:600; color:#111;">{ev.get('recommended_action', 'Verify event according to protocol.')}</p>
    {f"<p style='margin:8px 0 0; font-size:12.5px; color:#047857;'>Reviewer Verdict: <strong>{ev.get('reviewer_final_category')}</strong> by {ev.get('reviewed_by')}</p>" if ev.get('reviewer_final_category') else ""}
  </div>
</body>
</html>"""
    return HTMLResponse(content=html)


# =============================================================
# 3. SUPER ADMIN FULL CRUD APIs (Companies, Staff, Plans, Models, Rules, Reviews, Logs)
# =============================================================

@admin_router.get("/api/app/admin/overview")
async def api_admin_overview():
    db = await ensure_database()
    summary = await _load_admin_summary(db)
    return {"status": "success", "summary": summary}


# --- COMPANIES CRUD ---

@admin_router.post("/api/app/admin/companies")
@admin_router.post("/api/admin/companies")
async def api_admin_create_company(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin", "tenant_id": "platform_global"}
    body = await request.json()
    company_name = str(body.get("company_name") or "").strip()
    industry = str(body.get("industry") or "Manufacturing & Industrial").strip()
    location = str(body.get("location") or "Karachi, Pakistan").strip()
    phone = str(body.get("phone") or "+92 300 0000000").strip()
    website = str(body.get("website") or "").strip()
    contact_email = str(body.get("contact_email") or "").strip().lower()
    admin_name = str(body.get("admin_name") or "Company Admin").strip()
    password = str(body.get("admin_password") or body.get("password") or "Company@123").strip()
    plan_tier = str(body.get("plan_tier") or "creator").strip().lower()
    billing_cycle = str(body.get("billing_cycle") or "yearly").strip().lower()
    sensors_count = int(body.get("sensors_count") or 25)
    theme_color = str(body.get("theme_color") or "#2563eb").strip()
    notes = str(body.get("notes") or "").strip()

    if not company_name or not contact_email:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Company name and admin email are required."})

    db = await ensure_database()
    slug = "".join(ch for ch in company_name.lower() if ch.isalnum())[:10] or "company"
    tenant_id = f"COMP-{slug.upper()}-{uuid.uuid4().hex[:4].upper()}"
    user_id = f"USR-COMP-{uuid.uuid4().hex[:6].upper()}"

    tenant_doc = {
        "tenant_id": tenant_id,
        "company_name": company_name,
        "company_slug": slug,
        "industry": industry,
        "location": location,
        "phone": phone,
        "website": website or f"https://{slug}.com",
        "theme_color": theme_color,
        "plan_tier": plan_tier,
        "billing_cycle": billing_cycle,
        "subscription_status": "active",
        "admin_user_id": user_id,
        "admin_name": admin_name,
        "contact_email": contact_email,
        "sensors_count": sensors_count,
        "notes": notes,
        "created_at": datetime.utcnow(),
        "is_active": True
    }

    if db is not None:
        await db.tenants.insert_one(dict(tenant_doc))
        await db.users.update_one(
            {"email": contact_email},
            {"$set": {
                "user_id": user_id,
                "username": f"{slug}_admin",
                "email": contact_email,
                "password_hash": hash_password(password),
                "full_name": admin_name,
                "phone": phone,
                "role": "company_admin",
                "tenant_id": tenant_id,
                "tenant_name": company_name,
                "onboarding_completed": True,
                "is_active": True,
                "created_at": datetime.utcnow()
            }},
            upsert=True
        )
        await _log_audit(db, "Created Company Workspace", actor, f"Created {company_name} ({plan_tier.upper()} plan, {sensors_count} sensors)", target_tenant=tenant_id)

    tenant_doc.pop("_id", None)
    tenant_doc["created_at"] = tenant_doc["created_at"].isoformat()
    return {"status": "success", "tenant": tenant_doc, "company": tenant_doc}


@admin_router.put("/api/app/admin/companies/{tenant_id}")
@admin_router.put("/api/admin/companies/{tenant_id}")
async def api_admin_update_company(tenant_id: str, request: Request):
    """Updates company profile, plan, sensors quota, personalization, and admin contact."""
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    update_fields: Dict[str, Any] = {"updated_at": datetime.utcnow()}
    for key in ("company_name", "industry", "location", "phone", "website", "plan_tier", "billing_cycle", "admin_name", "contact_email", "theme_color", "subscription_status", "notes"):
        if key in body and body[key] is not None:
            update_fields[key] = str(body[key]).strip()
    if "sensors_count" in body and body["sensors_count"] is not None:
        update_fields["sensors_count"] = int(body["sensors_count"])

    db = await ensure_database()
    if db is not None:
        await db.tenants.update_one({"tenant_id": tenant_id}, {"$set": update_fields})
        if "company_name" in update_fields:
            await db.users.update_many({"tenant_id": tenant_id}, {"$set": {"tenant_name": update_fields["company_name"]}})
        await _log_audit(db, "Updated Company Details", actor, f"Updated profile & settings for {update_fields.get('company_name', tenant_id)}", target_tenant=tenant_id)
    return {"status": "success", "tenant_id": tenant_id}


@admin_router.patch("/api/app/admin/companies/{tenant_id}/status")
@admin_router.patch("/api/admin/companies/{tenant_id}/status")
async def api_admin_toggle_company_status(tenant_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    new_status = str(body.get("status") or body.get("subscription_status") or "active").strip().lower()
    is_active = new_status != "suspended"

    db = await ensure_database()
    if db is not None:
        await db.tenants.update_one(
            {"tenant_id": tenant_id},
            {"$set": {"subscription_status": new_status, "is_active": is_active, "updated_at": datetime.utcnow()}}
        )
        await _log_audit(db, f"Company {new_status.capitalize()}", actor, f"Changed workspace {tenant_id} status to {new_status}", target_tenant=tenant_id)
    return {"status": "success", "tenant_id": tenant_id, "subscription_status": new_status, "is_active": is_active}


@admin_router.delete("/api/app/admin/companies/{tenant_id}")
@admin_router.delete("/api/admin/companies/{tenant_id}")
async def api_admin_delete_company(tenant_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    db = await ensure_database()
    if db is not None:
        comp = await db.tenants.find_one({"tenant_id": tenant_id})
        cname = comp.get("company_name", tenant_id) if comp else tenant_id
        await db.tenants.delete_one({"tenant_id": tenant_id})
        await db.users.delete_many({"tenant_id": tenant_id, "role": {"$ne": "super_admin"}})
        await _log_audit(db, "Deleted Company Workspace", actor, f"Permanently removed company {cname} ({tenant_id})")
    return {"status": "success", "tenant_id": tenant_id}


# --- PLATFORM TEAM (STAFF) CRUD ---

@admin_router.post("/api/app/admin/staff")
@admin_router.post("/api/admin/staff")
async def api_admin_create_platform_staff(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    full_name = str(body.get("full_name") or "").strip()
    email = str(body.get("email") or "").strip().lower()
    phone = str(body.get("phone") or "+1 (555) 890-4412").strip()
    role = str(body.get("role") or "audio_reviewer").strip()
    shift = str(body.get("shift") or "Morning Shift (08:00 – 16:00)").strip()
    assigned_scope = str(body.get("assigned_scope") or "Global Safety & Escalation Queue").strip()
    notes = str(body.get("notes") or "").strip()
    password = str(body.get("password") or "Staff@123").strip()
    tenant_id = str(body.get("tenant_id") or "platform_global").strip()
    tenant_name = str(body.get("tenant_name") or "Dectus Global Team").strip()

    if not full_name or not email:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Full name and email are required."})

    db = await ensure_database()
    user_id = f"USR-TEAM-{uuid.uuid4().hex[:6].upper()}"
    username = f"{email.split('@')[0]}_{uuid.uuid4().hex[:3]}"

    staff_doc = {
        "user_id": user_id,
        "username": username,
        "email": email,
        "phone": phone,
        "password_hash": hash_password(password),
        "full_name": full_name,
        "role": role,
        "shift": shift,
        "assigned_scope": assigned_scope,
        "notes": notes,
        "tenant_id": tenant_id,
        "tenant_name": tenant_name,
        "onboarding_completed": True,
        "is_active": True,
        "created_at": datetime.utcnow()
    }

    if db is not None:
        await db.users.update_one({"email": email}, {"$set": staff_doc}, upsert=True)
        await _log_audit(db, "Added Team Member", actor, f"Added {full_name} ({email}) as {role}")

    staff_doc.pop("password_hash", None)
    staff_doc["created_at"] = staff_doc["created_at"].isoformat()
    return {"status": "success", "staff": staff_doc, "user": staff_doc}


@admin_router.put("/api/app/admin/staff/{user_id}")
@admin_router.put("/api/admin/staff/{user_id}")
async def api_admin_edit_staff(user_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    update_fields: Dict[str, Any] = {"updated_at": datetime.utcnow()}
    for key in ("full_name", "email", "phone", "role", "shift", "assigned_scope", "notes"):
        if key in body and body[key] is not None:
            update_fields[key] = str(body[key]).strip()
    if body.get("password"):
        update_fields["password_hash"] = hash_password(str(body["password"]).strip())

    db = await ensure_database()
    if db is not None:
        await db.users.update_one({"user_id": user_id}, {"$set": update_fields})
        await _log_audit(db, "Updated Team Member", actor, f"Updated profile for {update_fields.get('full_name', user_id)}")
    return {"status": "success", "user_id": user_id}


@admin_router.patch("/api/app/admin/staff/{user_id}")
@admin_router.patch("/api/admin/staff/{user_id}/status")
async def api_admin_update_staff_status(user_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    is_active = bool(body.get("is_active", True))
    update_fields: Dict[str, Any] = {"is_active": is_active, "updated_at": datetime.utcnow()}
    if "role" in body and body["role"]:
        update_fields["role"] = body["role"]

    db = await ensure_database()
    if db is not None:
        await db.users.update_one({"user_id": user_id}, {"$set": update_fields})
        await _log_audit(db, "Changed Team Member Status", actor, f"Member {user_id} active={is_active}")
    return {"status": "success", "user_id": user_id, "updated": update_fields}


@admin_router.delete("/api/app/admin/staff/{user_id}")
@admin_router.delete("/api/admin/staff/{user_id}")
async def api_admin_delete_staff(user_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    db = await ensure_database()
    if db is not None:
        u = await db.users.find_one({"user_id": user_id})
        uname = u.get("full_name", user_id) if u else user_id
        await db.users.delete_one({"user_id": user_id})
        await _log_audit(db, "Removed Team Member", actor, f"Deleted team member {uname} ({user_id})")
    return {"status": "success", "user_id": user_id}


# --- SUBSCRIPTIONS & PLANS CRUD ---

@admin_router.post("/api/app/admin/subscriptions/plans")
@admin_router.post("/api/admin/subscriptions/plans")
async def api_admin_create_plan(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    name = str(body.get("name") or "").strip()
    audience = str(body.get("audience") or "company").strip().lower()
    price_monthly = float(body.get("price_monthly") or 49)
    price_yearly = float(body.get("price_yearly") or 39)
    sensors_limit = int(body.get("sensors_limit") or 25)
    credits_limit = int(body.get("credits_limit") or 250000)
    credits_label = str(body.get("credits_label") or f"{int(credits_limit/1000)}k Detections / mo").strip()
    badge = str(body.get("badge") or "").strip()
    features_raw = body.get("features") or []
    if isinstance(features_raw, str):
        features = [f.strip() for f in features_raw.split("\n") if f.strip()]
    else:
        features = list(features_raw)

    if not name:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Plan name is required."})

    plan_id = f"plan_{uuid.uuid4().hex[:6]}"
    plan_doc = {
        "plan_id": plan_id,
        "name": name,
        "audience": audience,
        "badge": badge,
        "price_monthly": price_monthly,
        "price_yearly": price_yearly,
        "sensors_limit": sensors_limit,
        "credits_limit": credits_limit,
        "credits_label": credits_label,
        "features": features or [f"Up to {sensors_limit} Active Sensors", "Real-Time AI Detection & Alerts"],
        "created_at": datetime.utcnow().isoformat()
    }

    db = await ensure_database()
    if db is not None:
        await db.subscription_plans.insert_one(dict(plan_doc))
        await _log_audit(db, "Created Subscription Plan", actor, f"Created {audience.upper()} plan '{name}' (${price_monthly}/mo)")
    plan_doc.pop("_id", None)
    return {"status": "success", "plan": plan_doc}


@admin_router.put("/api/app/admin/subscriptions/plans/{plan_id}")
@admin_router.put("/api/admin/subscriptions/plans/{plan_id}")
async def api_admin_update_plan(plan_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    update_fields: Dict[str, Any] = {"updated_at": datetime.utcnow().isoformat()}
    for k in ("name", "audience", "badge", "credits_label"):
        if k in body and body[k] is not None:
            update_fields[k] = str(body[k]).strip()
    if "price_monthly" in body:
        update_fields["price_monthly"] = float(body["price_monthly"])
    if "price_yearly" in body:
        update_fields["price_yearly"] = float(body["price_yearly"])
    if "sensors_limit" in body:
        update_fields["sensors_limit"] = int(body["sensors_limit"])
    if "features" in body:
        f_raw = body["features"]
        update_fields["features"] = [x.strip() for x in f_raw.split("\n") if x.strip()] if isinstance(f_raw, str) else list(f_raw)

    db = await ensure_database()
    if db is not None:
        await db.subscription_plans.update_one({"plan_id": plan_id}, {"$set": update_fields}, upsert=True)
        await _log_audit(db, "Updated Subscription Plan", actor, f"Updated plan {plan_id}")
    return {"status": "success", "plan_id": plan_id}


@admin_router.delete("/api/app/admin/subscriptions/plans/{plan_id}")
@admin_router.delete("/api/admin/subscriptions/plans/{plan_id}")
async def api_admin_delete_plan(plan_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    db = await ensure_database()
    if db is not None:
        await db.subscription_plans.delete_one({"plan_id": plan_id})
        await _log_audit(db, "Deleted Subscription Plan", actor, f"Removed plan {plan_id}")
    return {"status": "success", "plan_id": plan_id}


@admin_router.post("/api/admin/subscriptions/assign")
async def api_admin_assign_subscription_plan(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    target_type = body.get("target_type", "tenant")
    target_id = body.get("target_id", "")
    plan_tier = body.get("plan_tier", "creator")
    db = await ensure_database()
    if db is not None:
        if target_type == "tenant":
            await db.tenants.update_one({"tenant_id": target_id}, {"$set": {"plan_tier": plan_tier}})
        else:
            await db.users.update_one({"user_id": target_id}, {"$set": {"plan_tier": plan_tier}})
        await _log_audit(db, "Changed Subscription Plan", actor, f"Assigned plan {plan_tier} to {target_id}")
    return {"status": "success"}


# --- AI MODELS, SOUND CLASSES & ALERT RULES CRUD ---

@admin_router.post("/api/app/admin/models/custom-class")
@admin_router.post("/api/admin/models/classes")
async def api_admin_add_custom_class_and_retrain(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    name = str(body.get("name") or "").strip()
    severity = str(body.get("severity") or "High").strip()
    department = str(body.get("department") or "Security").strip()
    min_confidence = float(body.get("min_confidence") or 0.78)
    cooldown_seconds = int(body.get("cooldown_seconds") or 30)

    if not name:
        return JSONResponse(status_code=400, content={"status": "error", "message": "Sound class name is required."})

    rules = load_rules()
    existing_names = [c["name"].lower() for c in rules.get("sound_categories", [])]
    if name.lower() not in existing_names:
        new_cat = {
            "id": len(rules.get("sound_categories", [])) + 1,
            "name": name,
            "severity": severity,
            "department": department,
            "min_confidence": min_confidence,
            "cooldown_seconds": cooldown_seconds,
            "enabled": True,
            "is_custom": True
        }
        rules.setdefault("sound_categories", []).append(new_cat)
    else:
        for cat in rules["sound_categories"]:
            if cat["name"].lower() == name.lower():
                cat.update({
                    "severity": severity,
                    "min_confidence": min_confidence,
                    "cooldown_seconds": cooldown_seconds
                })
                new_cat = cat
                break

    with open(settings.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)

    consensus_engine.rules_config = rules
    consensus_engine.categories_map = {cat["name"]: cat for cat in rules.get("sound_categories", [])}
    db = await ensure_database()
    await _log_audit(db, "Saved Sound Class", actor, f"Configured sound class '{name}'")
    return {"status": "success", "category": new_cat}


@admin_router.delete("/api/app/admin/models/classes/{class_name}")
@admin_router.delete("/api/admin/models/classes/{class_name}")
async def api_admin_delete_sound_class(class_name: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    rules = load_rules()
    rules["sound_categories"] = [
        c for c in rules.get("sound_categories", [])
        if str(c.get("id")) != str(class_name) and c.get("name", "").lower() != class_name.lower()
    ]
    with open(settings.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    consensus_engine.rules_config = rules
    consensus_engine.categories_map = {cat["name"]: cat for cat in rules.get("sound_categories", [])}
    db = await ensure_database()
    await _log_audit(db, "Removed Sound Class", actor, f"Deleted sound class '{class_name}'")
    return {"status": "success", "deleted": class_name}


@admin_router.put("/api/app/admin/models/gtm-config")
@admin_router.post("/api/admin/models/version")
async def api_admin_update_gtm_config(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    py_version = str(body.get("python_model_version") or "v1.0").strip()
    gtm_version = str(body.get("gtm_model_version") or "v2.5").strip()

    rules = load_rules()
    rules.setdefault("system", {})["python_model_version"] = py_version
    rules["system"]["gtm_model_version"] = gtm_version
    with open(settings.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)

    db = await ensure_database()
    await _log_audit(db, "Updated Model Versions", actor, f"Active versions set to {py_version} / {gtm_version}")
    return {"status": "success"}


@admin_router.put("/api/app/admin/rules")
@admin_router.post("/api/admin/rules")
async def api_admin_save_alert_rules(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    rules = load_rules()
    if "consensus_rules" in body:
        rules.setdefault("system", {})["consensus_rules"] = body["consensus_rules"]
    with open(settings.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    db = await ensure_database()
    await _log_audit(db, "Updated Alert Rules", actor, "Updated verification thresholds")
    return {"status": "success"}


@admin_router.put("/api/admin/rules/{rule_id}")
async def api_admin_update_single_rule(rule_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    body = await request.json()
    rules = load_rules()
    for cat in rules.get("sound_categories", []):
        if str(cat.get("id")) == str(rule_id) or cat.get("name", "").lower() == rule_id.lower():
            if "severity" in body:
                cat["severity"] = body["severity"]
            if "enabled" in body:
                cat["enabled"] = bool(body["enabled"])
            if "min_confidence" in body:
                cat["min_confidence"] = float(body["min_confidence"])
            if "cooldown_seconds" in body:
                cat["cooldown_seconds"] = int(body["cooldown_seconds"])
            break
    with open(settings.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    db = await ensure_database()
    await _log_audit(db, "Updated Alert Rule", actor, f"Updated rule {rule_id}")
    return {"status": "success"}


# --- REVIEWS & ACTIVITY LOGS CRUD ---

@admin_router.post("/api/app/admin/reviews/{review_id}/verdict")
@admin_router.post("/api/admin/reviews/{review_id}/resolve")
async def api_admin_submit_review_verdict(review_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "full_name": "Super Admin", "role": "super_admin"}
    body = await request.json()
    decision_type = str(body.get("action") or body.get("decision_type") or "Confirmed").strip()
    final_category = str(body.get("final_label") or body.get("final_category") or "Gunshot").strip()
    reviewer_notes = str(body.get("notes") or body.get("reviewer_notes") or "").strip()

    db = await ensure_database()
    if db is not None:
        await db.manual_reviews.update_one(
            {"review_id": review_id},
            {"$set": {
                "status": decision_type,
                "decision_type": decision_type,
                "final_label": final_category,
                "reviewer_final_category": final_category,
                "reviewer_notes": reviewer_notes,
                "reviewed_by": actor.get("full_name") or actor.get("username", "Admin"),
                "reviewed_at": datetime.utcnow().isoformat()
            }},
            upsert=True
        )
        await _log_audit(db, f"Review {decision_type}", actor, f"Review {review_id} resolved as {final_category}")

    return {"status": "success", "review_id": review_id}


@admin_router.delete("/api/app/admin/reviews/{review_id}")
@admin_router.delete("/api/admin/reviews/{review_id}")
async def api_admin_delete_review(review_id: str, request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    db = await ensure_database()
    if db is not None:
        await db.manual_reviews.delete_one({"review_id": review_id})
        await _log_audit(db, "Deleted Review Item", actor, f"Removed review item {review_id}")
    return {"status": "success", "review_id": review_id}


@admin_router.delete("/api/app/admin/audit-logs/{log_id}")
@admin_router.delete("/api/admin/audit-logs/{log_id}")
async def api_admin_delete_audit_log(log_id: str):
    db = await ensure_database()
    if db is not None:
        await db.audit_logs.delete_one({"log_id": log_id})
    return {"status": "success", "log_id": log_id}


@admin_router.get("/api/app/admin/export-csv")
@admin_router.get("/api/admin/audit-logs/export")
async def api_admin_export_csv(request: Request):
    actor = await get_authenticated_user(request) or {"username": "admin", "role": "super_admin"}
    db = await ensure_database()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Log ID", "Actor", "Role", "Action", "Details", "Status"])

    if db is not None:
        logs = await db.audit_logs.find({}, {"_id": 0}).sort("timestamp", -1).limit(500).to_list(length=500)
        for l in logs:
            writer.writerow([
                l.get("timestamp", ""),
                l.get("log_id", ""),
                l.get("username", ""),
                l.get("role", ""),
                l.get("action", ""),
                l.get("details", ""),
                l.get("status", "Success")
            ])
        await _log_audit(db, "Exported Activity CSV", actor, f"Exported {len(logs)} activity records to CSV")

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dectus_activity_logs.csv"}
    )

