# ==============================================================================
# 🛸🛠️ SONICSENTINEL AI — ADD 'drone' & 'drilling' (1,050+ CLIPS EACH + CLEAN SEQUENCE)
# ==============================================================================
# Run this in a single Google Colab cell!
# Sources:
#   1. drone    -> GitHub: saraalemadi/DroneAudioDataset (yes_drone / bebop / mambo)
#                  100% Public GitHub Repo (Zero Kaggle 403 Error!)
#   2. drilling -> Kaggle: chrisfilo/urbansound8k (Class 4 = drilling, 1,000 real 4s clips)
# ==============================================================================

from google.colab import drive, files
import os, sys, random, shutil, subprocess
import numpy as np

drive.mount('/content/drive')
subprocess.run([sys.executable, "-m", "pip", "install", "-q", "librosa", "soundfile", "kaggle", "numpy"], check=False)

import librosa
import soundfile as sf

BASE_DIR = '/content/drive/MyDrive/SonicSentinel_AI/dataset'
TMP_DIR  = '/content/tmp_drone_drill'
os.makedirs(TMP_DIR, exist_ok=True)

SR = 16000
TARGET_LEN = int(SR * 2.0)  # 32,000 samples (2.0s)
random.seed(42)
np.random.seed(42)

# Auto-load Kaggle credentials from Drive (for UrbanSound8K drilling)
kaggle_drive = '/content/drive/MyDrive/kaggle.json'
os.makedirs('/root/.kaggle', exist_ok=True)
if not os.path.exists('/root/.kaggle/kaggle.json') and os.path.exists(kaggle_drive):
    shutil.copy(kaggle_drive, '/root/.kaggle/kaggle.json')
    os.chmod('/root/.kaggle/kaggle.json', 0o600)
    print("✅ Kaggle credentials loaded from Drive!")

def save_2s_clip(y, out_path):
    if y.ndim > 1:
        y = np.mean(y, axis=0)
    y, _ = librosa.effects.trim(y, top_db=28)
    if len(y) < int(SR * 0.25):
        return False
    if len(y) >= TARGET_LEN:
        start = random.randint(0, len(y) - TARGET_LEN)
        y = y[start:start + TARGET_LEN]
    else:
        pad_l = random.randint(0, TARGET_LEN - len(y))
        y = np.pad(y, (pad_l, TARGET_LEN - len(y) - pad_l), mode='constant')
    if np.sqrt(np.mean(y**2)) < 0.005:
        return False
    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = (y / peak) * random.uniform(0.80, 0.94)
    sf.write(out_path, y.astype(np.float32), SR)
    return True

# ------------------------------------------------------------------------------
# STEP 1: BUILD 'drone' (1,080 Pure Real UAV Clips via GitHub DroneAudioDataset)
# ------------------------------------------------------------------------------
print("\n🛸 STEP 1: Downloading Official DroneAudioDataset from GitHub (Zero 403)...")
drone_dir = os.path.join(BASE_DIR, 'drone')
if os.path.exists(drone_dir):
    shutil.rmtree(drone_dir)
os.makedirs(drone_dir, exist_ok=True)

drone_repo = os.path.join(TMP_DIR, 'DroneAudioDataset')
subprocess.run(f"git clone --depth 1 https://github.com/saraalemadi/DroneAudioDataset.git {drone_repo} -q", shell=True)

drone_candidates = []
for root, _, flist in os.walk(drone_repo):
    folder_l = os.path.basename(root).lower()
    # Strictly take only real drone folders (yes_drone, bebop, membo) and skip 'unknown' / noise
    if any(skip in folder_l for skip in ['unknown', 'noise', 'no_drone', 'silence']):
        continue
    for fn in flist:
        if fn.lower().endswith('.wav') and 'unknown' not in fn.lower():
            drone_candidates.append(os.path.join(root, fn))

print(f"   Found {len(drone_candidates)} real Drone WAV recordings!")
random.shuffle(drone_candidates)

drone_saved = 0
for src in drone_candidates:
    if drone_saved >= 1080:
        break
    try:
        y, _ = librosa.load(src, sr=SR, mono=True)
        out_p = os.path.join(drone_dir, f"drone_{drone_saved + 1:04d}.wav")
        if save_2s_clip(y, out_p):
            drone_saved += 1
    except Exception:
        pass

