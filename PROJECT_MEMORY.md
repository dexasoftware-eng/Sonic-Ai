# SonicSentinel AI — Official Project Memory & Flow (Locked Rules)

Yeh file user ki instructions aur SRS ke mutabiq step-by-step memorize ki gayi hai. Ismein likha har rule final hai.

---

## 1. Architecture & Multi-Tenancy
- **Multi-Tenant System:** Multiple companies/organizations system mein register kar sakti hain. Har company ka data, sensors, aur alerts doosri company se isolated honge.
- **5 Roles:**
  - **Company ke 4 Roles:**
    1. `Security Operator` (Physical threats: Gunshot, Panic Scream, Aggression, Glass Breaking, Alarm/Siren)
    2. `Maintenance Operator` (Machinery Faults, equipment health & inspection alerts)
    3. `Audio Forensic Reviewer` (Spectrogram/waveform review, model disagreement resolution, manual override)
    4. `Administrator` (Thresholds, rules configuration, sensor/stream management, CSV/audit exports)
  - **5th Role (General):**
    5. `Normal User` (General citizen/resident/employee — self-registration, SOS help trigger, audio reporting)
- **Git Rule:** Jab tak user khud na bole, GitHub par `git push` nahi karna.

---

## 2. Problem & Solution
- **Problem:** Factories, public places, transport, buildings, ghar, farms, service centers aur security locations par sound ek warning signal hoti hai. Manual sunne mein time lagta hai, sounds miss hoti hain, response late hota hai, insani faisla alag hota hai, aur shor mein false alarms aate hain.
- **Solution:** AI ke zariye automatic monitoring jo **Uploaded Audio** aur **Live Microphone** dono ko real-time analyze kare.

---

## 3. Sound Categories & Confusion Pairs
### A. 10 Mandatory Classes (Pehle yeh 10 mukammal karni hain):
1. `Machinery Fault`
2. `Glass Breaking`
3. `Alarm/Siren`
4. `Vehicle Horn`
5. `Animal Sound`
6. `Gunshot`
7. `Panic Scream`
8. `Aggression / Violent Conflict`
9. `Person Asking for Help`
10. `Background Noise`

### B. Optional Classes (10 poori hone ke baad):
- Drone, Drilling/Grinder, Fireworks, Vehicle Backfire, Explosion, Door Impact, Graffiti Spray, Normal Machinery, Unknown Sound.

### C. Critical Events (Immediate Alert Required):
- Gunshot, Glass Breaking, Panic Scream, Aggressive shouting / Violent conflict, Help request, Alarm/Siren, Serious machinery fault.

### D. Milti-Julti Sounds Jinhein Alag Karna Hai (Confusion Pairs):
| Sound A (Target) | Sound B (Confuser) |
| :--- | :--- |
| Gunshot | Fireworks / Vehicle Backfire |
| Panic Scream | Normal shouting |
| Aggression | Normal conversation |
| Glass Breaking | Metal impact |
| Alarm | Vehicle Horn |
| Machinery Fault | Normal Machinery |
| Help Request | Ordinary speech |

---

## 4. Input Modes (Audio Kahan Se Aayegi)
### A. Audio Upload:
- **Supported Formats:** WAV, MP3, FLAC, OGG, M4A.
- **Batch Upload:** Authorized users ek sath multiple files upload kar sakte hain.
- **Analysis:** Poori recording ya segments mein analyze ho sakti hai.
- **Preview Controls:** Play, Pause, Replay, Seek, Volume.

### B. Live Microphone:
- User mic Start/Stop kar sake (pehle browser permission leni hogi).
- Audio chhoti windows (1–3 seconds) mein lagatar capture hogi.
- **Mic Status on UI:** `Available`, `Active`, `Paused`, `Disconnected`, `Permission Denied`.
- Live mode bhi exact wohi validation, preprocessing aur dual-model pipeline follow karega jo upload mode karta hai.

---

## 5. Audio Validation (Checking Gate)
- **Checks:** Format, file size, duration, sampling rate, channels, corruption check, signal presence check. Live mode mein mic availability aur permission check.
- **Rejection:** Silent, damaged/corrupt, unsupported, bohat short ya unusable audio ko reject karna hai aur user ko samajh aane wala clear error message dikhana hai.
- **Extracted Metadata:** Filename, format, duration, sampling rate, channels, bit depth, file size, upload date/time.

---

