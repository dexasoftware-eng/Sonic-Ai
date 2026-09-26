"""
Aggression Dataset Rebuilder
=============================
Downloads RAVDESS + CREMA-D from Kaggle, extracts ONLY angry/conflict clips,
standardizes each to 2s / 16kHz / mono WAV, and saves to the Drive dataset folder.

Also removes the bad aggression_noviolence_* files.

Usage:
    python scripts/rebuild_aggression_dataset.py --kaggle-json path/to/kaggle.json
    OR: place kaggle.json in %USERPROFILE%\.kaggle\kaggle.json and run without args
"""

import os
import sys
import shutil
import random
import argparse
import tempfile
import zipfile

import numpy as np
import soundfile as sf

try:
    import librosa
except ImportError:
    print("ERROR: librosa not installed. Run: pip install librosa")
    sys.exit(1)

# ─── CONFIG ──────────────────────────────────────────────────────────────────
DATASET_DIR   = r"G:\My Drive\SonicSentinel_AI\dataset\aggression"
TMP_DIR       = r"C:\Users\DELL\Desktop\SonicAi\data\tmp_aggression_rebuild"
TARGET_SR     = 16000
TARGET_SECS   = 2
TARGET_LEN    = TARGET_SR * TARGET_SECS  # 32000 samples
RANDOM_SEED   = 42

random.seed(RANDOM_SEED)
np.random.seed(RANDOM_SEED)

# ─── RAVDESS ANGER DETECTION ─────────────────────────────────────────────────
# RAVDESS filename format: 03-01-05-01-01-01-01.wav
# Position 3 (0-indexed 2) = emotion: 05 = angry, 06 = fearful, etc.
def is_ravdess_angry(filename: str) -> bool:
    parts = os.path.splitext(filename)[0].split("-")
    if len(parts) >= 3:
        return parts[2] == "05"  # emotion code 05 = angry
    return False

# ─── CREMA-D ANGER DETECTION ─────────────────────────────────────────────────
# CREMA-D filename format: 1001_DFA_ANG_XX.wav
# ANG = angry, FEA = fear, DIS = disgust, etc.
def is_cremad_angry(filename: str) -> bool:
    upper = filename.upper()
    return "_ANG_" in upper

# ─── AUDIO STANDARDIZER ──────────────────────────────────────────────────────
def standardize_and_save(y: np.ndarray, sr: int, out_path: str) -> bool:
    """Resample → mono → trim silence → crop/pad to 2s → normalize → save."""
    try:
        # Resample if needed
        if sr != TARGET_SR:
            y = librosa.resample(y, orig_sr=sr, target_sr=TARGET_SR)

        # Ensure mono
        if y.ndim > 1:
            y = np.mean(y, axis=0)

        # Trim leading/trailing silence
        y, _ = librosa.effects.trim(y, top_db=28)

        # Crop or pad to exactly TARGET_LEN samples
        if len(y) >= TARGET_LEN:
            # Take a random 2s window from within the clip
            start = random.randint(0, len(y) - TARGET_LEN)
            y = y[start:start + TARGET_LEN]
        else:
            pad_left = random.randint(0, TARGET_LEN - len(y))
            pad_right = TARGET_LEN - len(y) - pad_left
            y = np.pad(y, (pad_left, pad_right), mode="constant")

        # Peak normalize to 0.85
        peak = np.max(np.abs(y))
        if peak > 1e-6:
            y = (y / peak) * random.uniform(0.80, 0.92)

        sf.write(out_path, y.astype(np.float32), TARGET_SR)
        return True
    except Exception as e:
        print(f"  ⚠️  Failed to process {out_path}: {e}")
        return False


# ─── STEP 0: CLEAN BAD FILES ─────────────────────────────────────────────────
def clean_bad_files():
    print("\n━━━ STEP 0: Remove bad aggression_noviolence files ━━━")
    removed = 0
    for f in os.listdir(DATASET_DIR):
        if f.startswith("aggression_noviolence"):
            path = os.path.join(DATASET_DIR, f)
            size_gb = os.path.getsize(path) / (1024**3)
            os.remove(path)
            print(f"  🗑  Deleted: {f}  ({size_gb:.2f} GB)")
            removed += 1
    print(f"  ✅ Removed {removed} noviolence files\n")

    # Also remove unprocessed long angry files (> 5 MB = more than ~1 minute)
    long_removed = 0
    for f in os.listdir(DATASET_DIR):
        if f.startswith("aggression_angry"):
            path = os.path.join(DATASET_DIR, f)
            size_mb = os.path.getsize(path) / (1024**2)
            if size_mb > 0.5:  # longer than ~5 seconds
                os.remove(path)
                long_removed += 1
    print(f"  🗑  Removed {long_removed} unprocessed long aggression_angry files\n")


# ─── STEP 1: SETUP KAGGLE ────────────────────────────────────────────────────
def setup_kaggle(kaggle_json_path: str = None):
    kaggle_dir = os.path.join(os.path.expanduser("~"), ".kaggle")
    os.makedirs(kaggle_dir, exist_ok=True)
    dest = os.path.join(kaggle_dir, "kaggle.json")

    if kaggle_json_path and os.path.exists(kaggle_json_path):
        shutil.copy(kaggle_json_path, dest)
        print(f"  ✅ Copied kaggle.json from {kaggle_json_path}")
    elif os.path.exists(dest):
        print(f"  ✅ kaggle.json already at {dest}")
    else:
        print("\n  ❌ kaggle.json not found!")
        print("  Please:")
        print("  1. Go to https://www.kaggle.com/settings/account")
        print("  2. Click 'Create New Token' under 'API' section")
        print("  3. Download kaggle.json")
        print(f"  4. Place it at: {dest}")
        print("  OR run: python scripts/rebuild_aggression_dataset.py --kaggle-json C:\\path\\to\\kaggle.json")
        sys.exit(1)

    # Secure permissions
    try:
        import stat
        os.chmod(dest, stat.S_IRUSR | stat.S_IWUSR)
    except Exception:
        pass


