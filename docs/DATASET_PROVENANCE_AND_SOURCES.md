# 🛡️ SonicSentinel AI — Dataset Provenance, Sources & Methodology
### Aptech TechWiz 7 — NextWave AI and ML Category
**Document Version:** 1.0  
**Project:** SonicSentinel AI (Theme: AcousticX Intelligence)  
**Target Scale:** 10 Mandatory Sound Categories $\times$ 400 clips = **4,000 Total Audio Clips** (3,200 Train, 800 Test)  
**Audio Standard:** 16,000 Hz, Mono, 16/32-bit PCM WAV, Normalized Peak Amplitude (0.95), 2.0-second fixed analysis window.

---

## 1. Master Dataset Provenance Table

| # | Category Name | Primary Dataset Source | Source Identifier / Slug / Link | Original Seed Count | Strategy & Method Applied | Final Target |
| :- | :--- | :--- | :--- | :--- | :--- | :--- |
| **1** | **Gunshot** *(with Weapons)* | Gunshot Audio Dataset (YouTube Curated) | Kaggle: `emrahaydemr/gunshot-audio-dataset` | **851 real clips** across 8 gun models | **Direct Cloud Download** (Pre-tagged with weapon models: AK-47, Desert Eagle, M16, MP5, M249, etc.) | **851 clips** *(Ready)* |
| **2** | **Panic Scream** | Human Screaming Detection Dataset | Kaggle: `redwud/screaming-detection` | **862 real scream clips** | **Direct Cloud Download** (Positive scream emergency recordings) | **862 clips** *(Ready)* |
| **3** | **Aggression** | Audio-based Violence Detection Dataset | Kaggle: `fangfangz/audio-based-violence-detection-dataset` | **300+ clips** | **Direct Cloud Download** (Hostile shouting, physical fights, altercations) | **400 clips** *(Target)* |
| **4** | **Person Asking Help** | Threat Detection Audio Dataset | Kaggle: `mohithjain04/threat-detection-audio-dataset` | **300+ clips** | **Direct Cloud Download** (Real distress calls, emergency cries, "help me") | **400 clips** *(Target)* |
| **5** | **Glass Breaking** | ESC-50: Dataset for Environmental Sound Classification | Karol J. Piczak (ESC-50 GitHub / Local) | **40 real seed clips** | **Tareeqa 1: DSP Audio Augmentation** (Pitch shift $\pm 1.5$st, Time stretch $0.9\times-1.1\times$, Noise injection, Gain scaling) | **400 clips** *(Target)* |
| **6** | **Vehicle Horn** | UrbanSound8K (Salamon et al.) | Kaggle: `chrisfilo/urbansound8k` (Class 1) | **429 real clips** | **Tareeqa 2: Selective Cloud Extraction** (Filtered directly from UrbanSound8K in Colab) | **429 clips** *(Ready)* |
| **7** | **Alarm / Siren** | UrbanSound8K (Salamon et al.) | Kaggle: `chrisfilo/urbansound8k` (Class 8) | **929 real clips** | **Tareeqa 2: Selective Cloud Extraction** (Filtered directly from UrbanSound8K in Colab) | **929 clips** *(Ready)* |
| **8** | **Machinery Fault** | ESC-50 (Engine, Chainsaw, Washing Machine) | Karol J. Piczak (ESC-50 GitHub / Local) | **160 real seed clips** | **Tareeqa 1: DSP Audio Augmentation** (Acoustic load variation, noise injection) | **400 clips** *(Target)* |
| **9** | **Animal Sound** | ESC-50 (Dog, Cat, Rooster, Crow, Cow, Frog) | Karol J. Piczak (ESC-50 GitHub / Local) | **480 real clips** | **Local Extraction & Cloud Sync** (Already on Drive) | **480 clips** *(Ready)* |
| **10** | **Background Noise** | ESC-50 (Rain, Wind, Thunder, Fire, Footsteps) | Karol J. Piczak (ESC-50 GitHub / Local) | **320 real seed clips** | **Local Extraction + Augmentation** (Already on Drive) | **400 clips** *(Target)* |

---

## 2. Category-by-Category Technical Deep Dive

### 1. Gunshot with Weapon Identification Metadata
* **Dataset:** *Gunshot Audio Dataset*
* **Citation:** Tuncer, T., Dogan, S., Akbal, E., Aydemir, E. (2021). *An Automated Gunshot Audio Classification Method Based On Finger Pattern Feature Generator And Iterative Relieff Feature Selector*, Journal of Engineering Science of Adıyaman University.
* **Firearm Types & Counts:**
  1. **AK-47:** 72 files
  2. **IMI Desert Eagle:** 100 files
  3. **M16:** 200 files
  4. **MP5:** 100 files
  5. **M249:** 99 files
  6. **AK-12:** 98 files
  7. **Zastava M92:** 82 files
  8. **MG-42:** 100 files
* **Organization:** Each file is prefixed with its firearm model (`ak47_01.wav`, `desert_eagle_05.wav`) to support both coarse detection (Gunshot vs Other) and granular weapon forensics.

---