## 6. Preprocessing (Model ko Dene se Pehle 8 Safai Steps)
Raw audio seedhi model mein nahi jayegi. Yeh steps lazmi honge:
1. **Resampling:** Standard sampling rate par lana.
2. **Stereo → Mono:** 2 channels ko 1 channel banana.
3. **Normalization:** Volume ko suitable range mein lana.
4. **Silence Trimming:** Faltu khamoshi hatana.
5. **Noise Reduction:** Background shor kam karna.
6. **Segmentation:** Lambi audio ko fixed-length tukron mein todna (har segment ka **start aur end timestamp** store hoga).
7. **Padding/Truncation:** Chhoti audio ko barhana, lambi ko kaatna.
8. **Format Conversion:** Zaroorat ho to supported format mein badalna.
- **Additional Detection:** Silence, clipping, aur background noise level detect karna.

---

## 7. Audio Quality Analysis
- **Checks:** Silence, clipping, excessive noise, low signal, wrong duration, encoding issue, missing frames.
- **4 Quality Grades:**
  1. `Good`
  2. `Acceptable`
  3. `Poor`
  4. `Unusable`
- **Purpose:** Agar audio kharab hai toh model ki prediction par bharosa nahi kar sakte; quality grade alert aur uncertainty decision dono mein use hoga.

---

## 8. Dataset Rules (Sabse Sakht Requirements)
- **Minimum Size:** Minimum 3,000 unique original clips (10 classes × 300 original clips minimum; hamare dataset mein is se bhi zyada clips hain).
- **Mandatory Metadata System (Har Clip ke Sath):**
  - `Audio ID` (Unique), `filename`, `category`, `source`, `duration`, `sampling rate`, `channels`, `environment`, `recording device`, `approximate distance`, `original/augmented`, `dataset split`.
- **Acoustic Variety:** Alag devices, distances (near/far), indoor/outdoor, loudness, background interference, echo, duration, clean/noisy, single/overlapping sounds, alag speakers (taake model ratta na mare).
- **"Person Asking for Help" Defined Phrases:**
  - Sirf defined phrases: *"Help me"*, *"Somebody help"*, *"Please help"*, *"Call for help"*, *"Emergency"*.
  - Ethically licensed, voluntary, ya permitted synthetic sources se.
- **Strict Stratified Split (70 / 15 / 15):**
  - **70% Training** (Base: 2,100+ clips)
  - **15% Validation** (Base: 450+ clips)
  - **15% Testing** (Base: 450+ clips)
  - **Zero Data Leakage Rules:**
    - Validation/Test data training mein harqat use nahi hoga.
    - Ek original recording ke saare segments ek hi split mein rahenge.
    - Python aur GTM dono models ke liye exact same split use hoga.
    - Python aur GTM ki comparison same unseen test recordings par hogi.
- **Common Dataset Rule:** Python aur GTM dono ke liye same underlying dataset hoga (same Audio ID aur label). Alag dataset dekar fake comparison mana hai.
- **Augmentation Rules (Sirf Training ke liye):**
  - Techniques: Noise add, time shift, pitch shift, time stretch, volume change, limited reverb, distance simulation, device simulation.
  - Augmented file usi split (training) mein rahegi.
  - Augmented clip ko naya original clip count nahi kiya jayega (e.g., 300 original + 100 augmented = 400 training samples, par original count 300 hi mana jayega).
- **Pipeline Health Check:** Class imbalance aur insufficient samples ko automatically identify karna.

---

## 9. Acoustic Features (Python Pipeline — 10 Features)
Python pipeline har preprocessed audio window se yeh 10 acoustic features extract karegi:
1. **MFCC:** Awaaz ki frequency ki khaas pehchan (fingerprint).
2. **Mel Spectrogram:** Time aur frequency mein energy ka 2D naqsha.
3. **Chroma:** Pitch / sur se related information.
4. **Zero Crossing Rate (ZCR):** Signal zero line kitni baar cross karta hai.
5. **RMS Energy:** Loudness / signal energy.
6. **Spectral Centroid:** Frequency ka "center".
7. **Spectral Bandwidth:** Frequency kitni phaili hui hai.
8. **Spectral Roll-off:** Frequency distribution ka upper hissa.
9. **Onset Strength:** Sound ke achanak shuru hone ki taqat.
10. **Tempo:** Rhythm / speed.

---

## 10. Python Models (Training & Selection)
- **Minimum 3 Models Comparison:** Kam az kam 3 models train aur compare karne hain (Options: SVM, Random Forest, Gradient Boosting, XGBoost, CNN, CRNN, Transfer Learning Audio Model).
- **Hyperparameter Tuning:** Systematic tuning honi chahiye.
- **Model Selection Criteria:** Best model sirf accuracy se nahi, balki in tamam metrics se chuna jayega:
  - Accuracy, Precision, Recall, F1, Macro F1, Confusion Matrix, Class-wise performance, Critical-event recall, aur Noise robustness.