# ─── STEP 2: DOWNLOAD + EXTRACT RAVDESS ─────────────────────────────────────
def process_ravdess(out_dir: str) -> int:
    print("\n━━━ STEP 2: Download & Process RAVDESS Angry Clips ━━━")
    tmp = os.path.join(TMP_DIR, "ravdess")
    os.makedirs(tmp, exist_ok=True)

    print("  ⏬ Downloading RAVDESS (Emotional Speech Audio)...")
    os.system(f'"{sys.executable}" -m kaggle datasets download -d uwrfkaggler/ravdess-emotional-speech-audio -p "{tmp}" --unzip -q')

    angry_clips = []
    for root, _, files in os.walk(tmp):
        for fn in files:
            if fn.lower().endswith(".wav") and is_ravdess_angry(fn):
                angry_clips.append(os.path.join(root, fn))

    print(f"  Found {len(angry_clips)} RAVDESS angry clips")

    already = len([f for f in os.listdir(out_dir) if f.endswith(".wav")])
    added = 0
    for src in angry_clips:
        idx = already + added + 1
        out_name = os.path.join(out_dir, f"aggression_ravdess_{idx:04d}.wav")
        y, sr = librosa.load(src, sr=TARGET_SR, mono=True)
        if standardize_and_save(y, sr, out_name):
            added += 1

    print(f"  ✅ Added {added} RAVDESS angry clips → aggression/")
    return added


# ─── STEP 3: DOWNLOAD + EXTRACT CREMA-D ─────────────────────────────────────
def process_cremad(out_dir: str) -> int:
    print("\n━━━ STEP 3: Download & Process CREMA-D Angry Clips ━━━")
    tmp = os.path.join(TMP_DIR, "cremad")
    os.makedirs(tmp, exist_ok=True)

    print("  ⏬ Downloading CREMA-D...")
    os.system(f'"{sys.executable}" -m kaggle datasets download -d ejlok1/cremad -p "{tmp}" --unzip -q')

    angry_clips = []
    for root, _, files in os.walk(tmp):
        for fn in files:
            if fn.lower().endswith(".wav") and is_cremad_angry(fn):
                angry_clips.append(os.path.join(root, fn))

    print(f"  Found {len(angry_clips)} CREMA-D angry clips")

    already = len([f for f in os.listdir(out_dir) if f.endswith(".wav")])
    added = 0
    for src in angry_clips:
        idx = already + added + 1
        out_name = os.path.join(out_dir, f"aggression_cremad_{idx:04d}.wav")
        try:
            y, sr = librosa.load(src, sr=TARGET_SR, mono=True)
            if standardize_and_save(y, sr, out_name):
                added += 1
        except Exception as e:
            print(f"  ⚠️  Skipping {fn}: {e}")

    print(f"  ✅ Added {added} CREMA-D angry clips → aggression/")
    return added


# ─── STEP 4: FINAL REPORT ────────────────────────────────────────────────────
def final_report(out_dir: str):
    print("\n━━━ FINAL REPORT ━━━")
    all_files = [f for f in os.listdir(out_dir) if f.endswith(".wav")]
    
    ravdess  = [f for f in all_files if "ravdess" in f]
    cremad   = [f for f in all_files if "cremad" in f]
    original = [f for f in all_files if "real_actor" in f]
    other    = [f for f in all_files if f not in ravdess + cremad + original]

    total_size_mb = sum(os.path.getsize(os.path.join(out_dir, f)) for f in all_files) / (1024**2)

    print(f"  RAVDESS clips:        {len(ravdess):>5}")
    print(f"  CREMA-D clips:        {len(cremad):>5}")
    print(f"  Original actor clips: {len(original):>5}")
    print(f"  Other:                {len(other):>5}")
    print(f"  ─────────────────────────")
    print(f"  TOTAL:                {len(all_files):>5} clips")
    print(f"  Total size:           {total_size_mb:.1f} MB")
    print(f"  All standardized:     16kHz, mono, 2 seconds each")
    print(f"\n  ✅ Dataset saved to: {out_dir}")

    # Cleanup tmp
    if os.path.exists(TMP_DIR):
        shutil.rmtree(TMP_DIR, ignore_errors=True)
        print(f"  🧹 Temp files cleaned: {TMP_DIR}")


# ─── MAIN ────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Rebuild aggression dataset from RAVDESS + CREMA-D")
    parser.add_argument("--kaggle-json", type=str, default=None,
                        help="Path to kaggle.json API credentials file")
    parser.add_argument("--skip-download", action="store_true",
                        help="Skip download step (use if already downloaded to tmp)")
    args = parser.parse_args()

    print("=" * 60)
    print("  Aggression Dataset Rebuilder — Dectus AI")
    print("=" * 60)
    print(f"  Output dir: {DATASET_DIR}")
    print(f"  Target: 16kHz, mono, 2s clips")

    os.makedirs(DATASET_DIR, exist_ok=True)
    os.makedirs(TMP_DIR, exist_ok=True)

    # Step 0: Remove bad files
    clean_bad_files()

    if not args.skip_download:
        # Step 1: Setup Kaggle credentials
        setup_kaggle(args.kaggle_json)

        # Step 2: RAVDESS
        process_ravdess(DATASET_DIR)

        # Step 3: CREMA-D
        process_cremad(DATASET_DIR)

    # Step 4: Final report
    final_report(DATASET_DIR)


if __name__ == "__main__":
    main()
