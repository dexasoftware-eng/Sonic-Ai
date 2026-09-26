# AI Usage & Architectural Integrity Declaration (AI_USAGE.md)
**Platform Name:** SonicSentinel AI (Multi-Tenant Acoustic Intelligence SaaS)  
**Domain:** Sovereign Edge Acoustic Analytics & Machine Learning  
**Architecture Model:** Enterprise Multi-Tenant Sovereign DSP  

---

## 1. Architectural Integrity Statement
SonicSentinel AI adheres to strict architectural integrity and sovereign computation requirements. This document transparently outlines how AI-assisted development tools were utilized during system design, scaffolding, and verification.

**Key Architectural Guarantees:**
1. **Zero External Generative-AI APIs at Runtime:** All runtime sound classifications are executed strictly on-premise / natively through independently trained local 2D-CNN neural models and embedded sovereign classifiers. No external third-party cloud APIs (such as OpenAI Whisper, Google Gemini, or Claude API) are invoked to classify operational sounds.
2. **Zero Hardcoded Predictions:** All classifications, confidence distributions, and consensus matrices are dynamically computed from live mathematical audio features (FFT, Mel-filterbanks, MFCCs).
3. **Comprehensive Engineering Verification:** Every mathematical transform, signal processing filter, neural topology, consensus rule, and multi-tenant data boundary has been rigorously tested and verified by our engineering team.

---

## 2. Engineering Assistance & Architectural Log

### Entry 1: Multi-Tenant Architecture Blueprint & Scaffolding
* **Engineering Tool:** Antigravity AI Assistant
* **Purpose:** Multi-tenant enterprise SaaS design, modular directory scaffolding, and async boilerplate generation.
* **Scope:** Drafting asynchronous FastAPI endpoints, structuring Web Audio API HTML5 canvas visualizer, and designing MongoDB collection schemas with strict `tenant_id` isolation.
* **Files Affected:**
  * `app.py`
  * `src/database/`
  * `config/rules.json`
  * `config/settings.py`
  * `requirements.txt`
* **Engineering Customizations:**
  * Implemented strict tenant isolation filters across all database queries.
  * Customized consecutive window confirmation logic specifically for life-safety hazard classes.
  * Configured dual-model consensus parameters (minimum confidence threshold 0.80, top-two margin 0.15).
* **Verification Completed:**
  * Verified MongoDB connection against MongoDB Atlas Cloud clusters.
  * Verified FastAPI REST routes (`/health`, `/api/audio/upload`) and WebSocket stream (`/ws/live-audio`).

### Entry 2: Audio Engineering & Feature Extraction Pipeline
* **Engineering Tool:** Antigravity AI Assistant
* **Purpose:** Developing audio validation, acoustic quality filters (clipping, silence, SNR), and DSP feature extraction pipeline.
* **Scope:** Formulating SNR calculation logic and Librosa/SciPy feature extraction vectors (MFCCs, Mel-Spectrogram, Chroma, Spectral Centroid, Bandwidth, Roll-off, ZCR, RMS).
* **Files Affected:**
  * `src/audio/validator.py`
  * `src/audio/quality_checker.py`
  * `src/audio/preprocessor.py`
  * `src/audio/feature_extractor.py`
* **Engineering Customizations:**
  * Tuned RMS silence threshold (0.005) and clipping threshold (0.99) for real-world microphone noise floors.
  * Added sustained pure-tone detection to avoid misinterpreting industrial alarms as low SNR noise.
  * Synthesized reference audio clips across all mandatory categories for deterministic unit testing.
* **Verification Completed:**
  * 100% automated test coverage in `tests/test_audio_pipeline.py` and `tests/test_api_endpoints.py` (automated tests passed).

### Entry 3: Security, Forensic Audio Studio, & Dynamic Registry
* **Engineering Tool:** Antigravity AI Assistant
* **Purpose:** Developing cryptographic RBAC authentication layer, forensic audio review studio, and dynamic category registry.
* **Scope:** Implementing PBKDF2-HMAC-SHA256 password hashing helper, HTML5 Web Audio preview player with variable speed controls (0.5x, 1.0x, 1.5x), and automated test suites.
* **Files Affected:**
  * `src/database/security.py`
  * `app.py`
  * `templates/features.html`
  * `static/js/main.js`
  * `tests/test_auth_rbac.py`
* **Engineering Customizations:**
  * Implemented 5 enterprise persona workspaces (`security_operator`, `maintenance_operator`, `audio_reviewer`, `administrator`, `normal_user`).
  * Configured dynamic category additions with immediate real-time consensus engine reloading.
  * Added 0.5x slow-motion playback specifically tailored for acoustic forensic review.
* **Verification Completed:**
  * All automated test suites passed cleanly in `tests/`.