- **Full Probability Output:** Selected model har segment ko classify karega aur **10 ki 10 classes ke confidence scores** dega (sirf final class kaafi nahi — e.g. `Gunshot: 0.91, Glass: 0.04, Alarm: 0.02...`).

---

## 11. Google Teachable Machine (GTM — Independent Model)
- **Independent Training:** Alag Audio Project banana hai, jo Python se independently trained ho.
- **Exact Same Classes & Data:** Wahi 10 mandatory classes (same names) aur wahi common dataset use hoga.
- **Web Integration:** Web app mein integrate hokar same audio window ko independently classify karega aur predicted class + har class ka confidence dega.
- **Anti-Disqualification Rule:** Python ka result GTM ko input mein har-giz nahi dena (ye direct disqualification ka sabab ban sakta hai).

---

## 12. Python vs GTM Comparison & Consensus
- **Comparison Points:**
  - Dono ki predicted category.
  - Dono ke confidence values.
  - Category same hai ya nahi.
  - Top confidence ka farq: `Confidence Difference = |Python Top Confidence − GTM Top Confidence|`
  - Top-two confidence ka farq (margin).
- **Top-N Display:** Har model ki kam az kam **top 3 predictions** UI par display karni hain.
- **Model Consistency ke 4 Statuses:**
  1. `Acceptable Match` (Results kaafi compatible hain)
  2. `Weak Match` (Thoda farq ya kamzor agreement)
  3. `Model Disagreement` (Dono alag class bata rahe hain)
  4. `Uncertain Result` (Overall result par bharosa nahi)
- **Admin Configuration:** Admin `minimum confidence threshold` aur `top-two margin threshold` configure kar sake.

---

## 13. Uncertainty Handling (Jab Result "Pakka Nahi")
AI ka *"mujhe pata nahi"* kehna bhi system ka core feature hai. Result uncertain hoga jab:
1. Confidence kam ho.
2. Top 2 classes bohat qareeb hon (low top-two margin).
3. Audio quality `Poor` ho.
4. Models disagree karein (`Model Disagreement`).
5. Overlapping sounds hon (ek hi audio mein kai classes ka confidence ek saath strong ho).

---

## 14. Critical Event Confirmation (Repeated Detection)
Ek akeli, unstable 1-second prediction par blind critical alert nahi banega. Confirmation ke liye yeh conditions check hongi:
- Lagatar windows mein same detection (consecutive windows).
- Minimum confidence threshold pass hona.
- Python + GTM ka agreement.
- Repeated detection count.
- Top-two confidence difference (margin).
- Acceptable audio quality.

---

## 15. Alert System & Severity Rules
### A. 5 Severity Levels:
`Informational`, `Low`, `Medium`, `High`, `Critical`
*(SRS Note: SRS mein ek jagah 5 levels hain aur functional list mein "High" chhoot gaya hai — hum safely 5 levels hi rakhenge aur report mein yeh assumption likhenge).*

### B. Har Sound ka Behaviour:
| Sound Category | Severity | Action / Behaviour |
| :--- | :--- | :--- |
| **Background Noise** | `Informational` | Normally non-critical |
| **Animal Sound** | `Low` | Context dependent |
| **Vehicle Horn** | `Low` / `Medium` | Traffic / environment event |
| **Machinery Fault** | `High` | Maintenance alert + inspection recommendation |
| **Glass Breaking** | `High` | Security alert |
| **Alarm/Siren** | `High` | Attention alert |
| **Aggression** | `High` ya `Critical` | Confidence + repetition par depend karega |
| **Panic Scream** | `Critical` | Sufficient confidence par |
| **Person Asking for Help** | `Critical` | Defined phrases detect hone par |
| **Gunshot** | `Critical` | Sirf confirmation + confidence rules poore hone par |
| **Unknown** | `Unknown` / `Manual Review` | Manual Review Required |

### C. Configurable Alert Rules:
- Har rule mein shamil hoga: `category`, `minimum confidence`, `top-two margin`, `required consecutive detections`, `model agreement`, `audio quality`, `severity`, `recommended action`, `manual-review condition`, `escalation condition`.
- Rules JSON/YAML/CSV/database mein store honge aur Admin in sab ko configure kar sakega.

### D. Alert Handling & Lifecycle:
- Critical event par dashboard par visible alert aayega.
- Authorized users alert ko **Acknowledge**, **Dismiss**, ya **Escalate** kar sakenge.
- Complete alert history database mein maintain hogi.

---

