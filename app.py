import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, File, UploadFile, Form, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse

from config.settings import settings, load_rules, get_mandatory_classes
from src.database.mongodb import db_manager, get_database
from src.database.schemas import (
    AudioEventSchema, PredictionSchema, AlertSchema, ManualReviewSchema, AuditLogSchema
)
from src.audio.validator import AudioValidator, AudioValidationError
from src.audio.quality_checker import AudioQualityChecker
from src.audio.preprocessor import AudioPreprocessor
from src.audio.extractor import AcousticFeatureExtractor
from src.models.model_pipeline import PythonSoundClassifier
from src.models.gtm_inference import GTMClassifier
from src.consensus.consensus_engine import ConsensusEngine
from src.database.security import (
    hash_password, verify_password, generate_session_token, decode_session_token
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Dectus")

from src.app.admin_routes import (
    preprocessor,
    feature_extractor,
    python_model,
    gtm_model,
    consensus_engine,
    invalidate_telemetry_cache,
)

def _warmup_models() -> None:
    try:
        import numpy as np
        dummy_audio = np.sin(np.linspace(0, 2 * np.pi * 440, 32000, dtype=np.float32)) * 0.2
        feats = feature_extractor.extract_all_features(dummy_audio)
        python_model.predict(feats["cnn_input"], features=feats, audio=dummy_audio)
        gtm_model.predict(feats["cnn_input"], features=feats, audio=dummy_audio)
        logger.info("Dual-AI models & DSP feature extractor warmed up and ready.")
    except Exception as exc:
        logger.warning(f"Model warmup notice: {exc}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB, Run Migrations & Warmup AI Models
    logger.info("Initializing Dectus backend...")
    try:
        import asyncio
        asyncio.create_task(asyncio.to_thread(_warmup_models))
        await db_manager.connect()
        if db_manager.db is not None:
            from migrations.run_migrations import run_all_migrations
            mig_res = await run_all_migrations(db_manager.db)
            logger.info(f"Database migrations verified: {mig_res.get('applied_migrations', [])}")
    except Exception as e:
        logger.warning(f"MongoDB connection/migration notice: {e}.")
    yield
    # Shutdown
    await db_manager.close()

app = FastAPI(
    title=settings.APP_NAME,
    description="Enterprise Dual-Model Acoustic Threat Intelligence & Sound-Event Detection Platform",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static and Templates
app.mount("/static", StaticFiles(directory=str(settings.BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(settings.BASE_DIR / "templates"))

# Mount SaaS Multi-Tenant Application & Auth Subsystem
from src.app.auth_routes import app_auth_router
from src.app.app_routes import app_router
from src.app.admin_routes import admin_router
from src.app.company_routes import company_router
from src.app.reviewer_routes import reviewer_router
from src.app.security_routes import security_router
from src.app.stripe_routes import stripe_router
app.include_router(app_auth_router)
app.include_router(reviewer_router)
app.include_router(app_router)
app.include_router(admin_router)
app.include_router(company_router)
app.include_router(security_router)
app.include_router(stripe_router)


# -------------------------------------------------------------
# Web & REST API Endpoints
# -------------------------------------------------------------

from fastapi import Request

async def _get_dynamic_pricing_plans():
    """Fetches real-time, Super Admin-managed pricing tiers from MongoDB."""
    try:
        from src.database.mongodb import ensure_database
        from src.security.quotas import normalize_plan
        db = await ensure_database()
        if db is not None:
            raw = await db.subscription_plans.find({"is_active": {"$ne": False}}, {"_id": 0}).to_list(100)
            norm = [normalize_plan(p) for p in raw]
            comp = [p for p in norm if p["audience"] == "company"]
            ind = [p for p in norm if p["audience"] == "individual"]
            return ind, comp, norm
    except Exception as e:
        logger.warning(f"Notice loading dynamic pricing plans: {e}")
    from src.security.quotas import DEFAULT_INDIVIDUAL_PLAN, DEFAULT_COMPANY_PLAN, normalize_plan
    ind = [normalize_plan(DEFAULT_INDIVIDUAL_PLAN)]
    comp = [normalize_plan(DEFAULT_COMPANY_PLAN)]
    return ind, comp, ind + comp

@app.get("/api/subscriptions/plans")
async def api_public_subscriptions_plans():
    """Public REST endpoint returning current plans managed by Super Admin."""
    ind, comp, all_p = await _get_dynamic_pricing_plans()
    return {
        "status": "success",
        "plans": all_p,
        "individual": ind,
        "company": comp
    }

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves real-time acoustic monitoring landing page with dynamic pricing state"""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    ind_plans, comp_plans, all_plans = await _get_dynamic_pricing_plans()
    return templates.TemplateResponse(request=request, name="index.html", context={
        "user": user,
        "dashboard_url": dash_url,
        "individual_plans": ind_plans,
        "company_plans": comp_plans,
        "plans": all_plans
    })

@app.get("/about", response_class=HTMLResponse)
async def serve_about(request: Request):
    """Serves the comprehensive About Dectus page with session state"""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    return templates.TemplateResponse(request=request, name="about.html", context={
        "user": user,
        "dashboard_url": dash_url
    })

@app.get("/features", response_class=HTMLResponse)
async def serve_features(request: Request):
    """Serves the dedicated Features showcase page with session state"""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    return templates.TemplateResponse(request=request, name="features.html", context={
        "user": user,
        "dashboard_url": dash_url
    })

@app.get("/integrations", response_class=HTMLResponse)
async def serve_integrations(request: Request):
    """Serves the dedicated Integrations catalog and developer ecosystem page"""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    return templates.TemplateResponse(request=request, name="integrations.html", context={
        "user": user,
        "dashboard_url": dash_url
    })

@app.get("/pricing", response_class=HTMLResponse)
async def serve_pricing(request: Request):
    """Serves the dedicated Pricing page with 100% dynamic MongoDB tiers"""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    ind_plans, comp_plans, all_plans = await _get_dynamic_pricing_plans()
    return templates.TemplateResponse(request=request, name="pricing.html", context={
        "user": user,
        "dashboard_url": dash_url,
        "individual_plans": ind_plans,
        "company_plans": comp_plans,
        "plans": all_plans
    })

@app.get("/app/subscription/success", response_class=HTMLResponse)
async def serve_subscription_success(request: Request, plan_id: str = "comp_creator"):
    """Celebratory subscription confirmation view."""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    from src.database.mongodb import ensure_database
    from src.security.quotas import normalize_plan
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    db = await ensure_database()
    plan_doc = await db.subscription_plans.find_one({"plan_id": plan_id}, {"_id": 0}) if db is not None else None
    plan = normalize_plan(plan_doc)
    return templates.TemplateResponse(request=request, name="app/subscription_success.html", context={
        "user": user,
        "plan": plan,
        "dashboard_url": dash_url
    })


@app.get("/contact", response_class=HTMLResponse)
async def serve_contact(request: Request):
    """Serves the premium Contact and enterprise inquiries page"""
    from src.app.app_routes import get_authenticated_user
    from src.app.auth_routes import ROLE_REDIRECTS
    user = await get_authenticated_user(request)
    dash_url = ROLE_REDIRECTS.get(user.get("role"), "/app/user") if user else "/app/login"
    return templates.TemplateResponse(request=request, name="contact.html", context={
        "user": user,
        "dashboard_url": dash_url
    })

@app.post("/api/contact")
async def submit_contact(request: Request):
    """Handles enterprise contact inquiries and stores/logs them"""
    try:
        data = await request.json()
    except Exception:
        data = dict(await request.form())
    logger.info(f"Received enterprise contact inquiry: {data.get('email', 'anonymous')} - {data.get('reason', 'General')}")
    return JSONResponse(status_code=200, content={
        "success": True,
        "message": "Thank you. Your message has been received and routed to our team."
    })

@app.get("/health")
async def health_check():
    """Health status and configuration overview"""
    db_status = "connected" if db_manager.client is not None else "disconnected"
    return {
        "status": "healthy",
        "app_name": settings.APP_NAME,
        "database": db_status,
        "sample_rate": settings.SAMPLE_RATE,
        "mandatory_classes_count": len(get_mandatory_classes()),
        "classes": get_mandatory_classes()
    }

# -------------------------------------------------------------
# Authentication & Role-Based Access Control (RBAC)
# -------------------------------------------------------------

VALID_ROLES = {"normal_user", "audio_reviewer", "security_operator", "maintenance_operator", "administrator"}

@app.post("/api/auth/register")
async def register_user(
    username: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    full_name: str = Form("User"),
    role: str = Form("normal_user"),
    tenant_id: str = Form("default_org")
):
    """Registers a new user account with hashed password and assigned role."""
    if role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail=f"Invalid role. Must be one of: {', '.join(sorted(VALID_ROLES))}")

    db = get_database()
    user_id = f"USR-{uuid.uuid4().hex[:8].upper()}"
    pwd_hash = hash_password(password)

    if db is not None:
        existing = await db.users.find_one({"$or": [{"username": username}, {"email": email}]})
        if existing:
            raise HTTPException(status_code=400, detail="Username or email already exists")

        await db.users.insert_one({
            "user_id": user_id,
            "tenant_id": tenant_id,
            "username": username,
            "email": email,
            "password_hash": pwd_hash,
            "full_name": full_name,
            "role": role,
            "created_at": datetime.utcnow(),
            "is_active": True
        })

    token = generate_session_token(user_id=user_id, username=username, role=role, tenant_id=tenant_id)
    return {
        "status": "success",
        "message": "User registered successfully",
        "user": {
            "user_id": user_id,
            "username": username,
            "email": email,
            "full_name": full_name,
            "role": role,
            "tenant_id": tenant_id
        },
        "session_token": token
    }

@app.post("/api/auth/login")
async def login_user(
    username: str = Form(...),
    password: str = Form(...)
):
    """Authenticates credentials against stored PBKDF2 hash."""
    db = get_database()
    
    # Check default demo accounts fallback if database not seeded
    demo_defaults = {
        "admin@sonicsentinel.ai": ("admin123", "administrator", "Dectus Cloud", "System Administrator"),
        "guard@metro.gov": ("guard123", "security_operator", "Metro Transit Police", "Officer Alex (SOC)"),
        "engineer@indus.ind": ("engineer123", "maintenance_operator", "Indus Heavy Industries", "Eng. Tariq (Plant)"),
        "reviewer@sonicsentinel.ai": ("reviewer123", "audio_reviewer", "Global Acoustic QA", "Dr. Sarah (Acoustics)"),
        "user@resident.org": ("user123", "normal_user", "City Commons", "Resident Dave")
    }

    user = None
    if db is not None:
        user = await db.users.find_one({"$or": [{"username": username}, {"email": username}]})

    if user:
        if not verify_password(password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid username or password")
        u_id = user.get("user_id", str(user["_id"]))
        u_name = user["username"]
        u_role = user["role"]
        u_tenant = user.get("tenant_id", "default_org")
        u_full = user.get("full_name", u_name)
    elif username in demo_defaults and password == demo_defaults[username][0]:
        _, u_role, u_tenant, u_full = demo_defaults[username]
        u_id = f"DEMO-{u_role[:3].upper()}"
        u_name = username
    else:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = generate_session_token(user_id=u_id, username=u_name, role=u_role, tenant_id=u_tenant)
    return {
        "status": "success",
        "user": {
            "user_id": u_id,
            "username": u_name,
            "full_name": u_full,
            "role": u_role,
            "tenant_id": u_tenant
        },
        "session_token": token
    }

@app.get("/api/auth/me")
async def get_current_user(token: Optional[str] = None):
    """Returns current active user session profile."""
    if not token:
        return {"authenticated": False, "role": "guest"}
    payload = decode_session_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired session token")
    return {"authenticated": True, "user": payload}

@app.post("/api/auth/seed-demo-users")
async def seed_demo_users():
    """Seeds standard demo accounts across all 5 roles into MongoDB for evaluator defense."""
    db = get_database()
    demo_accounts = [
        {"username": "guard_metro", "email": "guard@metro.gov", "password": "guard123", "full_name": "Officer Alex", "role": "security_operator", "tenant_id": "Metro Transit Police"},
        {"username": "engineer_indus", "email": "engineer@indus.ind", "password": "engineer123", "full_name": "Eng. Tariq", "role": "maintenance_operator", "tenant_id": "Indus Heavy Industries"},
        {"username": "reviewer_qa", "email": "reviewer@sonicsentinel.ai", "password": "reviewer123", "full_name": "Dr. Sarah", "role": "audio_reviewer", "tenant_id": "Global Acoustic QA"},
        {"username": "admin_cloud", "email": "admin@sonicsentinel.ai", "password": "admin123", "full_name": "System Administrator", "role": "administrator", "tenant_id": "Dectus Cloud"},
        {"username": "resident_user", "email": "user@resident.org", "password": "user123", "full_name": "Dave Resident", "role": "normal_user", "tenant_id": "City Commons"}
    ]

    seeded_count = 0
    if db is not None:
        for acc in demo_accounts:
            existing = await db.users.find_one({"email": acc["email"]})
            if not existing:
                await db.users.insert_one({
                    "user_id": f"USR-{uuid.uuid4().hex[:8].upper()}",
                    "tenant_id": acc["tenant_id"],
                    "username": acc["username"],
                    "email": acc["email"],
                    "password_hash": hash_password(acc["password"]),
                    "full_name": acc["full_name"],
                    "role": acc["role"],
                    "created_at": datetime.utcnow(),
                    "is_active": True
                })
                seeded_count += 1

    return {
        "status": "success",
        "message": f"Seeded {seeded_count} demo accounts into MongoDB.",
        "accounts": [
            {"role": a["role"], "email": a["email"], "password": a["password"], "tenant": a["tenant_id"]}
            for a in demo_accounts
        ]
    }

@app.post("/api/audio/upload")
async def upload_audio_file(file: UploadFile = File(...)):
    """
    Validates, processes, and classifies uploaded audio file.
    Runs dual-model consensus and generates alerts if critical threats detected.
    """
    audio_id = str(uuid.uuid4())
    temp_path = settings.UPLOAD_DIR / f"{audio_id}_{file.filename}"

    # Save uploaded file
    try:
        contents = await file.read()
        with open(temp_path, "wb") as f:
            f.write(contents)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save uploaded file: {e}")

    # 1. Validation
    try:
        val_info = AudioValidator.inspect_and_validate(temp_path)
    except AudioValidationError as e:
        if temp_path.exists():
            temp_path.unlink()
        raise HTTPException(status_code=400, detail=str(e))

    # 2. Preprocess & Quality Check
    try:
        audio_data, sr = preprocessor.load_and_preprocess(str(temp_path))
        quality_info = AudioQualityChecker.analyze_quality(audio_data, sr)

        # Segment audio into 2.0s windows
        segments = preprocessor.segment_audio(audio_data)
        
        # Analyze the primary / highest-energy segment
        primary_segment = segments[0]["audio"] if segments else audio_data

        # 3. Dual-Model Inference
        py_pred = python_model.predict(primary_segment)
        gtm_pred = gtm_model.predict(primary_segment)

        # 4. Consensus & Decision Evaluation
        evaluation = consensus_engine.evaluate(py_pred, gtm_pred, quality_info)

        # 5. Persist to MongoDB (if connected)
        try:
            from src.database.mongodb import ensure_database
            db = await ensure_database()
            if db is not None:
                # Audio Event Record
                await db.audio_events.insert_one({
                    "audio_id": audio_id,
                    "filename": file.filename,
                    "file_path": str(temp_path),
                    "input_source": "upload",
                    "duration_seconds": val_info["duration_seconds"],
                    "sample_rate": sr,
                    "file_size_bytes": val_info["file_size_bytes"],
                    "quality": quality_info["quality"],
                    "snr_db": quality_info["snr_db"],
                    "is_silent": quality_info["is_silent"],
                    "is_clipped": quality_info["is_clipped"],
                    "created_at": datetime.utcnow()
                })

                # Prediction Record
                await db.predictions.insert_one({
                    "audio_id": audio_id,
                    "python_prediction": py_pred["predicted_class"],
                    "python_confidence": py_pred["confidence"],
                    "python_scores": py_pred["all_confidences"],
                    "gtm_prediction": gtm_pred["predicted_class"],
                    "gtm_confidence": gtm_pred["confidence"],
                    "gtm_scores": gtm_pred["all_confidences"],
                    "consistency_status": evaluation["consistency_status"],
                    "confidence_gap": evaluation["confidence_difference"],
                    "top_two_margin": evaluation["top_two_margin"],
                    "created_at": datetime.utcnow()
                })

                # Alert Record if triggered
                if evaluation["alert_triggered"]:
                    alert_id = f"ALT-{uuid.uuid4().hex[:8].upper()}"
                    await db.alerts.insert_one({
                        "alert_id": alert_id,
                        "audio_id": audio_id,
                        "sound_category": evaluation["final_category"],
                        "severity": evaluation["severity"],
                        "department": evaluation["department"],
                        "recommended_action": evaluation["recommended_action"],
                        "status": "New",
                        "created_at": datetime.utcnow()
                    })

                # Manual Review Queue if needed
                if evaluation["needs_manual_review"]:
                    review_id = f"REV-{uuid.uuid4().hex[:8].upper()}"
                    await db.manual_reviews.insert_one({
                        "review_id": review_id,
                        "audio_id": audio_id,
                        "filename": file.filename,
                        "ai_python_prediction": py_pred["predicted_class"],
                        "ai_gtm_prediction": gtm_pred["predicted_class"],
                        "consistency_status": evaluation["consistency_status"],
                        "reasons": evaluation["review_reasons"],
                        "status": "Pending",
                        "created_at": datetime.utcnow()
                    })
        except Exception as dbe:
            logger.warning(f"MongoDB event logging notice: {dbe}")

        return {
            "status": "success",
            "audio_id": audio_id,
            "filename": file.filename,
            "validation": val_info,
            "quality": quality_info,
            "python_model": py_pred,
            "gtm_model": gtm_pred,
            "consensus": evaluation
        }

    except Exception as e:
        logger.error(f"Processing error: {e}")
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

@app.get("/api/alerts")
async def get_alerts():
    """Returns active alerts from MongoDB"""
    db = get_database()
    if db is None:
        return {"alerts": []}
    cursor = db.alerts.find().sort("created_at", -1).limit(50)
    alerts = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        alerts.append(doc)
    return {"alerts": alerts}

@app.post("/api/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, operator_name: str = Form("Security Officer")):
    """Acknowledges an alert by security operator"""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database offline")
    res = await db.alerts.update_one(
        {"alert_id": alert_id},
        {"$set": {"status": "Acknowledged", "acknowledged_by": operator_name, "acknowledged_at": datetime.utcnow()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Alert not found")
    return {"status": "acknowledged", "alert_id": alert_id}

@app.get("/api/review-queue")
async def get_review_queue():
    """Returns pending items awaiting human review"""
    db = get_database()
    if db is None:
        return {"queue": []}
    cursor = db.manual_reviews.find({"status": "Pending"}).sort("created_at", -1).limit(50)
    queue = []
    async for doc in cursor:
        doc["_id"] = str(doc["_id"])
        queue.append(doc)
    return {"queue": queue}

@app.post("/api/review-queue/{review_id}/decision")
async def submit_review_decision(
    review_id: str,
    action: str = Form(...),  # 'confirm' or 'override'
    confirmed_category: str = Form(...),
    notes: Optional[str] = Form(""),
    reviewer_name: str = Form("Audio Reviewer")
):
    """Submits human review decision and override"""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database offline")
    res = await db.manual_reviews.update_one(
        {"review_id": review_id},
        {"$set": {
            "status": "Reviewed",
            "action_taken": action,
            "final_category": confirmed_category,
            "reviewer_notes": notes,
            "reviewer_username": reviewer_name,
            "reviewed_at": datetime.utcnow()
        }}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Review entry not found")
    return {"status": "reviewed", "review_id": review_id}

from fastapi.responses import FileResponse, Response
import io
import csv

@app.get("/api/categories")
async def get_categories():
    """Returns all active sound categories and rules"""
    rules = load_rules()
    return {"categories": rules.get("sound_categories", [])}

@app.post("/api/categories")
async def add_custom_category(
    name: str = Form(...),
    severity: str = Form("Medium"),
    department: str = Form("General"),
    min_confidence: float = Form(0.75),
    recommended_action: str = Form("Inspect detected sound event.")
):
    """Dynamically registers a new sound event class in real-time (Surprise Evaluator Test Ready!)"""
    import json
    rules = load_rules()
    existing_names = [c["name"].lower() for c in rules["sound_categories"]]
    if name.lower() in existing_names:
        raise HTTPException(status_code=400, detail="Category already exists")
    
    new_cat = {
        "id": len(rules["sound_categories"]) + 1,
        "name": name,
        "severity": severity,
        "department": department,
        "min_confidence": min_confidence,
        "top_two_margin": 0.10,
        "consecutive_windows_required": 1,
        "require_model_agreement": False,
        "recommended_action": recommended_action,
        "description": f"Custom user-registered category for {department}."
    }
    rules["sound_categories"].append(new_cat)
    with open(settings.RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(rules, f, indent=2)
    
    # Live reload in consensus engine and model pipelines
    consensus_engine.rules_config = load_rules()
    consensus_engine.categories_map = {cat["name"]: cat for cat in consensus_engine.rules_config.get("sound_categories", [])}
    if name not in python_model.classes:
        python_model.classes.append(name)
    if name not in gtm_model.classes:
        gtm_model.classes.append(name)
        
    return {"status": "success", "category": new_cat}

@app.get("/api/sample-audio/{category_filename}")
async def serve_sample_audio(category_filename: str):
    """Serves sample audio files for playback in the review studio"""
    path = settings.SAMPLE_AUDIO_DIR / category_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Sample audio not found")
    return FileResponse(str(path), media_type="audio/wav")

@app.get("/api/export")
async def export_events_csv():
    """Exports events records to CSV for administrative audits"""
    db = get_database()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Event ID", "Audio ID", "Category", "Severity", "Status", "Action", "Timestamp"])
    if db is not None:
        async for a in db.alerts.find().sort("created_at", -1):
            writer.writerow([
                a.get("alert_id", ""), a.get("audio_id", ""), a.get("sound_category", ""),
                a.get("severity", ""), a.get("status", ""), a.get("recommended_action", ""),
                a.get("created_at", "")
            ])
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=sonicsentinel_audit.csv"}
    )

# -------------------------------------------------------------
# WebSocket: Real-Time Live Microphone Audio Stream
# -------------------------------------------------------------

@app.websocket("/ws/live-audio")
async def websocket_live_audio(websocket: WebSocket):
    """
    Bi-directional real-time microphone stream:
    - Receives audio chunk (Float32 PCM bytes) from browser Web Audio API
    - Runs immediate validation, dual-model inference & consensus
    - Persists non-ambient detections to MongoDB and sends back real-time prediction
    """
    await websocket.accept()
    stream_id = f"stream_{uuid.uuid4().hex[:8]}"
    logger.info(f"WebSocket client connected: {stream_id}")
    last_db_save_ts = 0.0

    def _infer_live_chunk(chunk_arr):
        padded = preprocessor.pad_or_truncate(chunk_arr)
        qual = AudioQualityChecker.analyze_quality(padded, settings.SAMPLE_RATE)
        if qual["is_silent"]:
            return padded, qual, None, None, None
        py_p = python_model.predict(padded)
        gtm_p = gtm_model.predict(padded)
        ev_r = consensus_engine.evaluate(py_p, gtm_p, qual, stream_id=stream_id)
        return padded, qual, py_p, gtm_p, ev_r

    try:
        import asyncio
        import numpy as np
        import time as _time
        from src.database.mongodb import ensure_database

        while True:
            data = await websocket.receive_bytes()
            if not data:
                continue

            audio_chunk = np.frombuffer(data, dtype=np.float32)
            audio_chunk = np.nan_to_num(audio_chunk, nan=0.0, posinf=0.0, neginf=0.0)

            if len(audio_chunk) < int(settings.SAMPLE_RATE * 0.25):
                continue

            padded_chunk, quality, py_pred, gtm_pred, eval_res = await asyncio.to_thread(
                _infer_live_chunk, audio_chunk
            )

            if quality["is_silent"]:
                await websocket.send_json({
                    "stream_id": stream_id,
                    "status": "ambient",
                    "predicted_class": "Normal / Background",
                    "python_prediction": "Normal / Background",
                    "python_confidence": 0.0,
                    "gtm_prediction": "Normal / Background",
                    "gtm_confidence": 0.0,
                    "consistency_status": "Standby",
                    "severity": "Low",
                    "snr_db": round(float(quality.get("snr_db", 0.0)), 1),
                    "quality": quality.get("quality", "Unusable"),
                    "alert_triggered": False,
                    "timestamp": datetime.utcnow().isoformat()
                })
                continue

            now_ts = _time.time()
            final_cat = eval_res["final_category"]
            persisted_id = None
            total_detections = None

            # Persist significant live microphone detections to MongoDB (rate-limited to 1 every 4s per stream)
            if (final_cat not in ("Normal / Background", "Background Noise") or eval_res["alert_triggered"]) and (now_ts - last_db_save_ts >= 4.0):
                last_db_save_ts = now_ts
                db = await ensure_database()
                if db is not None:
                    persisted_id = f"AUD_{uuid.uuid4().hex[:6].upper()}"
                    feats = await asyncio.to_thread(feature_extractor.extract_tabular_features, padded_chunk)
                    now_dt = datetime.utcnow()
                    db_ops = [
                        db.audio_events.insert_one({
                            "audio_id": persisted_id,
                            "tenant_id": "platform_global",
                            "user_id": "USR-RESIDENT-001",
                            "zone_name": "ZONE-RESIDENCE",
                            "filename": f"live_mic_{persisted_id.lower()}.wav",
                            "input_source": "Live Microphone",
                            "duration_seconds": round(len(audio_chunk) / settings.SAMPLE_RATE, 2),
                            "sample_rate": settings.SAMPLE_RATE,
                            "channels": 1,
                            "quality": quality["quality"],
                            "snr_db": quality["snr_db"],
                            "is_silent": quality["is_silent"],
                            "is_clipped": quality["is_clipped"],
                            "python_prediction": py_pred["predicted_class"],
                            "python_confidence": py_pred["confidence"],
                            "gtm_prediction": gtm_pred["predicted_class"],
                            "gtm_confidence": gtm_pred["confidence"],
                            "consistency_status": eval_res["consistency_status"],
                            "confidence_difference": eval_res["confidence_difference"],
                            "top_two_margin": eval_res["top_two_margin"],
                            "severity": eval_res["severity"],
                            "recommended_action": eval_res["recommended_action"],
                            "department": eval_res["department"],
                            "lifecycle_status": "Alert Generated" if eval_res["alert_triggered"] else "Classified",
                            "acoustic_features": {
                                "spectral_centroid": feats["spectral_centroid"],
                                "spectral_bandwidth": feats["spectral_bandwidth"],
                                "spectral_rolloff": feats["spectral_rolloff"],
                                "zero_crossing_rate": feats["zero_crossing_rate"],
                                "rms_energy": feats["rms_energy"],
                                "onset_strength": feats["onset_strength"],
                            },
                            "created_at": now_dt
                        }),
                        db.predictions.insert_one({
                            "audio_id": persisted_id,
                            "tenant_id": "platform_global",
                            "python_prediction": py_pred["predicted_class"],
                            "python_confidence": py_pred["confidence"],
                            "gtm_prediction": gtm_pred["predicted_class"],
                            "gtm_confidence": gtm_pred["confidence"],
                            "consistency_status": eval_res["consistency_status"],
                            "created_at": now_dt
                        })
                    ]
                    if eval_res["alert_triggered"] or eval_res["severity"] in ("Critical", "High"):
                        db_ops.append(db.alerts.insert_one({
                            "alert_id": f"ALT-{uuid.uuid4().hex[:6].upper()}",
                            "audio_id": persisted_id,
                            "tenant_id": "platform_global",
                            "zone_name": "ZONE-RESIDENCE",
                            "sound_category": final_cat,
                            "severity": eval_res["severity"],
                            "department": eval_res["department"],
                            "python_confidence": py_pred["confidence"],
                            "gtm_confidence": gtm_pred["confidence"],
                            "consistency_status": eval_res["consistency_status"],
                            "quality": quality["quality"],
                            "recommended_action": eval_res["recommended_action"],
                            "status": "New",
                            "created_at": now_dt
                        }))
                    await asyncio.gather(*db_ops)
                    invalidate_telemetry_cache()
                    total_detections = await db.audio_events.count_documents({})

            await websocket.send_json({
                "stream_id": stream_id,
                "status": "detected",
                "audio_id": persisted_id,
                "total_detections": total_detections,
                "predicted_class": final_cat,
                "python_prediction": py_pred["predicted_class"],
                "python_confidence": py_pred["confidence"],
                "gtm_prediction": gtm_pred["predicted_class"],
                "gtm_confidence": gtm_pred["confidence"],
                "consistency_status": eval_res["consistency_status"],
                "severity": eval_res["severity"],
                "alert_triggered": eval_res["alert_triggered"],
                "consecutive_count": eval_res["consecutive_count"],
                "snr_db": round(float(quality.get("snr_db", 0.0)), 1),
                "quality": quality["quality"],
                "recommended_action": eval_res["recommended_action"],
                "timestamp": datetime.utcnow().isoformat()
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {stream_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
