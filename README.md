# 🛡️ SonicSentinel AI — Enterprise Multi-Tenant Acoustic Intelligence SaaS
### Aptech TechWiz 7 — NextWave AI and ML Category

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-Modern%20Async-teal.svg)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%20Cloud-green.svg)](https://www.mongodb.com/)
[![Librosa](https://img.shields.io/badge/Audio-Librosa%20DSP-orange.svg)](https://librosa.org/)
[![Architecture](https://img.shields.io/badge/Architecture-Multi--Tenant%20B2B%20SaaS-purple.svg)](https://github.com/)

SonicSentinel AI is an enterprise-grade, multi-tenant B2B acoustic intelligence platform. It ingests audio feeds from distributed facility microphones and uploaded recordings, evaluates acoustic signatures using an independent **Dual-AI Verification Engine** (Custom Python Deep Learning Model + Google Teachable Machine), and delivers tenant-isolated tactical security alerts and predictive industrial maintenance telemetry in real time.

---

## 🌟 SaaS Product Architecture

SonicSentinel AI bridges the gap between smart city public security and industrial machine monitoring through a multi-tenant cloud architecture:

```
                                [ SonicSentinel Cloud Platform ]
                                               │
               ┌───────────────────────────────┴───────────────────────────────┐
               ▼                                                               ▼
   [ Tenant: Metro Transit Police ]                                [ Tenant: Indus Heavy Industries ]
   - Public Safety & Threat Detection                              - Predictive Machinery Maintenance
   - Audio Feeds: Station Mics, Public Perimeters                   - Audio Feeds: Motor Turbines, Compressors
   - Monitored Events: Gunshots, Screams, Glass                     - Monitored Events: Bearing Faults, Cavitation
   - Dedicated SOC Operators & Dispatchers                          - Dedicated Plant Engineers & Technicians
```

### 1. Unified Multi-Tenant Data Isolation
* Every audio stream, detection event, prediction, alert, and review is tagged with a unique `tenant_id`.
* Strict tenant isolation at the database layer (MongoDB Atlas Cloud) guarantees data privacy and compliance.
* Tenant Admins configure custom sensitivity thresholds, alert rules, and sensor deployments per facility.

### 2. Dual-AI Consensus & Cross-Verification (Core Requirement)
* **Model 1: Custom Python Deep Learning Classifier:**
  * Trained on comprehensive acoustic features (MFCCs, Mel-Spectrograms, Chroma, Spectral Centroid, ZCR, RMS energy).
  * 2D-CNN / ResNet architecture targeting ≥85% test accuracy and ≥0.80 Macro F1-score.
* **Model 2: Google Teachable Machine (GTM) Audio Classifier:**
  * Independently trained audio classification model using the exact same stratified dataset split.
* **Consensus & Dispute Engine:**
  * Calculates `|Python_Confidence - GTM_Confidence|` and top-two margin.
  * Evaluates Consistency Status (`Acceptable Match`, `Weak Match`, `Model Disagreement`, `Uncertain Result`).
  * Enforces consecutive-window confirmation for critical life-safety hazards.
  * Automatically routes model disagreements and low-confidence audio to the **Manual Review Queue**.

---

## 🎯 10 Mandatory Sound Event Classes & Extended Registry

SonicSentinel AI supports the mandatory SRS classes plus dynamic custom categories:

| ID | Sound Category | Target Sector | Default Severity | Automated Action Protocol |
|---|---|---|---|---|
| 1 | **Machinery Fault** | Industrial Plants | High | Schedule mechanical inspection for bearing/motor fault |
| 2 | **Glass Breaking** | Commercial & Security | High | Perimeter alert & camera auto-pan to sector |
| 3 | **Alarm or Siren** | Facilities & Smart Cities | High | Emergency evacuation / emergency service alert |
| 4 | **Vehicle Horn** | Logistics & Transit | Low | Environmental noise & traffic logging |
| 5 | **Animal Sound** | Residential & Perimeters | Low | Context logging for perimeter activity |
| 6 | **Gunshot** | Police & Tactical Security | **Critical** | Immediate facility lockdown & police notification |
| 7 | **Panic Scream** | Public Safety & Health | **Critical** | Rapid response guard & medical team dispatch |
| 8 | **Aggression / Violence** | Campuses & Public Venues | High / Critical | Security patrol deployment to de-escalate confrontation |
| 9 | **Person Asking for Help** | Hospitals & Facilities | **Critical** | Distress responder dispatch ("Help me", "Emergency") |
| 10 | **Background Noise** | Ambient Baseline | Informational | Ambient filter baseline (HVAC, wind, rain) |

* **Extended Dynamic Categories:** Drone Sound, Fireworks, Explosion, Drilling/Grinder, Vehicle Backfire, Door Impact, and custom user-defined acoustic classes created via the Admin Registry.

---

## 👥 Role-Based Access Control (RBAC) & Workspaces

The platform routes authenticated users to dedicated, clutter-free workspaces:

1. **Platform Super-Admin:** Global tenant management, multi-organization quotas, platform health telemetry, and global AI model version tracking.
2. **Tenant Administrator (`/app/admin`):** Facility sensor management, custom alert threshold sliders, category registry, user access control, and compliance audit trail.
3. **Security Operator (`/app/security`):** Tactical Security Operations Center (SOC) dashboard. High-priority threat radar, instant audio buzzer, and 1-click alert response (`Acknowledge`, `Dispatch Unit`, `Dismiss`).
4. **Maintenance Engineer (`/app/maintenance`):** Industrial machinery health telemetry, acoustic vibration spectrograms, bearing wear trendlines, and work order generation.
5. **Audio Forensic Reviewer (`/app/reviewer`):** Human-in-the-loop forensic studio. Interactive scrubbable waveform audio player, dual-model comparison breakdown, and decision override tool with required forensic commentary.
6. **Normal User / Resident (`/app/user`):** Audio file upload analyzer, personal microphone test sandbox, and basic ambient noise monitoring.

---

## 📁 Repository Directory Structure (Modular Enterprise Layout)

```text
SonicSentinel-AI/
├── src/                         # Core AI, Audio Processing & Backend Engine
│   ├── audio/                   # Preprocessing, quality validation, feature extraction, augmentation
│   │   ├── validator.py         # Format, size, and duration validation
│   │   ├── quality_checker.py   # Silence detection (RMS), clipping, SNR health check
│   │   ├── preprocessor.py      # Resampling to 16kHz mono & 2.0s window segmentation
│   │   └── extractor.py         # MFCCs, Mel-Spectrogram, Chroma, Spectral moments, ZCR, RMS
│   ├── models/                  # Native Python ML/DL + Google Teachable Machine inference
│   │   ├── model_pipeline.py    # Python acoustic feature classifier & trained model loader
│   │   ├── gtm_inference.py     # Independent GTM Teachable Machine audio model loader
│   │   ├── saved_models/        # Serialized CNN / ML weights (classifier.joblib)
│   │   └── gtm_files/           # Exported GTM model weights and metadata.json
│   ├── consensus/               # Dual-AI Decision & Alerting Engine
│   │   └── consensus_engine.py  # Model agreement, confidence gap, window confirmation, review routing
│   └── database/                # Persistence & Security Layer
│       ├── mongodb.py           # Async Motor connection with Atlas cloud & local fallback
│       ├── schemas.py           # Multi-tenant Pydantic models with tenant_id isolation
│       └── security.py          # PBKDF2-HMAC password hashing & HMAC signed session tokens
├── static/                      # Frontend UI assets (Web Audio API waveform visualizer, CSS)
├── templates/                   # Frontend dashboard (Jinja2 index.html with 5-persona switcher)
├── config/                      # Alert thresholds, 10 mandatory categories (rules.json, settings.py)
├── data/                        # Audio datasets & metadata
├── notebooks/                   # Google Colab GPU training & model comparison notebooks
├── sample_audio/                # Reference WAV clips for all 10 sound categories & edge cases
├── tests/                       # Pytest automated test suite (15 unit & integration tests)
├── reports/                     # Model comparison reports & evaluation artifacts
├── app.py                       # Main FastAPI application server & WebSocket engine
├── requirements.txt             # Pinned production dependencies
├── AI_USAGE.md                  # Aptech TechWiz competition integrity declaration
└── README.md
```


---

## 🚀 Installation & Quickstart

### 1. Prerequisites
* Python 3.10+
* MongoDB Atlas Cloud connection string (or local MongoDB)
* Modern web browser (Chrome, Edge, Firefox)

### 2. Setup Isolated Environment
```powershell
# Clone the repository
git clone <repo-url>
cd SonicAi

# Activate virtual environment
.\.venv\Scripts\Activate.ps1

# Install pinned dependencies
pip install -r requirements.txt
```

### 3. Configure Credentials
Copy `.env.example` to `.env` and set your MongoDB Cloud URI:
```env
MONGODB_URI=mongodb+srv://dexasoftware_db_user:RLSz3kQb9vlFGD9I@cluster0.909zcsz.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=sonic_sentinel_db
```

### 4. Run Development Server
```powershell
python -m uvicorn app:app --reload --host 0.0.0.0 --port 8000
```
* **SaaS Web Application:** [http://localhost:8000](http://localhost:8000)
* **Interactive API Documentation:** [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Automated Testing
```powershell
python -m pytest tests/ -v
```

---

## 📜 Competition Compliance & Integrity
* **Theme:** AcousticX Intelligence
* **Category:** NextWave AI and ML
* **Organizer:** Aptech TechWiz 7
* **Compliance:** Fully compliant with SRS Section 1.8 (Anti-Shortcut rules). No external generative-AI APIs are invoked during sound classification. All detections are computed natively via local models.