## 16. Manual Review (Forensic Review Queue)
### A. Review Queue Triggers (Kab Event Review Queue mein Jayega):
1. Python aur GTM alag prediction dein (`Model Disagreement`).
2. Confidence kam ho.
3. Audio quality `Poor` ho.
4. Top 2 classes bohat qareeb hon (low top-two margin).
5. Overlapping sounds hon.
6. Unknown pattern ho.
7. Critical event ho lekin models agree na karein.
8. Possible false alarm ho.

### B. Reviewer Actions & Preservation Rule:
- **Actions:** Reviewer audio sune, class confirm/correct kare, comments de, recommended action de, aur automatic result ko **Override** kar sake.
- **Strict Preservation Rule:** Override ke baad bhi **original model output preserve rahega** (delete ya overwrite nahi hoga).

---

## 17. Final Decision & Event Storage
- **Final Decision Inputs (8 Factors):**
  - Python prediction, GTM prediction, confidence difference, top-two difference, audio quality, repeated detection, critical-event rules, manual-review conditions.
- **Final Output Fields:**
  - Detected category, model agreement, confidence level, severity, alert status, recommended action, manual review required hai ya nahi.
- **Database Storage per Event:**
  - `Audio ID`, metadata, Python prediction + confidence scores, GTM prediction + confidence, audio quality, severity, alert status, reviewer decision, model versions, processing timestamp.
- **Event Status Lifecycle:**
  - `Uploaded` → `Classified` → `Uncertain` → `Alert Generated` → `Manual Review` → `Reviewed` → `Closed`

---

## 18. Visualization (Waveform & Spectrogram)
- Waveform aur Spectrogram / Mel Spectrogram generate aur UI par display karne hain.
- Yeh visualizations downloadable reports mein bhi shamil honge.

---

## 19. Users & Roles
- Registration/Login, user profile create/update, aur har user ka unique `User ID`.
- **5 Roles:** `Normal User`, `Audio Reviewer`, `Security Operator`, `Maintenance Operator`, `Administrator` (Multi-tenant company isolation ke sath har role ke alag permissions).

---

## 20. Dashboards (3 Views)
| Dashboard | Kya Dikhata Hai |
| :--- | :--- |
| **User Dashboard** | Recent uploads, current detections, critical events, audio warnings, manual-review records |
| **Live Dashboard** | Mic status, current sound, Python result, GTM result, agreement, severity, active alert, waveform, spectrogram, quality |
| **Admin Dashboard** | Total events, category counts, critical alerts, average confidence, disagreements, poor-quality recordings, detection trends |
- Saath mein **critical timeline**, **recent detections**, aur **category statistics** bhi shamil honge.

---

## 21. Search, Analytics & Reports
- **Search / Filter:** `Audio ID`, `filename`, `category`, `date range`, `confidence`, `severity`, `quality`, `review status`, `user`.
- **Analytics:** Category frequency, critical event frequency, confidence distribution, false positives, false negatives, model disagreement, audio quality, alert response.
- **Downloadable Report:** Metadata, Python prediction, GTM prediction, confidence, difference, waveform, spectrogram, quality, severity, alert, review decision.
- **Admin Export:** CSV / Excel-compatible export.

---

## 22. Security, Database & Privacy
- **Storage & Database:**
  - Audio securely store ho, controlled access ke saath.
  - Database collections/records: `users`, `metadata`, `predictions`, `confidence`, `alerts`, `reviews`, `model versions`, `audit records`.
- **Duplicate Detection (2 Levels):**
  - *Exact Duplicate:* Secure hash (SHA-256) se.
  - *Near-Duplicate:* Re-encoded, trimmed ya volume-adjusted copies pakadne ki koshish.
- **Model Version Linking:** Har prediction ke saath Python aur GTM dono ka version linked ho.
- **Audit Trail:** Logins, uploads, mic sessions, predictions, alerts, reviews, overrides, exports, model updates.
- **Error Handling & Anomaly Alerts:**
  - Samajh aane wale clear errors (invalid file, unsupported format, decoding failure, model failure, DB failure, report failure).
  - Admin ko anomalies par alert (repeated failed uploads, model failures, low-confidence spikes, zyada critical alerts, duplicates, failed logins).
- **Privacy & Fairness:**
  - User ko saaf pata ho ke mic active hai (chhup kar recording nahi).
  - Data retention period admin set kar sake.
  - UI desktop, tablet aur mobile browsers par responsive ho.
  - Bias se bachao (alag speakers/devices/environments ke against).

---

