# AI Usage Declaration (AI_USAGE.md)
**Project Name:** SonicSentinel AI (Multi-Tenant Acoustic Intelligence SaaS)  
**Theme:** AcousticX Intelligence  
**Competition:** Aptech TechWiz 7 — NextWave AI and ML Category  

---

## 1. Compliance Statement
In strict adherence to the Aptech TechWiz 7 Competition Rules and SRS Section 1.8 (Competition Integrity and Anti-Shortcut Requirements, Item 10 & 15), this document transparently declares all instances where AI-assisted development tools were utilized during the conception, architecture, coding, and testing of the SonicSentinel AI system.

**Key Affirmations:**
1. **Zero External Generative-AI APIs at Runtime:** All runtime sound classifications are executed strictly on-premise / natively through our independently trained local Python models and exported Google Teachable Machine models. No external APIs (such as OpenAI Whisper, Google Gemini, or Claude API) are invoked to classify sounds.
2. **Zero Hardcoded Fakes:** No hardcoded predictions, invented confidence scores, or pre-scripted evaluation answers are utilized.
3. **Comprehensive Human Verification:** Every mathematical audio transform (FFT, Mel-filterbanks, MFCCs), neural architecture, consensus rule, and MongoDB multi-tenant schema has been thoroughly reviewed, understood, modified, and tested by team members.

---

## 2. Record of AI Assistance Across Competition Days

### Entry 1: Multi-Tenant Architecture Blueprint & Scaffolding
* **AI Tool Name:** Antigravity AI Assistant
* **Purpose:** Multi-tenant enterprise SaaS design, directory scaffolding compliant with TechWiz SRS Section 1.10, and initial boilerplate generation.
* **Assistance Requested:** Drafting asynchronous FastAPI endpoints, structuring Web Audio API HTML5 canvas visualizer, and designing MongoDB Pydantic collection schemas with `tenant_id` isolation.
* **Files Affected:**
  * `app.py`
  * `database/mongodb.py`
  * `database/schemas.py`
  * `config/rules.json`
  * `config/settings.py`
  * `requirements.txt`
* **Student Modifications & Customizations:**
  * Implemented tenant isolation filters across all database queries.
  * Customized consecutive window confirmation logic specifically for Gunshot and Panic Scream classes.
  * Configured dual-model consensus parameters (minimum confidence threshold 0.80, top-two margin 0.15).
* **Testing Completed:**
  * Verified MongoDB connection against local MongoDB and MongoDB Atlas Cloud (`cluster0.909zcsz.mongodb.net`).
  * Verified FastAPI REST routes (`/health`, `/api/audio/upload`) and WebSocket stream (`/ws/live-audio`).
* **Verifying Team Members:**
  * Team Lead / ML Engineer
  * Full-Stack Developer

### Entry 2: Audio Engineering & Feature Extraction Pipeline
* **AI Tool Name:** Antigravity AI Assistant
* **Purpose:** Developing audio validation, quality checks (clipping, silence, SNR), and feature extraction pipeline.
* **Assistance Requested:** Formulating SNR calculation logic and Librosa/SciPy feature extraction vectors (MFCCs, Mel-Spectrogram, Chroma, Spectral Centroid, Bandwidth, Roll-off, ZCR, RMS).
* **Files Affected:**
  * `audio_preprocessing/validator.py`
  * `audio_preprocessing/quality_checker.py`
  * `audio_preprocessing/preprocessor.py`
  * `feature_extraction/extractor.py`
  * `sample_audio/generate_synthetic_samples.py`
* **Student Modifications & Customizations:**
  * Tuned RMS silence threshold (0.005) and clipping threshold (0.99) for real-world microphone noise floors.
  * Added sustained pure-tone detection to avoid misinterpreting alarms as low SNR noise.
  * Synthesized 12 reference audio clips across all mandatory categories for deterministic unit testing.
* **Testing Completed:**
  * 100% automated test coverage in `tests/test_audio_pipeline.py` and `tests/test_api_endpoints.py` (9/9 tests passed).
* **Verifying Team Members:**
  * Audio Signal Processing Engineer
  * Quality Assurance Tester

### Entry 3: Phase 1 Finalization — RBAC Authentication, Forensic Audio Preview, & Dynamic Registry
* **AI Tool Name:** Antigravity AI Assistant
* **Purpose:** Developing cryptographic RBAC authentication layer, forensic audio preview widget, interactive persona navigation, and dynamic category registry.
* **Assistance Requested:** Generating PBKDF2-HMAC-SHA256 password hashing helper, HTML5 Web Audio preview player with variable speed controls (0.5x, 1.0x, 1.5x), and automated Pytest test suite for RBAC.
* **Files Affected:**
  * `database/security.py`
  * `app.py`
  * `templates/index.html`
  * `static/js/main.js`
  * `tests/test_auth_rbac.py`
  * `config/settings.py`
  * `config/rules.json`
* **Student Modifications & Customizations:**
  * Implemented 5 competition-aligned demo accounts (`security_operator`, `maintenance_operator`, `audio_reviewer`, `administrator`, `normal_user`) with 1-click seeding for live defense.
  * Configured dynamic category additions with immediate real-time consensus engine reloading to handle unexpected evaluator sound categories.
  * Added 0.5x slow-motion playback specifically tailored for acoustic forensic review.
* **Testing Completed:**
  * 15/15 automated tests passed cleanly in `tests/` (100% green).
* **Verifying Team Members:**
  * Full-Stack Developer
  * Security & DevOps Engineer

---

*(This log is updated continuously across all competition days as new modules and Colab training runs are executed).*

