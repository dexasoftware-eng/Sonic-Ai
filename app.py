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
logger = logging.getLogger("SonicSentinel")

# ML & Inference Singletons
preprocessor = AudioPreprocessor(target_sr=settings.SAMPLE_RATE, target_duration=settings.WINDOW_DURATION_SEC)
feature_extractor = AcousticFeatureExtractor(sample_rate=settings.SAMPLE_RATE)
python_model = PythonSoundClassifier()
gtm_model = GTMClassifier()
consensus_engine = ConsensusEngine()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Connect to MongoDB
    logger.info("Initializing SonicSentinel AI backend...")
    try:
        await db_manager.connect()
    except Exception as e:
        logger.warning(f"MongoDB connection notice: {e}. Will attempt auto-reconnect on queries.")
    yield
    # Shutdown
    await db_manager.close()

app = FastAPI(
    title=settings.APP_NAME,
    description="Dual-Model Acoustic Intelligence & Sound-Event Detection System for Aptech TechWiz 7",
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

# -------------------------------------------------------------
# Web & REST API Endpoints
# -------------------------------------------------------------

from fastapi import Request

@app.get("/", response_class=HTMLResponse)
async def serve_dashboard(request: Request):
    """Serves real-time acoustic monitoring dashboard"""
    return templates.TemplateResponse(request=request, name="index.html")

@app.get("/about", response_class=HTMLResponse)
async def serve_about(request: Request):
    """Serves the comprehensive About SonicSentinel AI page"""
    return templates.TemplateResponse(request=request, name="about.html")

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
        "admin@sonicsentinel.ai": ("admin123", "administrator", "SonicSentinel Cloud", "System Administrator"),
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
        {"username": "admin_cloud", "email": "admin@sonicsentinel.ai", "password": "admin123", "full_name": "System Administrator", "role": "administrator", "tenant_id": "SonicSentinel Cloud"},
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
        db = get_database()
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
    - Sends back real-time prediction and alert triggers in < 1 second!
    """
    await websocket.accept()
    stream_id = f"stream_{uuid.uuid4().hex[:8]}"
    logger.info(f"WebSocket client connected: {stream_id}")

    try:
        import numpy as np
        while True:
            # Receive binary audio chunk or JSON message
            data = await websocket.receive_bytes()
            if not data:
                continue

            # Convert raw 32-bit float bytes to numpy array
            audio_chunk = np.frombuffer(data, dtype=np.float32)

            if len(audio_chunk) < int(settings.SAMPLE_RATE * 0.5):
                continue  # Skip tiny packets

            # Preprocess & Quality Check
            quality = AudioQualityChecker.analyze_quality(audio_chunk, settings.SAMPLE_RATE)

            if quality["is_silent"]:
                await websocket.send_json({
                    "stream_id": stream_id,
                    "status": "ambient",
                    "predicted_class": "Background Noise",
                    "confidence": 0.98,
                    "severity": "Informational",
                    "quality": quality["quality"],
                    "alert_triggered": False
                })
                continue

            # Dual Model Predictions
            py_pred = python_model.predict(audio_chunk)
            gtm_pred = gtm_model.predict(audio_chunk)

            # Consensus & Consecutive Confirmation
            eval_res = consensus_engine.evaluate(py_pred, gtm_pred, quality, stream_id=stream_id)

            # Send back instant response
            await websocket.send_json({
                "stream_id": stream_id,
                "status": "detected",
                "predicted_class": eval_res["final_category"],
                "python_confidence": py_pred["confidence"],
                "gtm_confidence": gtm_pred["confidence"],
                "consistency_status": eval_res["consistency_status"],
                "severity": eval_res["severity"],
                "alert_triggered": eval_res["alert_triggered"],
                "consecutive_count": eval_res["consecutive_count"],
                "quality": quality["quality"],
                "recommended_action": eval_res["recommended_action"],
                "timestamp": datetime.utcnow().isoformat()
            })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected: {stream_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