## 23. Non-Functional Requirements (Performance & Accuracy Targets)
| Metric / Parameter | Official Target |
| :--- | :--- |
| **Speed (Upload)** | 30 second ki audio **8 second ke andar** process ho |
| **Speed (Live)** | **3 second ke andar** prediction aaye |
| **Scalability** | Kam az kam **20,000 events**, multiple concurrent users |
| **Accuracy (Dono Models)** | **85%+** overall test accuracy, **0.80+** macro F1 |
| **Critical Classes Recall** | **85%+** (*Gunshot, Glass Breaking, Panic Scream, Aggression, Help*) |
| **Availability** | Monitoring hours mein **99% uptime** |
| **Usability** | Har role ke liye easy aur intuitive UI |

---

## 24. Enterprise SaaS Architecture, Stripe, UI Design & Portal Modules
### A. UI/UX Design Standard:
- **ElevenLabs / Modern AI Studio Aesthetic:** Sleek, studio-grade AI audio interface (clean high-contrast design, studio audio transport bar, smooth waveform/spectrogram visualizers, crisp typography, responsive across desktop/tablet/mobile).

### B. Subscription Model & Stripe Payment Integration:
- **Stripe Checkout Integration:** Subscription purchase aur completion ke liye Stripe payment gateway integrate hoga.
- **2 Subscription Categories:**
  1. **Individual (Normal User) Subscription (B2C):**
     - Aam user/resident individual plan leta hai.
     - Uske critical alerts aur manual reviews **Super Admin ki Global Platform Team** (*Platform Audio Reviewer*, *Platform Security Operator*, *Platform Maintenance Operator*) handle karti hai.
  2. **Company (Enterprise Tenant) Subscription (B2B):**
     - Company register karke enterprise plan leti hai.
     - Company ka apna **Company Admin** hota hai jo apni company ke liye khud ke *Company Audio Reviewer*, *Company Security Operator*, aur *Company Maintenance Operator* add karta hai.
     - Company ka saara data, alerts, aur reviews 100% usi company ke andar isolated rehte hain.

### C. Dynamic Custom Category & Live Model Retraining (Admin Studio):
- **Add Custom Category:** Admin apni marzi se nayi sound category/class (e.g. Optional classes jaise *Drone*, *Explosion*, *Fireworks* ya custom class) add kar sakta hai.
- **Batch Clip Upload & Retraining:** Admin us class ke multiple audio clips upload karke portal se hi **Model Retrain** trigger kar sakta hai.
- System automatically clips ko validate/preprocess karke features extract karega, Python model ka naya version (`v1.1`, `v1.2`...) train karega, aur Audit Trail mein retraining evidence save karega (sath hi GTM model link/weights update karne ka option bhi hoga).

### D. 4-Way Professional Audio Ingestion Hub:
1. **File & Batch Upload** (SRS Mandatory — WAV, MP3, FLAC, OGG, M4A with Studio Player).
2. **Live Browser Microphone** (SRS Mandatory — 1–3s sliding windows with mic status indicator).
3. **Remote Stream / CCTV Audio URL Connector** (Direct stream ya cloud audio URL fetch & analyze).
4. **IoT Edge Sensor API & Multi-Zone Live Scenario Simulator** (Company API Keys for hardware sensors + Live Multi-Zone Acoustic Soundboard for real-time stress-testing & judge demonstrations).

### E. Role-Wise UI Portal Modules (Screens):
- **Public Website:** Landing Page, Pricing & Subscriptions (Normal vs Company), Login / Register.
- **Super Admin Portal:** Global Dashboard, Companies Management, Subscriptions & Stripe Manager, Platform Team Manager (for Normal Users), AI Model Studio & Custom Class Trainer, Dataset & Metadata Explorer, Global Audit & Anomaly Logs.
- **Company Admin Portal:** Company Dashboard, 4-Way Audio Studio, Company Staff (Roles) Manager, Sensors/Zones Manager, Company Alert Rules & Thresholds, Search/Analytics & CSV Export, Company Subscription & Billing.
- **Security Operator Portal:** Live Tactical Threat Radar, Security Alerts Queue (Acknowledge/Dismiss/Escalate), Incident History.
- **Maintenance Operator Portal:** Machinery Health Monitor, Maintenance Alerts & Inspection Queue, Equipment Audio Logs.
- **Audio Forensic Reviewer Portal:** Manual Review Queue, Forensic Workbench (Player + Waveform + Spectrogram + Python vs GTM Top-3), Override & Verdict Panel (preserving original AI outputs).
- **Normal User Portal:** Personal Dashboard, Audio Scanner (Upload + Live Mic + SOS Help), My Alerts & Review Updates, My Reports & Subscription.