### 2. Panic Scream & Emergency Human Distress
* **Dataset:** *Human Screaming Detection Dataset*
* **Source:** Kaggle `redwud/screaming-detection`
* **Details:** Contains 862 verified positive human emergency screaming recordings captured in high distress conditions.
* **Role:** Essential for immediate critical alert generation in public security surveillance.

---

### 3. Aggression & Public Violence
* **Dataset:** *Audio-based Violence Detection Dataset*
* **Source:** Kaggle `fangfangz/audio-based-violence-detection-dataset`
* **Details:** Human vocal expressions of aggression: loud hostile shouting, verbal altercation, and brawl sounds recorded in mobile and public CCTV environments.

---

### 4. Person Asking for Help
* **Dataset:** *Threat Detection Audio Dataset*
* **Source:** Kaggle `mohithjain04/threat-detection-audio-dataset`
* **Details:** Voice-triggered distress detection dataset containing emergency calls, cries for help ("help me!", "bachao!"), and simulated crisis scenarios.

---

### 5. Glass Breaking (Tareeqa 1: DSP Augmentation)
* **Base Seed:** ESC-50 Class `glass_breaking` (40 real high-fidelity recordings of shattering glass, bottles, and windows).
* **Augmentation Rationale:** Glass shatter events have distinct sharp transient acoustic signatures. Rather than mixing unrelated noise, we expand the 40 seed clips into 400 distinct training instances using scientific DSP:
  - **Pitch Shift (+1.5, +2.0 semitones):** Simulates thin window pane glass and wine glasses.
  - **Pitch Shift (-1.5, -2.0 semitones):** Simulates thick tempered glass and heavy bottles.
  - **Time Stretch ($0.9\times, 1.1\times$):** Simulates slower cascading shatters vs sudden snaps.
  - **Distance Attenuation ($0.7\times$ gain):** Simulates acoustic sound propagation from 30 meters away.
  - **Ambient Noise Injection (15dB - 25dB SNR):** Simulates shatter occurring in realistic noisy street environments.
* **Output:** $40 \times 10 = \mathbf{400 \text{ training clips}}$.

---

### 6 & 7. Vehicle Horn & Alarm/Siren (Tareeqa 2: UrbanSound8K Extraction)
* **Dataset:** *UrbanSound8K*
* **Citation:** J. Salamon, C. Jacoby and J. P. Bello, *A Dataset and Taxonomy for Urban Sound Research*, 22nd ACM International Conference on Multimedia, Orlando, USA, Nov. 2014.
* **Extraction Methodology:**
  - UrbanSound8K is downloaded inside Google Colab's high-speed cloud container.
  - Files are filtered automatically by class identifier:
    - `ClassID 1` $\rightarrow$ **Car Horn** (**429 real recordings**)
    - `ClassID 8` $\rightarrow$ **Siren** (**929 real recordings**)
  - Only these filtered files are written to Google Drive; the remaining 6.8 GB temporary archive is discarded immediately from Colab RAM.

---

### 8. Machinery Fault
* **Base Seed:** ESC-50 classes: `engine`, `chainsaw`, `washing_machine` (160 real clips).
* **Expansion:** DSP noise injection and speed perturbation bring the mechanical fault profiles to 400 clips.

---

### 9 & 10. Animal Sound & Background Noise
* **Animal Sound:** ESC-50 classes: `dog`, `cat`, `rooster`, `crow`, `cow`, `frog`, `chirping_birds` (**480 real clips**).
* **Background Noise:** ESC-50 classes: `rain`, `sea_waves`, `wind`, `crackling_fire`, `thunderstorm`, `footsteps` (**320 real clips + augmented**).

---

## 3. Storage Architecture: 5TB Google Drive + Zero Laptop Footprint

```
Google Drive: MyDrive/
└── SonicSentinel_AI/
    ├── DATASET_SOURCES.md                           <-- This documentation file
    ├── 01_google_drive_dataset_accumulator.ipynb     <-- Automated download & slicing pipeline
    ├── 02_model_training_comparison.ipynb            <-- Random Forest vs XGBoost vs 2D-CNN
    └── dataset/
        ├── gunshot/               (851 clips — AK-47, Desert Eagle, M16, MP5, etc.)
        ├── panic_scream/          (862 clips — Emergency screaming)
        ├── aggression/            (400 clips — Hostile shouting & violence)
        ├── person_asking_help/    (400 clips — Distress cries & help calls)
        ├── glass_breaking/        (400 clips — 40 seed + 360 DSP augmented)
        ├── vehicle_horn/          (429 clips — UrbanSound8K Class 1)
        ├── alarm_siren/           (929 clips — UrbanSound8K Class 8)
        ├── machinery_fault/       (400 clips — ESC-50 + DSP augmented)
        ├── animal_sound/          (480 clips — ESC-50)
        └── background_noise/      (400 clips — ESC-50)
```

**Total Dataset Size:** ~4,500+ audio clips (~2.5 GB)  
**Laptop C: Drive Impact:** **0 MB** (Streamed via Google Cloud)  
**Colab Training Runtime:** ~8 to 12 minutes on free T4 GPU.
