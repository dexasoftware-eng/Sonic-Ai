# 🛡️ SonicSentinel AI — Complete Dataset Provenance, Sources & Scale Breakdown
### Enterprise Sovereign Acoustic Intelligence Platform
**Total Scale:** **15,798 Audio Clips** across **14 Sound Classes** (2.60 GB on Google Drive)  
**Standard Audio Specifications:** 16,000 Hz, 1-Channel Mono, 2.0s Duration (32,000 samples), Peak Amplitude Normalized $[-1.0, 1.0]$.

---

## 📊 Master Dataset Inventory (All 14 Classes)

| # | Class Name | Exact Clips Count | Primary Dataset Source | Source Identifier / Slug / Repository | Acoustic Description & Role |
|:--|:---|:---:|:---|:---|:---|
| **1** | **`aggression`** | **1,924** | Audio-based Violence Detection Dataset + Real Altercations | Kaggle: `fangfangz/audio-based-violence-detection-dataset` | Vocal altercations, screaming arguments, physical fighting sounds, shouting, angry human vocal attacks. |
| **2** | **`panic_scream`** | **1,583** | Audio Dataset of Scream & Non-Scream | Kaggle: `aananehsansiam/audio-dataset-of-scream-and-non-scream` | Real human emergency screams, distress shrieks, terror calls, fear vocalizations. |
| **3** | **`gunshot`** | **1,180** | Gunshot Audio Dataset (8 Weapon Profiles) | Kaggle: `emrahaydemr/gunshot-audio-dataset` | Real ballistic gunshots across 8 firearms: AK-47, Desert Eagle, M16, MP5, Glock, Shotgun, Sniper, Revolver. |
| **4** | **`animal_sound`** | **1,102** | ESC-50 + Clean Domestic & Wildlife Animals | Karol J. Piczak (ESC-50) + Kaggle Animal Sound Dataset | Filtered pure animal sounds: +150 Dogs (barking, growling), +150 Cats (meowing, hissing), Lion, Elephant, Horse, Cow, Sheep, Rooster, Crow. |
| **5** | **`crying_baby`** | **1,082** | Donate-a-Cry Database + Infant Audio | Kaggle: Donate-a-Cry Corpus + Infant Soundscapes | Human baby crying (hunger, pain, discomfort). Acts as a primary guard class to prevent scream false alarms. |
| **6** | **`drilling`** | **1,080** | UrbanSound8K (Class 4) + Industrial Audio | Kaggle: `chrisfilo/urbansound8k` (Drilling Class 4) | High-speed electric drills, rotary hammer drills, concrete drilling, impact drivers. |
| **7** | **`drone`** | **1,080** | DroneAudioDataset + UAV Acoustic Dataset | GitHub: `DroneAudioDataset` + Mendeley Data UAV Acoustics | Small, medium, and multi-rotor UAV propeller hums, quadcopter motor pitch shifts, drone aerial passes. |
| **8** | **`background_noise`** | **1,080** | ESC-50 Environmental Benchmarks | Karol J. Piczak (ESC-50) + Ambient Field Recordings | Rain, ambient wind, thunder, city murmurs, indoor hum, airflow. Critical negative class. |
| **9** | **`machinery_fault`** | **1,060** | Industrial Machine Fault Audio + ESC-50 | Karol J. Piczak (ESC-50: engine, chainsaw, washing machine) | Abnormal motor vibrations, bearing friction, unaligned rotor faults, industrial pump failures. |
| **10** | **`glass_breaking`** | **1,050** | ESC-50 Glass Breaking + Window Shatter Recordings | Karol J. Piczak (ESC-50 Class 43) + Sound Effects Library | High-frequency window shatters, glass bottle fracturing, burglar entry impacts. Pure glass without tin/can clicks. |
| **11** | **`laughing`** | **1,050** | Human Vocal Emotional Corpus + ESC-50 | Karol J. Piczak (ESC-50 Class 26) + Vocal Soundscapes | Natural human laughter and giggles. Acts as an emotional guard class against false positive aggression alerts. |
| **12** | **`vehicle_horn`** | **1,050** | UrbanSound8K (Class 1: Car Horn) + ESC-50 | Kaggle: `chrisfilo/urbansound8k` (Class 1) + ESC-50 | Real automotive horn bursts, truck blast horns, emergency vehicle honking. |
| **13** | **`alarm_siren`** | **1,009** | UrbanSound8K (Class 8: Siren) + ESC-50 | Kaggle: `chrisfilo/urbansound8k` (Class 8: Siren) + ESC-50 | Police cruisers, ambulances, fire brigade sirens, building fire alarms, burglar security klaxons. |
| **14** | **`person_asking_help`** | **468** | Threat Detection Audio & Real Distress Calls | Kaggle: `mohithjain04/threat-detection-audio-dataset` | Clear spoken English distress phrases: *"Help me"*, *"Please help"*, *"Somebody call police"*, *"Emergency"*. Preserved in natural count with balanced loss weights. |

---

## 🎯 Total Scale & Volume Summary:
- **Total Audios:** **15,798 Verified Audio WAV Files**
- **Dataset Storage Size:** **2.60 GB**
- **Storage Location:** Google Drive Cloud Cluster (`MyDrive/SonicSentinel_AI/dataset/`)
- **Stratified Split Distribution (70% / 15% / 15%):**
  - **Training Split (70%):** `11,058 clips`
  - **Validation Split (15%):** `2,370 clips`
  - **Test Split (Unseen 15%):** `2,370 clips`
- **Champion Evaluation Accuracy on Unseen Test Split:** **93.04% (Deep 2D-CNN)**
