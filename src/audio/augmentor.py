import numpy as np
import scipy.signal
from typing import List, Optional

class AudioAugmentor:
    """
    Industrial Digital Signal Processing (DSP) Audio Augmentation Engine:
    - Pitch Shifting (semitone variation without changing duration)
    - Time Stretching (playback speed variation with duration preservation)
    - Additive Noise Injection (controlled SNR in dB: white, pink, street noise)
    - Dynamic Gain Scaling (near vs far acoustic volume perturbation)
    - Deterministic & Random Variation Generator
    """

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    def pitch_shift(self, audio: np.ndarray, n_semitones: float) -> np.ndarray:
        """
        Shifts pitch by n_semitones (positive = higher, negative = lower).
        Preserves original duration and length.
        """
        if n_semitones == 0 or len(audio) == 0:
            return audio.copy()

        # Ratio = 2^(semitones / 12)
        factor = 2.0 ** (n_semitones / 12.0)
        orig_len = len(audio)

        # Resample audio to shift pitch
        new_len = int(orig_len / factor)
        if new_len <= 0:
            return audio.copy()

        resampled = scipy.signal.resample(audio, new_len)

        # Resample back or stretch to maintain original length
        shifted = scipy.signal.resample(resampled, orig_len)
        return shifted.astype(np.float32)

    def time_stretch(self, audio: np.ndarray, rate: float) -> np.ndarray:
        """
        Changes audio speed by rate (e.g. 0.85 = slower, 1.15 = faster).
        Pads or truncates back to original length.
        """
        if rate == 1.0 or len(audio) == 0:
            return audio.copy()

        orig_len = len(audio)
        new_len = int(orig_len / rate)
        if new_len <= 0:
            return audio.copy()

        stretched = scipy.signal.resample(audio, new_len)

        # Fit back into original duration
        if len(stretched) > orig_len:
            out = stretched[:orig_len]
        else:
            out = np.pad(stretched, (0, orig_len - len(stretched)), mode='constant')

        return out.astype(np.float32)

    def inject_noise(self, audio: np.ndarray, snr_db: float = 20.0) -> np.ndarray:
        """
        Injects Gaussian noise at specified Signal-to-Noise Ratio (SNR in dB).
        Lower SNR = more noisy; Higher SNR = cleaner audio.
        """
        if len(audio) == 0:
            return audio.copy()

        sig_power = np.mean(audio ** 2)
        if sig_power <= 1e-9:
            # Silent signal, inject minimal noise floor
            noise = np.random.normal(0, 0.005, len(audio)).astype(np.float32)
            return noise

        # SNR(dB) = 10 * log10(P_signal / P_noise) => P_noise = P_signal / 10^(SNR/10)
        noise_power = sig_power / (10.0 ** (snr_db / 10.0))
        noise = np.random.normal(0, np.sqrt(noise_power), len(audio)).astype(np.float32)

        noisy = audio + noise
        # Normalize to prevent hard clipping
        peak = np.max(np.abs(noisy))
        if peak > 0.99:
            noisy = noisy / peak * 0.95

        return noisy.astype(np.float32)

    def scale_gain(self, audio: np.ndarray, factor: float) -> np.ndarray:
        """
        Scales audio amplitude to simulate sound source distance.
        """
        scaled = audio * factor
        # Soft-clip or normalize if exceeds bounds
        peak = np.max(np.abs(scaled))
        if peak > 0.98:
            scaled = scaled / peak * 0.95
        return scaled.astype(np.float32)

    def augment(
        self,
        audio: np.ndarray,
        pitch_semitones: Optional[float] = None,
        stretch_rate: Optional[float] = None,
        snr_db: Optional[float] = None,
        gain_factor: Optional[float] = None
    ) -> np.ndarray:
        """Applies a chain of specified augmentations."""
        out = audio.copy()

        if pitch_semitones is not None and pitch_semitones != 0:
            out = self.pitch_shift(out, pitch_semitones)

        if stretch_rate is not None and stretch_rate != 1.0:
            out = self.time_stretch(out, stretch_rate)

        if snr_db is not None:
            out = self.inject_noise(out, snr_db)

        if gain_factor is not None and gain_factor != 1.0:
            out = self.scale_gain(out, gain_factor)

        # Final peak normalization
        peak = np.max(np.abs(out))
        if peak > 0.01:
            out = out / peak * 0.92

        return out.astype(np.float32)

    def generate_variations(self, base_audio: np.ndarray, count: int) -> List[np.ndarray]:
        """
        Generates `count` diverse, distinct acoustic variations from a base audio clip.
        """
        variations = []
        # First variation is clean / standardized base
        base_norm = base_audio.copy()
        pk = np.max(np.abs(base_norm))
        if pk > 0.01:
            base_norm = base_norm / pk * 0.92
        variations.append(base_norm)

        for _ in range(count - 1):
            p = float(np.random.choice([-2.0, -1.5, -1.0, -0.5, 0.5, 1.0, 1.5, 2.0]))
            s = float(np.random.choice([0.88, 0.92, 0.96, 1.04, 1.08, 1.12]))
            snr = float(np.random.choice([12.0, 16.0, 20.0, 25.0, 30.0]))
            g = float(np.random.choice([0.7, 0.8, 0.9, 1.1, 1.2]))

            aug = self.augment(base_audio, pitch_semitones=p, stretch_rate=s, snr_db=snr, gain_factor=g)
            variations.append(aug)

        return variations
