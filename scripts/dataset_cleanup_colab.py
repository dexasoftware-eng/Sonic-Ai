"""
dataset_cleanup_colab.py
=========================
Colab mein 5 cells paste karo — ek ek run karo.

Actions:
  CELL 1 — Setup
  CELL 2 — Remove: fireworks + church_bells
  CELL 3 — Merge: helicopter + airplane + vacuum_cleaner → background_noise
  CELL 4 — Augment: crying_baby (40 → 200) + laughing (40 → 200)
  CELL 5 — Final verification of all classes
"""

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 1 — Setup (run first)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
from google.colab import drive
drive.mount('/content/drive')

!pip install -q librosa soundfile numpy

import os, random, shutil
import numpy as np
import librosa
import soundfile as sf

BASE  = '/content/drive/MyDrive/SonicSentinel_AI/dataset'
SR    = 16000
LEN   = SR * 2   # 32000 samples = 2 seconds
random.seed(42)
np.random.seed(42)

def aug_save(y, out_path, variant):
    \"\"\"Apply one DSP augmentation and save as 2s clip.\"\"\"
    y = y.copy()
    if variant == 0:   # pitch shift up
        y = librosa.effects.pitch_shift(y, sr=SR, n_steps=random.uniform(1.0, 3.5))
    elif variant == 1: # pitch shift down
        y = librosa.effects.pitch_shift(y, sr=SR, n_steps=random.uniform(-3.5, -1.0))
    elif variant == 2: # time stretch slower
        rate = random.uniform(0.80, 0.93)
        y = librosa.effects.time_stretch(y, rate=rate)
    elif variant == 3: # time stretch faster
        rate = random.uniform(1.07, 1.22)
        y = librosa.effects.time_stretch(y, rate=rate)
    elif variant == 4: # gaussian noise
        y = y + np.random.normal(0, random.uniform(0.004, 0.012), len(y)).astype(np.float32)
    elif variant == 5: # gain scale
        y = y * random.uniform(0.55, 0.90)

    # Crop or pad to exactly 2s
    if len(y) >= LEN:
        start = random.randint(0, len(y) - LEN)
        y = y[start:start + LEN]
    else:
        pad = LEN - len(y)
        y = np.pad(y, (random.randint(0, pad), 0), mode='constant')[:LEN]

    # Normalize
    peak = np.max(np.abs(y))
    if peak > 1e-6:
        y = (y / peak) * random.uniform(0.80, 0.93)

    sf.write(out_path, y.astype(np.float32), SR)

print("✅ Setup complete!")
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 2 — Remove fireworks + church_bells entirely
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
TO_REMOVE = ['fireworks', 'church_bells']

for cls in TO_REMOVE:
    cls_path = os.path.join(BASE, cls)
    if os.path.exists(cls_path):
        files = os.listdir(cls_path)
        shutil.rmtree(cls_path)
        print(f"🗑  Removed class '{cls}' — {len(files)} files deleted")
    else:
        print(f"⚠️  '{cls}' not found (already removed?)")

print(f"\\n✅ Done — {len(TO_REMOVE)} classes removed from dataset")
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 3 — Merge helicopter + airplane + vacuum_cleaner → background_noise
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
TO_MERGE = ['helicopter', 'airplane', 'vacuum_cleaner']
bg_dir   = os.path.join(BASE, 'background_noise')
os.makedirs(bg_dir, exist_ok=True)

total_moved = 0
for cls in TO_MERGE:
    cls_path = os.path.join(BASE, cls)
    if not os.path.exists(cls_path):
        print(f"⚠️  '{cls}' not found, skipping")
        continue
    files = [f for f in os.listdir(cls_path) if f.endswith('.wav')]
    moved = 0
    for f in files:
        src  = os.path.join(cls_path, f)
        # Rename to avoid collision: prefix with class name
        dst  = os.path.join(bg_dir, f'bg_{cls}_{f}')
        shutil.move(src, dst)
        moved += 1
    shutil.rmtree(cls_path)   # remove now-empty folder
    total_moved += moved
    print(f"  ✅ Moved {moved} clips from '{cls}' → background_noise/")

bg_total = len([f for f in os.listdir(bg_dir) if f.endswith('.wav')])
print(f"\\n  background_noise total: {bg_total} clips (was 400, added {total_moved})")
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 4 — Augment crying_baby + laughing → 200 clips each
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
TARGET = 200   # each class augment to this many clips

for cls in ['crying_baby', 'laughing']:
    cls_dir  = os.path.join(BASE, cls)
    originals = sorted([f for f in os.listdir(cls_dir) if f.endswith('.wav')])
    current   = len(originals)
    needed    = TARGET - current

    print(f"\\n━━━ {cls}: {current} → {TARGET} (need {needed} augmented clips) ━━━")

    if needed <= 0:
        print(f"  Already has {current} clips, no augmentation needed.")
        continue

    # Load all originals into memory
    waves = []
    for fn in originals:
        try:
            y, sr = librosa.load(os.path.join(cls_dir, fn), sr=SR, mono=True)
            if len(y) >= LEN:
                y = y[:LEN]
            else:
                y = np.pad(y, (0, LEN - len(y)), mode='constant')
            waves.append(y)
        except:
            pass

    if not waves:
        print(f"  ❌ No valid audio loaded for {cls}")
        continue

    added = 0
    variant_cycle = 0
    while added < needed:
        # Round-robin through originals
        base_wave = waves[added % len(waves)]
        out_name  = os.path.join(cls_dir, f'aug_{cls}_{added+1:04d}.wav')
        try:
            aug_save(base_wave, out_name, variant_cycle % 6)
            added += 1
            variant_cycle += 1
        except Exception as e:
            print(f"  ⚠️  aug failed: {e}")
            variant_cycle += 1
            continue

    final = len([f for f in os.listdir(cls_dir) if f.endswith('.wav')])
    print(f"  ✅ {cls}: {current} originals + {added} augmented = {final} total clips")
"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CELL 5 — Final verification of ALL classes
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""
classes = sorted(os.listdir(BASE))
total_clips = 0

print("=" * 60)
print("  FINAL DATASET VERIFICATION")
print("=" * 60)

core_10 = {
    'aggression', 'alarm_siren', 'animal_sound', 'background_noise',
    'glass_breaking', 'gunshot', 'machinery_fault', 'panic_scream',
    'person_asking_help', 'vehicle_horn'
}

print("\\n  [CORE 10 CLASSES]")
for cls in sorted(core_10):
    p = os.path.join(BASE, cls)
    if not os.path.isdir(p): continue
    files = [f for f in os.listdir(p) if f.endswith('.wav')]
    orig  = [f for f in files if not f.startswith('aug_')]
    aug   = [f for f in files if f.startswith('aug_')]
    total_clips += len(files)
    print(f"  {cls:<25} {len(files):>5} clips  (orig:{len(orig)}, aug:{len(aug)})")

print("\\n  [AMBIENT CLASSES]")
for cls in sorted(classes):
    if cls in core_10: continue
    p = os.path.join(BASE, cls)
    if not os.path.isdir(p): continue
    files = [f for f in os.listdir(p) if f.endswith('.wav')]
    orig  = [f for f in files if not f.startswith('aug_')]
    aug   = [f for f in files if f.startswith('aug_')]
    total_clips += len(files)
    print(f"  {cls:<25} {len(files):>5} clips  (orig:{len(orig)}, aug:{len(aug)})")

print("=" * 60)
print(f"  GRAND TOTAL: {total_clips} clips across {len(classes)} classes")
print("=" * 60)
"""
