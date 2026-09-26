"""
aggression_rebuild_colab.py
============================
Google Colab mein run karo — har section ek Colab cell ki tarah hai.
Steps:
  1. Drive mount + setup
  2. Bad files delete karo
  3. fangfangz dataset slice karo (2s windows)
  4. RAVDESS + CREMA-D angry clips extract karo
  5. Final report
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 1 — Mount Drive + Install libs
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from google.colab import drive
drive.mount('/content/drive')

!pip install -q librosa soundfile numpy scipy

import os, math, random, shutil
import numpy as np
import librosa
import soundfile as sf

BASE_DIR    = '/content/drive/MyDrive/SonicSentinel_AI/dataset'
agg_dir     = os.path.join(BASE_DIR, 'aggression')
TARGET_SR   = 16000
TARGET_SECS = 2
TARGET_LEN  = TARGET_SR * TARGET_SECS   # 32000 samples
random.seed(42)
np.random.seed(42)

def standardize_and_save(y, sr, out_path):
    if sr != TARGET_SR:
        y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)
    if y.ndim > 1:
        y = np.mean(y, axis=0)
    y, _ = librosa.effects.trim(y, top_db=28)
    if len(y) >= TARGET_LEN:
        start = random.randint(0, len(y) - TARGET_LEN)
        y = y[start:start + TARGET_LEN]
    else:
        pad_l = random.randint(0, TARGET_LEN - len(y))
        y = np.pad(y, (pad_l, TARGET_LEN - len(y) - pad_l), mode='constant')
    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = (y / peak) * random.uniform(0.80, 0.93)
    sf.write(out_path, y.astype(np.float32), TARGET_SR)

print("✅ Setup complete!")
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 2 — Delete garbage files
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
print("━━━ Removing bad files ━━━")
removed_nv = removed_long = 0

for f in list(os.listdir(agg_dir)):
    fpath = os.path.join(agg_dir, f)
    if f.startswith('aggression_noviolence'):
        gb = os.path.getsize(fpath) / (1024**3)
        os.remove(fpath)
        print(f"  🗑  {f}  ({gb:.2f} GB freed)")
        removed_nv += 1
    elif f.startswith('aggression_angry') and os.path.getsize(fpath) > 500_000:
        os.remove(fpath)   # raw unsliced long recording
        removed_long += 1

print(f"  ✅ Removed {removed_nv} noviolence files + {removed_long} unsliced angry files")
print(f"  Clean clips now: {len([f for f in os.listdir(agg_dir) if f.endswith('.wav')])}")
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 3 — Download fangfangz & slice into 2s windows
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
print("━━━ Downloading fangfangz aggression dataset ━━━")
os.makedirs('/content/tmp_agg_long', exist_ok=True)
!kaggle datasets download -d fangfangz/audio-dataset-for-detecting-aggression-in-speech \
    -p /content/tmp_agg_long --unzip -q

long_files = []
for root, _, files_list in os.walk('/content/tmp_agg_long'):
    for fn in files_list:
        if fn.lower().endswith(('.wav', '.mp3', '.flac')):
            # Only pick aggressive files — skip noviolence-labelled ones
            if 'nonv' not in fn.lower() and 'non_v' not in fn.lower():
                long_files.append(os.path.join(root, fn))

print(f"Found {len(long_files)} aggressive source audio files")

STRIDE_SEC = 1.5    # 1.5s hop → 0.5s overlap between windows
MIN_RMS    = 0.012  # skip silent windows

slice_count = 0
current_agg = len([f for f in os.listdir(agg_dir) if f.endswith('.wav')])

for src in long_files:
    try:
        y, sr = librosa.load(src, sr=TARGET_SR, mono=True)
        total_secs = len(y) / TARGET_SR
        n_windows = max(1, int(math.floor((total_secs - TARGET_SECS) / STRIDE_SEC)) + 1)

        for w in range(n_windows):
            start = int(w * STRIDE_SEC * TARGET_SR)
            window = y[start : start + TARGET_LEN]
            if len(window) < TARGET_LEN:
                break
            if np.sqrt(np.mean(window**2)) < MIN_RMS:
                continue  # skip near-silent window
            peak = np.max(np.abs(window))
            if peak > 1e-6:
                window = (window / peak) * random.uniform(0.80, 0.93)
            out_name = os.path.join(
                agg_dir,
                f'aggression_angry_slice_{current_agg + slice_count + 1:05d}.wav'
            )
            sf.write(out_name, window.astype(np.float32), TARGET_SR)
            slice_count += 1
    except Exception as e:
        print(f"  ⚠️ Skipping {os.path.basename(src)}: {e}")

print(f"✅ Sliced {slice_count} x 2s clips from fangfangz audio")
shutil.rmtree('/content/tmp_agg_long', ignore_errors=True)
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 4 — RAVDESS + CREMA-D angry actor clips
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
print("━━━ Downloading RAVDESS + CREMA-D ━━━")
os.makedirs('/content/tmp_agg_actors', exist_ok=True)
!kaggle datasets download -d uwrfkaggler/ravdess-emotional-speech-audio \
    -p /content/tmp_agg_actors --unzip -q
!kaggle datasets download -d ejlok1/cremad \
    -p /content/tmp_agg_actors --unzip -q

actor_candidates = []
for root, _, files_list in os.walk('/content/tmp_agg_actors'):
    for fn in files_list:
        if not fn.lower().endswith('.wav'):
            continue
        # RAVDESS format: 03-01-05-01-01-01-01.wav → part[2]=='05' means angry
        parts = os.path.splitext(fn)[0].split('-')
        ravdess_angry = len(parts) >= 3 and parts[2] == '05'
        # CREMA-D format: 1001_DFA_ANG_XX.wav
        cremad_angry  = '_ANG_' in fn.upper()
        if ravdess_angry or cremad_angry:
            actor_candidates.append(os.path.join(root, fn))

print(f"Found {len(actor_candidates)} angry actor clips")

current_agg = len([f for f in os.listdir(agg_dir) if f.endswith('.wav')])
actor_added = 0
random.shuffle(actor_candidates)

for src_path in actor_candidates:
    try:
        y, sr = librosa.load(src_path, sr=TARGET_SR, mono=True)
        out_name = os.path.join(
            agg_dir,
            f'aggression_real_actor_{current_agg + actor_added + 1:04d}.wav'
        )
        standardize_and_save(y, sr, out_name)
        actor_added += 1
    except Exception:
        pass

print(f"✅ Added {actor_added} RAVDESS + CREMA-D angry clips")
shutil.rmtree('/content/tmp_agg_actors', ignore_errors=True)
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 5 — Final Report
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
all_agg = [f for f in os.listdir(agg_dir) if f.endswith('.wav')]
sliced  = [f for f in all_agg if 'slice' in f]
actors  = [f for f in all_agg if 'real_actor' in f]
size_mb = sum(os.path.getsize(os.path.join(agg_dir, f)) for f in all_agg) / (1024**2)

print("=" * 55)
print("   AGGRESSION DATASET — FINAL REPORT")
print("=" * 55)
print(f"  Sliced windows (fangfangz):      {len(sliced):>5}")
print(f"  Actor clips (RAVDESS+CREMA-D):   {len(actors):>5}")
print(f"  ─────────────────────────────────────")
print(f"  TOTAL clips:                     {len(all_agg):>5}")
print(f"  Total size:                      {size_mb:.1f} MB")
print(f"  Format: 16 kHz | mono | 2s each    ✅")
print("=" * 55)
"""
