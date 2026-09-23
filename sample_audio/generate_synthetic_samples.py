import os
from pathlib import Path
import numpy as np
import scipy.signal
import soundfile as sf

def generate_samples(output_dir: Path):
    output_dir.mkdir(parents=True, exist_ok=True)
    sr = 16000
    duration = 2.0  # 2 seconds
    t = np.linspace(0, duration, int(sr * duration), endpoint=False)

    samples = {}

    # 1. Machinery Fault (Low-frequency rattle + harmonic rumble)
    hum = 0.3 * np.sin(2 * np.pi * 120 * t) + 0.2 * np.sin(2 * np.pi * 240 * t)
    rattle = 0.25 * np.random.normal(0, 0.2, len(t)) * (np.sin(2 * np.pi * 15 * t) > 0.5)
    samples["machinery_fault.wav"] = (hum + rattle) * 0.8

    # 2. Glass Breaking (Sharp impact + high-frequency shatter bursts)
    shatter = np.zeros_like(t)
    # Impact at 0.2s
    imp_idx = int(0.2 * sr)
    decay = np.exp(-15 * (t[imp_idx:] - 0.2))
    high_freq = np.sin(2 * np.pi * 3500 * t[imp_idx:]) + np.sin(2 * np.pi * 4800 * t[imp_idx:])
    noise = np.random.normal(0, 0.4, len(t[imp_idx:]))
    shatter[imp_idx:] = (high_freq + noise) * decay
    samples["glass_breaking.wav"] = shatter

    # 3. Alarm or Siren (Dual-tone frequency modulation 800Hz - 1400Hz)
    freq_sweep = 1100 + 400 * np.sin(2 * np.pi * 2.0 * t)
    phase = 2 * np.pi * np.cumsum(freq_sweep) / sr
    samples["alarm_siren.wav"] = 0.7 * np.sin(phase)

    # 4. Vehicle Horn (Dual steady chord 420Hz + 520Hz)
    horn = 0.4 * np.sin(2 * np.pi * 420 * t) + 0.4 * np.sin(2 * np.pi * 520 * t)
    samples["vehicle_horn.wav"] = horn

    # 5. Animal Sound (Barking bursts with pitch envelope)
    bark = np.zeros_like(t)
    for start in [0.2, 0.8, 1.4]:
        idx = int(start * sr)
        w_len = int(0.25 * sr)
        tw = t[:w_len]
        burst = (np.sin(2 * np.pi * 650 * tw) + 0.5 * np.random.normal(0, 0.2, w_len)) * np.sin(np.pi * tw / 0.25)
        bark[idx:idx+w_len] += burst
    samples["animal_sound.wav"] = bark * 0.7

    # 6. Gunshot (High-energy sharp ballistic impulse at 0.3s)
    shot = np.zeros_like(t)
    s_idx = int(0.3 * sr)
    t_shot = t[s_idx:] - 0.3
    decay_shot = np.exp(-35 * t_shot)
    shot[s_idx:] = (np.random.normal(0, 1.0, len(t_shot)) + 0.5 * np.sin(2 * np.pi * 800 * t_shot)) * decay_shot
    samples["gunshot.wav"] = shot

    # 7. Panic Scream (High-pitch human resonance ~1800Hz with tremor)
    tremor = 1800 + 150 * np.sin(2 * np.pi * 8.0 * t)
    phase_scream = 2 * np.pi * np.cumsum(tremor) / sr
    scream = 0.6 * np.sin(phase_scream) + 0.2 * np.random.normal(0, 0.1, len(t))
    # Envelope rising
    env = np.clip(t / 0.4, 0, 1) * np.exp(-0.5 * t)
    samples["panic_scream.wav"] = scream * env

    # 8. Aggression (Rough guttural bursts)
    agg = np.zeros_like(t)
    for start in [0.1, 0.9]:
        idx = int(start * sr)
        w_len = int(0.5 * sr)
        tw = t[:w_len]
        agg_burst = np.sin(2 * np.pi * 320 * tw) * (1 + 0.3 * np.sin(2 * np.pi * 50 * tw)) + 0.4 * np.random.normal(0, 0.3, w_len)
        agg[idx:idx+w_len] += agg_burst * np.sin(np.pi * tw / 0.5)
    samples["aggression.wav"] = agg * 0.6

    # 9. Person Asking for Help (Speech formant rhythm)
    speech = np.zeros_like(t)
    for start in [0.2, 1.1]:
        idx = int(start * sr)
        w_len = int(0.45 * sr)
        tw = t[:w_len]
        formant = (np.sin(2 * np.pi * 700 * tw) + 0.6 * np.sin(2 * np.pi * 1400 * tw)) * np.sin(np.pi * tw / 0.45)
        speech[idx:idx+w_len] += formant
    samples["person_asking_help.wav"] = speech * 0.7

    # 10. Background Noise (Pinkish ambient room noise)
    noise = np.random.normal(0, 0.05, len(t))
    b, a = scipy.signal.butter(2, 0.2, btype='low')
    filtered_noise = scipy.signal.lfilter(b, a, noise)
    samples["background_noise.wav"] = filtered_noise

    # Edge cases
    # 11. Test Silence
    samples["test_silence.wav"] = np.zeros(int(sr * 2.0), dtype=np.float32)

    # 12. Test Clipped
    clipped = 2.5 * np.sin(2 * np.pi * 440 * t)
    samples["test_clipped.wav"] = np.clip(clipped, -1.0, 1.0)

    # Write each file
    for name, audio in samples.items():
        peak = np.max(np.abs(audio))
        if peak > 1.0:
            audio = audio / peak * 0.95
        elif peak > 0 and name != "test_silence.wav" and name != "background_noise.wav":
            audio = audio / peak * 0.90
        file_path = output_dir / name
        sf.write(str(file_path), audio.astype(np.float32), sr)
        print(f"Generated {name} ({len(audio)} samples)")

if __name__ == "__main__":
    out = Path(__file__).resolve().parent
    generate_samples(out)
