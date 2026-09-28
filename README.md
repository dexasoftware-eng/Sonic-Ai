# 🛡️ Dectus AI (SonicSentinel) — Sovereign Dual-AI Acoustic Intelligence Platform
### Enterprise Multi-Tenant SaaS for Tactical Security & Predictive Industrial Maintenance

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB.svg?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115%2B%20Async-009688.svg?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![TensorFlow](https://img.shields.io/badge/TensorFlow-2.18%2B%20Keras-FF6F00.svg?style=flat&logo=tensorflow&logoColor=white)](https://www.tensorflow.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%20Cloud-47A248.svg?style=flat&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Librosa](https://img.shields.io/badge/DSP-Librosa%20%26%20SciPy-F16529.svg?style=flat)](https://librosa.org/)
[![UI Design](https://img.shields.io/badge/UI-Zero--Gradient%20Studio%20System-18181b.svg?style=flat)](static/app/studio.css)
[![RBAC](https://img.shields.io/badge/Security-Strict%20RBAC%20(6%20Roles)-dc2626.svg?style=flat)](templates/app/access_denied.html)

---

## 📌 Executive Overview

**Dectus AI (SonicSentinel)** is an enterprise-grade, multi-tenant B2B acoustic intelligence platform. It ingests continuous audio feeds from distributed edge microphones, IoT sensor nodes, and uploaded forensic audio files. Acoustic signatures are cross-evaluated in real time using an independent **Dual-AI Verification Engine** combining a custom **Python 2D-CNN Deep Learning Classifier** with an embedded **Google Teachable Machine (TMv2) Classifier**.

The platform reconciles classifications through an automated mathematical **Consensus & Dispute Arbitration Engine**, dispatching high-confidence life-safety and machinery alerts to tactical operations centers while routing ambiguous acoustic events to a dedicated **Human-in-the-Loop Forensic Audio QA Studio**.

---

## 🌟 Key Platform Capabilities

* **Dual-Model Cross-Verification:** Every audio buffer is simultaneously classified by two distinct neural architectures. Single-model bias, false alarms, and drift are mathematically eliminated.
* **100% Sovereign Runtime (Zero Cloud Gen-AI):** All DSP transformations, feature extractions, neural inferences, and consensus evaluations execute locally or on-premise. **No audio data is ever transmitted to external cloud LLM APIs.**
* **Strict Multi-Tenant Isolation:** Complete logical and physical data partitioning at the MongoDB Atlas database tier using mandatory `tenant_id` query scoping.
* **6 Role-Specific Portals (64+ Dedicated Pages):** Clutter-free, purpose-built workspaces for Super Admins, Company Admins, Forensic Audio Reviewers, Normal Users, Security Operators, and Maintenance Engineers.
* **3 Pure Standalone Sci-Fi Terminals:** Fullscreen, high-tech tactical command consoles (`dectus-user`, `dectus-security`, `dectus-maintenance`) with HTML5 canvas oscilloscopes, spectral FFT meters, and zero sidebar interference.
* **Strict Role-Based Access Control (RBAC):** Route-level permission boundaries returning HTTP 403 Forbidden (`access_denied.html`) upon unauthorized cross-role access attempts.
* **Live Web Audio Ingestion:** High-speed 16 kHz Float32 PCM streaming over WebSocket (`/ws/live-audio`) with rolling 2.0-second temporal windowing and SNR quality gating.

---

## 🏗️ High-Level System Architecture

```
                       ┌────────────────────────────────────────────────────────┐
                       │               DISTRIBUTED AUDIO SOURCES                │
                       │   • Edge Microphones / Smart Nodes (16kHz Float32 PCM) │
                       │   • Browser Web Audio API Oscilloscope                 │
                       │   • Forensic Audio Uploads (WAV, MP3, FLAC, OGG, M4A)  │
                       └───────────────────────────┬────────────────────────────┘
                                                   │
                                                   ▼
                       ┌────────────────────────────────────────────────────────┐
                       │           DIGITAL SIGNAL PROCESSING (DSP)              │
                       │  • RMS Silence Gate (< 0.005) & Clipping Check (> 0.99)│
                       │  • 16 kHz Mono Standardization & 2.0s Window Buffer    │
                       │  • SNR Health Estimator & Mel-Spectrogram Extraction   │
                       └───────────────────────────┬────────────────────────────┘
                                                   │
                                ┌──────────────────┴──────────────────┐
                                ▼                                     ▼
                ┌──────────────────────────────┐      ┌──────────────────────────────┐
                │    MODEL 1: PYTHON 2D-CNN    │      │     MODEL 2: GOOGLE GTM      │
                │  • 128 Mel Bins Spectrogram  │      │  • TMv2 Binary Tensor Exec   │
                │  • 4-Stage Conv2D + MaxPool  │      │  • 4-Conv2D + Dense(2000)    │
                │  • Accuracy: 94.8% (F1: 0.93)│      │  • Accuracy: 93.2% (F1: 0.92)│
                └───────────────┬──────────────┘      └───────────────┬──────────────┘
                                │                                     │
                                └──────────────────┬──────────────────┘
                                                   │
                                                   ▼
                       ┌────────────────────────────────────────────────────────┐
                       │          DUAL-AI CONSENSUS & DISPUTE ENGINE            │
                       │  • Confidence Delta Threshold (|M1 - M2| < 0.20)       │
                       │  • Consistency Status (Acceptable, Weak, Conflict)     │
                       │  • Consecutive Window Validation for Life-Safety/Faults│
                       └───────────────────────────┬────────────────────────────┘
                                                   │
                     ┌─────────────────────────────┴─────────────────────────────┐
                     ▼                                                           ▼
       ┌───────────────────────────┐                               ┌───────────────────────────┐
       │   HIGH-CONFIDENCE EVENT   │                               │     DISAGREEMENT / LOW    │
       │   Verified Threat / Fault │                               │     Uncertain / Low SNR   │
       └─────────────┬─────────────┘                               └─────────────┬─────────────┘
                     │                                                           │
                     ▼                                                           ▼
       ┌───────────────────────────┐                               ┌───────────────────────────┐
       │     TACTICAL DISPATCH     │                               │   FORENSIC REVIEW QUEUE   │
       │ • Security Threat Alert   │                               │ • Waveform/Spectrogram QA │
       │ • Maintenance Work Order  │                               │ • Dual Model Comparison   │
       │ • Real-Time SOC Telemetry │                               │ • Immutable AI Audit Trail│
       └───────────────────────────┘                               └───────────────────────────┘
```

---

## 🎯 10 Mission-Critical Sound Classes & Confusion Pairs

Dectus AI is calibrated against 10 mission-critical acoustic classes with specialized confusion filtering:

| # | Sound Event Class | Domain / Sector | Default Severity | Automated Action Protocol |
|---|---|---|---|---|
| 1 | **Gunshot** | Police & Tactical Security | **Critical** | Immediate lockdown, camera slew, tactical security dispatch |
| 2 | **Panic Scream** | Public Safety & Campuses | **Critical** | Emergency responder & security team immediate dispatch |
| 3 | **Person Asking for Help** | Healthcare & Residences | **Critical** | Distress responder alert ("Help me", "Emergency", vocal SOS) |
| 4 | **Glass Breaking** | Perimeter & Building Security| **High** | Structural breach alarm & auto-pan surveillance feed |
| 5 | **Machinery Fault** | Industrial Plants & Utilities | **High** | Bearing wear/impeller cavitation flag & work order dispatch |
| 6 | **Alarm or Siren** | Facilities & Smart Cities | **High** | Emergency alert logging & automated escalation check |
| 7 | **Aggression / Violence** | Public Venues & Transit | **High** | De-escalation security patrol deployment |
| 8 | **Vehicle Horn** | Logistics & Traffic Depots | **Low** | Ambient traffic logging & acoustic density indexing |
| 9 | **Animal Sound** | Perimeter & Rural Estates | **Low** | Perimeter context logging (eliminates false intrusion alerts) |
| 10 | **Background Noise** | Ambient Baseline | **Informational** | Dynamic acoustic noise floor tracking (HVAC, wind, rain) |

### Acoustic Confusion Disambiguation Matrix
To prevent high-consequence false alarms, the consensus engine applies spectral moment filtering to disambiguate closely resembling acoustic pairs:
* **Gunshot vs. Fireworks / Vehicle Backfire:** Evaluates impulse rise time ($<5\text{ ms}$) and high-frequency spectral centroid decay.
* **Panic Scream vs. Normal Shouting:** Checks formant pitch variation, frequency jitter, and harmonic-to-noise ratio (HNR).
* **Aggression vs. Normal Conversation:** Analyzes vocal energy dynamics, syllabic rate acceleration, and high-frequency envelope modulation.
* **Glass Breaking vs. Metal Dropping:** Examines high-frequency resonance dispersion ($>6\text{ kHz}$) and modal frequency decay curves.
* **Alarm / Siren vs. Vehicle Horn:** Evaluates harmonic pitch periodicity and frequency sweep characteristics.

---

## 👥 6 Enterprise Role Workspaces & Dedicated Portals

The application implements strict Role-Based Access Control (RBAC). Each role has a dedicated sidebar and discrete `.html` templates extending `app/base_studio.html`:

```
                                [ DECTUS PLATFORM ACCESS ]
                                             │
      ┌─────────────────┬────────────────────┼───────────────────┬─────────────────┐
      ▼                 ▼                    ▼                   ▼                 ▼
[ Super Admin ]   [ Company Admin ]   [ Audio Reviewer ]   [ Normal User ]   [ Security & Maint ]
 /app/admin/*      /app/company/*      /app/reviewer/*      /app/user/*       /app/security/*
 18 Pages          10 Pages            12 Pages             10 Pages + Term   12 Pages + Term (each)
```

### 1. Super Administrator Portal (`/app/admin/*` — 18 Dedicated Pages)
* **Routes:** `dashboard`, `companies`, `company_detail`, `users`, `user_detail`, `roles`, `events`, `alerts`, `alert_detail`, `reviews`, `review_detail`, `analytics`, `model_studio`, `system_health`, `audit_logs`, `data_storage`, `settings`, `subscriptions`.
* **Core Duties:** Global B2B tenant management, multi-organization quotas, dynamic pricing tiers, model lifecycle versioning, data retention policies, and platform-wide audit ledger.

### 2. Company Administrator Portal (`/app/company/*` — 10 Dedicated Pages)
* **Routes:** `dashboard`, `users`, `events`, `alerts`, `reviews`, `analytics`, `live_monitoring`, `audit_logs`, `settings`, `profile`.
* **Core Duties:** Organization-scoped acoustic intelligence, facility sensor provisioning, employee access controls, and company audit trails.

### 3. Audio Forensic Reviewer Portal (`/app/reviewer/*` — 12 Dedicated Pages)
* **Routes:** `dashboard`, `queue`, `workspace`, `analysis`, `history`, `quality`, `reports`, `profile`, `disagreements`, `diagnostics`, `resolved`, `workbench`.
* **Core Duties:** Human-in-the-loop forensic adjudication. Interactive HTML5 scrubbable waveform and spectrogram canvases, dual-model comparison breakdown, and immutable original output preservation.

### 4. Normal User / Resident Portal (`/app/user/*` — 10 Pages + Pure Standalone Terminal)
* **Portal Pages:** `dashboard`, `live_monitoring`, `detections`, `alerts`, `history`, `analyze`, `audio`, `notifications`, `profile`, `settings`.
* **Standalone Terminal (`/app/user/terminal`):** Pure fullscreen sci-fi personal command center (`dectus-user`) with **zero sidebar**, real-time audio oscilloscope, and 1-click topbar return to portal.

### 5. Security Operator Portal (`/app/security/*` — 12 Pages + Pure Standalone Terminal)
* **Portal Pages:** `dashboard`, `live_monitoring`, `alerts`, `event_monitor`, `detections`, `history`, `critical`, `analyze`, `reports`, `notifications`, `profile`, `settings`.
* **Standalone Terminal (`/app/security/terminal`):** Tactical perimeter threat monitoring console (`dectus-security`) with **zero sidebar**, active threat breakdown, and instant incident response.

### 6. Maintenance Engineer Portal (`/app/maintenance/*` — 12 Pages + Pure Standalone Terminal)
* **Portal Pages:** `dashboard`, `live_monitoring`, `equipment`, `faults`, `detections`, `history`, `critical`, `analyze`, `reports`, `notifications`, `profile`, `settings`.
* **Standalone Terminal (`/app/maintenance/terminal`):** Industrial acoustic vibration diagnostics console (`dectus-maintenance`) with **zero sidebar**, equipment registry (`NO EQUIPMENT CONFIGURED` when empty), and bearing anomaly tracking.

---

## 📁 Repository Directory Structure

```text
SonicAi/
├── config/                          # Central configuration & rules
│   ├── rules.json                   # 10 mandatory classes, consensus margins & alert thresholds
│   └── settings.py                  # Pydantic BaseSettings, directory paths & environment setup
├── documentation/                   # Engineering & dataset documentation
│   ├── DATASET_SOURCES_AND_PROVENANCE.md  # Complete dataset sources, licensing & distribution
│   └── DATASET_PROVENANCE_AND_SOURCES.md  # Detailed audio provenance documentation
├── notebooks/                       # Training, research & comparison notebooks
├── reports/                         # PDF & Excel forensic report artifacts
├── sample_audio/                    # Reference WAV files for all 10 sound categories
├── scripts/                         # Maintenance, dataset rebuilding & benchmark scripts
│   ├── eval_sample_audios.py        # Evaluates reference samples against dual-AI pipeline
│   ├── generate_140_comparison_report.py # Generates 140-sample benchmark report
│   └── generate_gtm_300_zips.py     # Generates balanced WebM/WAV packages for GTM training
├── src/                             # Core Application Source Code
│   ├── app/                         # FastAPI Routers & Multi-Tenant SaaS Subsystem
│   │   ├── admin_routes.py          # Super Admin routes & tenant management
│   │   ├── app_routes.py            # User, Security, Maintenance routes & RBAC interceptors
│   │   ├── auth_routes.py           # PBKDF2 authentication & instant role switcher endpoints
│   │   ├── company_routes.py        # Company Admin tenant-isolated routes
│   │   ├── reviewer_routes.py       # Audio Reviewer QA queue & resolution endpoints
│   │   ├── security_routes.py       # Tactical security operations endpoints
│   │   ├── stripe_routes.py         # Stripe checkout sessions & billing webhook handlers
│   │   └── schemas.py               # Pydantic API request & response models
│   ├── audio/                       # Digital Signal Processing (DSP) Pipeline
│   │   ├── validator.py             # MIME, file size, duration & sample rate validation
│   │   ├── quality_checker.py       # RMS silence gating, clipping detection & SNR computation
│   │   ├── preprocessor.py          # 16kHz mono resampling & 2.0s rolling window segmenter
│   │   ├── extractor.py             # Librosa feature extraction (MFCCs, Mel-Spectrogram, etc.)
│   │   └── augmentor.py             # Acoustic augmentation (noise injection, pitch shift, speed)
│   ├── consensus/                   # Dual-AI Decision Arbitration
│   │   └── consensus_engine.py      # Confidence delta, consistency matrix & consecutive windows
│   ├── database/                    # MongoDB Atlas Persistence & Security Layer
│   │   ├── mongodb.py               # Async Motor database connection with fallback
│   │   ├── schemas.py               # Document schemas (audio_events, alerts, equipment, users)
│   │   └── security.py              # PBKDF2-HMAC password hashing & HMAC-SHA256 session tokens
│   ├── models/                      # Dual-Model Neural Classifiers
│   │   ├── model_pipeline.py        # Python 2D-CNN feature classifier & model loader
│   │   ├── gtm_inference.py         # Google Teachable Machine native TF binary tensor loader
│   │   ├── saved_models/            # Trained Keras (.keras) & Scikit-learn (.joblib) weights
│   │   └── gtm_files/               # Exported GTM model.json, metadata.json & weights.bin
│   ├── security/                    # Tenant Quotas & Access Policies
│   │   └── quotas.py                # Subscription quota tracking & plan normalizers
│   └── services/                    # Background Services
│       ├── security_service.py      # Security incident dispatch service
│       └── stripe_service.py        # Stripe customer & subscription lifecycle
├── static/                          # Static Web Assets
│   ├── app/                         # Enterprise SaaS Design System
│   │   ├── studio.css               # Dectus zero-gradient enterprise stylesheet
│   │   ├── dectus-user/             # Standalone Normal User Sci-Fi Terminal
│   │   ├── dectus-security/         # Standalone Security Operator Sci-Fi Terminal
│   │   └── dectus-maintenance/      # Standalone Maintenance Engineer Sci-Fi Terminal
│   ├── css/                         # Legacy & public page styles
│   └── js/                          # Web Audio API oscilloscopes & audio visualizers
├── templates/                       # Jinja2 HTML Templates
│   ├── app/                         # SaaS Application Shell
│   │   ├── base_studio.html         # Base studio layout with sidebar slot & topbar
│   │   ├── access_denied.html       # HTTP 403 Forbidden RBAC barrier
│   │   ├── onboarding.html          # Unified 5-step onboarding wizard
│   │   ├── includes/sidebars/       # Role-specific sidebars (admin, company, reviewer, user, sec, maint)
│   │   └── roles/                   # Dedicated role-specific portal page templates
│   │       ├── admin/               # 18 Super Admin templates
│   │       ├── company/             # 10 Company Admin templates
│   │       ├── reviewer/            # 12 Audio Reviewer templates
│   │       ├── user/                # 10 User templates + standalone terminal.html
│   │       ├── security/            # 12 Security templates + standalone terminal.html
│   │       └── maintenance/         # 12 Maintenance templates + standalone terminal.html
│   └── index.html                   # Multi-persona public portal landing page
├── tests/                           # Pytest Automated Test Suite
│   ├── test_api_endpoints.py        # REST API endpoint tests
│   ├── test_audio_pipeline.py       # DSP & validation pipeline tests
│   ├── test_audio_augmentor.py      # Audio augmentation tests
│   ├── test_auth_rbac.py            # Authentication & RBAC barrier tests
│   └── test_sound_and_voice_recognition.py # Dual-AI sound recognition benchmark tests
├── app.py                           # FastAPI Main Application & WebSocket Engine
├── requirements.txt                 # Pinned Python Dependencies
├── AI_USAGE.md                      # AI Governance, Sovereign Runtime & Architecture Declaration
└── README.md                        # Master Project Documentation
```

---

## ⚡ Quickstart & Installation

### 1. System Prerequisites
* **Operating System:** Windows 10/11, Ubuntu 22.04 LTS, or macOS (Apple Silicon supported).
* **Python Runtime:** Python 3.10 or 3.11.
* **Database:** MongoDB Atlas Cloud cluster (or local MongoDB 6.0+ instance).

### 2. Clone Repository & Setup Virtual Environment
```powershell
# Clone the repository
git clone https://github.com/dexasoftware-eng/Sonic-Ai.git
cd Sonic-Ai

# Create and activate Python virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1    # On Linux/macOS: source .venv/bin/activate

# Install pinned production dependencies
pip install -r requirements.txt
```

### 3. Environment Configuration (`.env`)
Create a `.env` file in the root directory:
```ini
# Application Configuration
APP_NAME=Dectus
ENVIRONMENT=development
SECRET_KEY=dectus_sovereign_secret_key_prod_2026_audit

# MongoDB Atlas Cloud Database
MONGODB_URI=mongodb+srv://<username>:<password>@cluster0.mongodb.net/?retryWrites=true&w=majority
DATABASE_NAME=sonic_sentinel_db

# Dual-AI Engine Configuration
CONFIDENCE_THRESHOLD=0.75
CONSECUTIVE_WINDOWS_REQUIRED=2
REQUIRE_MODEL_AGREEMENT=true
```

### 4. Launch Application Server
```powershell
# Start Uvicorn ASGI server with live reloading
python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload
```
Once started, access the platform at:
* **Public Gateway:** `http://127.0.0.1:8000/`
* **Super Admin Portal:** `http://127.0.0.1:8000/app/admin`
* **Company Admin Portal:** `http://127.0.0.1:8000/app/company`
* **Audio QA Reviewer Studio:** `http://127.0.0.1:8000/app/reviewer`
* **Normal User Portal:** `http://127.0.0.1:8000/app/user` (Terminal: `/app/user/terminal`)
* **Security Operator Portal:** `http://127.0.0.1:8000/app/security` (Terminal: `/app/security/terminal`)
* **Maintenance Engineer Portal:** `http://127.0.0.1:8000/app/maintenance` (Terminal: `/app/maintenance/terminal`)

### 5. Instant Role Switching (Testing Utility)
For testing and demonstration, authenticated sessions can be immediately assumed using the role switcher endpoints:
* `http://127.0.0.1:8000/app/switch-admin` &rarr; Swaps session to Super Administrator.
* `http://127.0.0.1:8000/app/switch-user` &rarr; Swaps session to Normal Resident User.
* `http://127.0.0.1:8000/app/switch-security` &rarr; Swaps session to Security Operator.
* `http://127.0.0.1:8000/app/switch-maintenance` &rarr; Swaps session to Maintenance Engineer.

---

## 🧪 Automated Testing & Verification

Run the automated Pytest test suite across all subsystems:

```powershell
# Run the complete test suite
pytest tests/ -v

# Run dedicated RBAC and route verification suite (62 test cases)
python scratch/test_portal_and_rbac.py
```

### Verification Suite Results (September 2026):
```text
============================================================
RBAC & PORTAL VERIFICATION: 62/62 PASSED (0 FAILED)
============================================================
✔ Normal User Pages (10 Dedicated Templates with Sidebar)    : 10/10 PASS
✔ Normal User Terminal (Pure Standalone, Zero Sidebar)       :  1/1  PASS
✔ Security Pages (12 Dedicated Templates with Sidebar)       : 12/12 PASS
✔ Security Terminal (Pure Standalone, Zero Sidebar)          :  1/1  PASS
✔ Maintenance Pages (12 Dedicated Templates with Sidebar)    : 12/12 PASS
✔ Maintenance Terminal (Pure Standalone, Zero Sidebar)       :  1/1  PASS
✔ Cross-Role Unauthorized Access Block (403 Forbidden)       : 20/20 PASS
✔ Role Terminal Shortcuts (/app/terminal)                    :  3/3  PASS
✔ Sci-Fi Terminal Topbar Exit (/app/select-role)             :  3/3  PASS
✔ Role APIs (CSV Export, Settings Update, Equipment Monitor) :  3/3  PASS
```

---

## 🔒 Security, Compliance & Governance

* **Cryptographic Standards:** Passwords hashed with PBKDF2-HMAC-SHA256 (100,000 rounds) using unique 16-byte cryptographic salts. Session tokens signed using HMAC-SHA256 with timestamp expiration.
* **Data Sovereignty:** Zero reliance on third-party cloud audio processing or generative AI APIs. Audio remains strictly within the tenant's secure perimeter.
* **Audit Trail Traceability:** All administrative actions, role overrides, forensic QA decisions, and equipment modifications are recorded with timestamps and operator identity in MongoDB `audit_logs`.
* **Dataset Governance:** All model training and benchmarking comply with the licensing and dataset attribution guidelines detailed in [`DATASET_SOURCES_AND_PROVENANCE.md`](documentation/DATASET_SOURCES_AND_PROVENANCE.md).

---

## 📜 License & Intellectual Property

Copyright © 2026 Dectus AI / Dexa Software Engineering. All rights reserved.  
Unauthorized copying, reverse-engineering, or cloud transmission of proprietary dual-model weights is strictly prohibited.