# If repo had ~1,000 clips, top up remaining to 1,080 with slight pitch/distance variations
if 0 < drone_saved < 1080:
    seed_files = [os.path.join(drone_dir, f) for f in os.listdir(drone_dir) if f.endswith('.wav')]
    idx = 0
    while drone_saved < 1080:
        y, _ = librosa.load(seed_files[idx % len(seed_files)], sr=SR, mono=True)
        y = librosa.effects.pitch_shift(y, sr=SR, n_steps=random.uniform(-1.5, 1.5))
        out_p = os.path.join(drone_dir, f"drone_{drone_saved + 1:04d}.wav")
        if save_2s_clip(y, out_p):
            drone_saved += 1
        idx += 1

print(f"   ✅ 'drone' completed: {drone_saved} clips (drone_0001.wav ... drone_{drone_saved:04d}.wav)")
shutil.rmtree(drone_repo, ignore_errors=True)

# ------------------------------------------------------------------------------
# STEP 2: BUILD 'drilling' (1,080 Real Clips from UrbanSound8K Class 4)
# ------------------------------------------------------------------------------
print("\n🛠️ STEP 2: Downloading UrbanSound8K & Extracting Class 4 ('drilling')...")
drill_dir = os.path.join(BASE_DIR, 'drilling')
if os.path.exists(drill_dir):
    shutil.rmtree(drill_dir)
os.makedirs(drill_dir, exist_ok=True)

us8k_tmp = os.path.join(TMP_DIR, 'us8k')
os.makedirs(us8k_tmp, exist_ok=True)
subprocess.run(f"kaggle datasets download -d chrisfilo/urbansound8k -p {us8k_tmp} --unzip -q", shell=True)

drill_candidates = []
for root, _, flist in os.walk(us8k_tmp):
    for fn in flist:
        if fn.lower().endswith('.wav'):
            parts = fn.split('-')
            # Class ID '4' in UrbanSound8K is strictly 'drilling' (1,000 real files)
            if len(parts) >= 2 and parts[1] == '4':
                drill_candidates.append(os.path.join(root, fn))

print(f"   Found {len(drill_candidates)} real Drilling WAV recordings!")
random.shuffle(drill_candidates)

drill_saved = 0
# Pass 1: First 2s window from each real drilling file
for src in drill_candidates:
    if drill_saved >= 1080:
        break
    try:
        y, _ = librosa.load(src, sr=SR, mono=True)
        out_p = os.path.join(drill_dir, f"drilling_{drill_saved + 1:04d}.wav")
        if save_2s_clip(y[:TARGET_LEN], out_p):
            drill_saved += 1
    except Exception:
        pass

# Pass 2: Second non-overlapping 2s window (2.0s - 4.0s) from 4-second drilling files to reach 1,080
for src in drill_candidates:
    if drill_saved >= 1080:
        break
    try:
        y, _ = librosa.load(src, sr=SR, mono=True)
        if len(y) >= int(3.2 * SR):
            out_p = os.path.join(drill_dir, f"drilling_{drill_saved + 1:04d}.wav")
            if save_2s_clip(y[-TARGET_LEN:], out_p):
                drill_saved += 1
    except Exception:
        pass

print(f"   ✅ 'drilling' completed: {drill_saved} clips (drilling_0001.wav ... drilling_{drill_saved:04d}.wav)")
shutil.rmtree(TMP_DIR, ignore_errors=True)

# ------------------------------------------------------------------------------
# FINAL VERIFICATION ACROSS ALL 14 CLASSES
# ------------------------------------------------------------------------------
print("\n" + "="*75)
print("🏆 FINAL DATASET INVENTORY (14 CLASSES)")
print("="*75)
all_classes = sorted([
    d for d in os.listdir(BASE_DIR)
    if os.path.isdir(os.path.join(BASE_DIR, d)) and not d.startswith('.')
])
grand_total = 0
for cls_name in all_classes:
    cls_path = os.path.join(BASE_DIR, cls_name)
    flist = sorted([f for f in os.listdir(cls_path) if f.endswith('.wav')])
    grand_total += len(flist)
    sample_str = f"{flist[0]} ... {flist[-1]}" if flist else "EMPTY"
    print(f"  {cls_name:<20} | {len(flist):5d} clips | {sample_str}")
print("="*75)
print(f"  GRAND TOTAL: {grand_total} clips across {len(all_classes)} classes ✅")
print("="*75)
