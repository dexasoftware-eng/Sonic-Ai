import os
import json
import zipfile
import numpy as np
import librosa
from pathlib import Path

# Paths
DATASET_DIR = Path(r"G:\My Drive\SonicSentinel_AI\dataset")
OUTPUT_DIR = Path.home() / "Downloads" / "GTM_Upload_Ready"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 14 Standard Classes mapped to GTM Folder Names
CLASSES_MAP = [
    ("background_noise", "01_Background_Noise", "Background Noise"),
    ("aggression", "02_Aggression", "Aggression"),
    ("alarm_siren", "03_Alarm_or_Siren", "Alarm or siren"),
    ("animal_sound", "04_Animal_Sound", "Animal sound"),
    ("crying_baby", "05_Crying_Baby", "Crying baby"),
    ("drilling", "06_Drilling_or_Grinder_Sound", "Drilling"),
    ("drone", "07_Drone_Sound", "Drone"),
    ("glass_breaking", "08_Glass_Breaking", "Glass breaking"),
    ("gunshot", "09_Gunshot", "Gunshot"),
    ("laughing", "10_Laughing", "Laughing"),
    ("machinery_fault", "11_Machinery_Fault", "Machinery"),
    ("panic_scream", "12_Panic_Scream", "PanicScream"),
    ("person_asking_help", "13_Person_Asking_for_Help", "PersonAskingForHelp"),
    ("vehicle_horn", "14_Vehicle_Horn", "VehicleHorn"),
]

CLIPS_PER_CLASS = 300
TARGET_SR = 44100
N_FFT = 2048
HOP_LENGTH = 1024
NUM_FRAMES = 43
NUM_BINS = 232

def wav_to_gtm_frequency_frames(wav_path: str):
    """
    Simulates Google WebAudio AnalyserNode getFloatFrequencyData()
    - Resamples to 44.1 kHz
    - Takes 1.0 second duration (44,100 samples)
    - STFT with N_FFT=2048, hop=1024 -> 43 frames
    - First 232 frequency bins
    - Decibel range [-130.0, -20.0]
    """
    try:
        y, sr = librosa.load(wav_path, sr=TARGET_SR, mono=True, duration=1.0)
    except Exception as e:
        return None

    target_len = TARGET_SR  # 44100 samples = 1 sec
    if len(y) < target_len:
        y = np.pad(y, (0, target_len - len(y)), mode='constant')
    else:
        y = y[:target_len]

    # STFT calculation
    stft = librosa.stft(y, n_fft=N_FFT, hop_length=HOP_LENGTH, window='hann', center=True)
    # Shape of stft: (1 + 2048/2, 44) = (1025, 44)
    # First 232 frequency bins, exactly 43 time frames
    mag = np.abs(stft[:NUM_BINS, :NUM_FRAMES])

    # Convert to dB relative to full scale
    ref = 1.0
    db = 20.0 * np.log10(np.maximum(mag, 1e-6) / ref)

    # WebAudio default decibel limits: minDecibels = -100, maxDecibels = -30 (or -130 to -20)
    db = np.clip(db, -130.0, -20.0)

    # Transpose to (43 frames, 232 bins)
    frames = db.T.tolist()
    # Round to 2 decimal places to minimize zip size
    frames_rounded = [[round(val, 2) for val in frame] for frame in frames]
    return frames_rounded

# Minimal valid dummy webm header (43 bytes) to satisfy GTM UI loader
DUMMY_WEBM_BYTES = bytes([
    0x1A, 0x45, 0xDF, 0xA3, 0x9F, 0x42, 0x86, 0x81, 0x01, 0x42, 0xF7, 0x81, 0x01, 0x42, 0xF2, 0x81,
    0x04, 0x42, 0xF3, 0x81, 0x08, 0x42, 0x82, 0x84, 0x77, 0x65, 0x62, 0x6D, 0x42, 0x87, 0x81, 0x02,
    0x42, 0x85, 0x81, 0x02, 0x18, 0x53, 0x80, 0x67, 0x01, 0xFF, 0xFF
])

print("Starting 300-Clip GTM Zip Builder for all 14 Classes...")

for src_folder_name, dst_folder_name, gtm_label in CLASSES_MAP:
    class_src_dir = DATASET_DIR / src_folder_name
    class_out_dir = OUTPUT_DIR / dst_folder_name
    class_out_dir.mkdir(parents=True, exist_ok=True)
    zip_path = class_out_dir / f"{dst_folder_name}.zip"

    wav_files = sorted([f for f in class_src_dir.glob("*.wav")])
    selected_wavs = wav_files[:CLIPS_PER_CLASS]
    total_selected = len(selected_wavs)

    print(f"Processing [{gtm_label}] ({dst_folder_name}) -> {total_selected} clips...")

    samples_data = []
    for idx, wav_f in enumerate(selected_wavs, 1):
        frames = wav_to_gtm_frequency_frames(str(wav_f))
        if frames is None:
            continue
        sample_entry = {
            "blob": None,
            "blobFilePath": "sample-1.webm",
            "frequencyFrames": frames,
            "startTime": 0,
            "endTime": 1,
            "recordingDuration": 1
        }
        samples_data.append(sample_entry)

    # Create ZIP containing 'samples.json' and 'sample-1.webm'
    with zipfile.ZipFile(zip_path, 'w', compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("samples.json", json.dumps(samples_data))
        z.writestr("sample-1.webm", DUMMY_WEBM_BYTES)

    zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"   Done: {zip_path.name} ({len(samples_data)} samples, {zip_size_mb:.2f} MB)")

print("\nALL 14 CLASSES PACKAGED (300 CLIPS EACH) READY FOR GTM UPLOAD!")
print(f"Output Location: {OUTPUT_DIR}")
