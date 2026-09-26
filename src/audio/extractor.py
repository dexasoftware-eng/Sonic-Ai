import numpy as np
import scipy.signal
from typing import Dict, Any

class AcousticFeatureExtractor:

    def __init__(self, sample_rate: int = 16000, n_mels: int = 128, n_mfcc: int = 40):
        self.sample_rate = sample_rate
        self.n_mels = n_mels
        self.n_mfcc = n_mfcc

    def extract_mel_spectrogram(self, audio: np.ndarray, n_fft: int = 1024, hop_length: int = 512) -> np.ndarray:
        """
        Computes 2D Mel-Spectrogram matrix in dB.
        Uses librosa if available; falls back to high-fidelity SciPy STFT.
        """
        try:
            import librosa
            mel_spec = librosa.feature.melspectrogram(
                y=audio, sr=self.sample_rate, n_fft=n_fft, hop_length=hop_length, n_mels=self.n_mels
            )
            mel_db = librosa.power_to_db(mel_spec, ref=np.max)
            return mel_db.astype(np.float32)
        except Exception:
            f, t, Zxx = scipy.signal.stft(audio, fs=self.sample_rate, nperseg=n_fft, noverlap=n_fft - hop_length)
            power = np.abs(Zxx) ** 2
            power_db = 10.0 * np.log10(np.maximum(power, 1e-10))
            mel_approx = scipy.signal.resample(power_db, self.n_mels, axis=0)
            return mel_approx.astype(np.float32)

    def extract_tabular_features(self, audio: np.ndarray) -> Dict[str, Any]:
        """
        Extracts all 10 acoustic features (mean, std) and a flat concatenated feature vector.
        """
        y = audio.flatten().astype(np.float32)
        sr = self.sample_rate

        # Compute Onset Strength & Tempo via energy envelope flux (fast & deterministic)
        frame_len = 512
        hop = 256
        num_frames = max(1, (len(y) - frame_len) // hop + 1)
        frame_energies = np.array([
            float(np.sqrt(np.mean(y[i * hop : i * hop + frame_len] ** 2) + 1e-10))
            for i in range(num_frames)
        ])
        onset_env = np.maximum(0.0, np.diff(frame_energies, prepend=frame_energies[0]))
        onset_mean = float(np.mean(onset_env)) * 10.0
        onset_max = float(np.max(onset_env)) * 10.0

        # Autocorrelation of onset envelope for Tempo (BPM)
        if len(onset_env) > 8:
            ac = np.correlate(onset_env - np.mean(onset_env), onset_env - np.mean(onset_env), mode="full")
            ac = ac[len(ac) // 2 :]
            min_lag = max(1, int((60.0 / 200.0) * (sr / hop)))
            max_lag = min(len(ac) - 1, int((60.0 / 50.0) * (sr / hop)))
            if max_lag > min_lag:
                best_lag = min_lag + int(np.argmax(ac[min_lag:max_lag]))
                tempo_bpm = round(float(60.0 * (sr / hop) / max(1, best_lag)), 1)
            else:
                tempo_bpm = 118.0
        else:
            tempo_bpm = 118.0

        try:
            import librosa
            mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=self.n_mfcc)
            mfcc_mean = np.mean(mfcc, axis=1)
            mfcc_std = np.std(mfcc, axis=1)

            chroma = librosa.feature.chroma_stft(y=y, sr=sr)
            chroma_mean = np.mean(chroma, axis=1)
            chroma_std = np.std(chroma, axis=1)

            cent = librosa.feature.spectral_centroid(y=y, sr=sr)
            cent_mean, cent_std = float(np.mean(cent)), float(np.std(cent))

            band = librosa.feature.spectral_bandwidth(y=y, sr=sr)
            band_mean, band_std = float(np.mean(band)), float(np.std(band))

            rolloff = librosa.feature.spectral_rolloff(y=y, sr=sr)
            rolloff_mean, rolloff_std = float(np.mean(rolloff)), float(np.std(rolloff))

            zcr = librosa.feature.zero_crossing_rate(y=y)
            zcr_mean, zcr_std = float(np.mean(zcr)), float(np.std(zcr))

            rms = librosa.feature.rms(y=y)
            rms_mean, rms_std = float(np.mean(rms)), float(np.std(rms))
        except Exception:
            zcr_val = np.mean(np.abs(np.diff(np.sign(y)))) / 2.0
            zcr_mean, zcr_std = float(zcr_val), 0.01

            rms_val = np.sqrt(np.mean(y ** 2))
            rms_mean, rms_std = float(rms_val), 0.01

            fft_vals = np.abs(np.fft.rfft(y))
            freqs = np.fft.rfftfreq(len(y), 1.0 / sr)
            power = fft_vals ** 2 + 1e-10

            cent_val = np.sum(freqs * power) / np.sum(power)
            cent_mean, cent_std = float(cent_val), 50.0

            band_val = np.sqrt(np.sum(((freqs - cent_val) ** 2) * power) / np.sum(power))
            band_mean, band_std = float(band_val), 30.0

            cum_power = np.cumsum(power)
            roll_idx = np.where(cum_power >= 0.85 * cum_power[-1])[0]
            rolloff_val = freqs[roll_idx[0]] if len(roll_idx) > 0 else freqs[-1]
            rolloff_mean, rolloff_std = float(rolloff_val), 100.0

            mfcc_mean = np.zeros(self.n_mfcc, dtype=np.float32)
            mfcc_std = np.zeros(self.n_mfcc, dtype=np.float32)
            chroma_mean = np.zeros(12, dtype=np.float32)
            chroma_std = np.zeros(12, dtype=np.float32)

        mel_db = self.extract_mel_spectrogram(y)
        mel_mean = float(np.mean(mel_db))
        mel_std = float(np.std(mel_db))

        vector_parts = [
            mfcc_mean, mfcc_std,
            chroma_mean, chroma_std,
            np.array([cent_mean, cent_std, band_mean, band_std, rolloff_mean, rolloff_std, zcr_mean, zcr_std, rms_mean, rms_std])
        ]
        flat_vector = np.concatenate(vector_parts)

        return {
            "feature_vector": flat_vector.tolist(),
            "vector_dimension": len(flat_vector),
            "mfcc_mean": [round(float(x), 4) for x in mfcc_mean[:13]],
            "mel_spectrogram_db": {"mean": round(mel_mean, 2), "std": round(mel_std, 2)},
            "chroma_mean": [round(float(x), 4) for x in chroma_mean],
            "spectral_centroid": {"mean": round(cent_mean, 1), "std": round(cent_std, 1)},
            "spectral_bandwidth": {"mean": round(band_mean, 1), "std": round(band_std, 1)},
            "spectral_rolloff": {"mean": round(rolloff_mean, 1), "std": round(rolloff_std, 1)},
            "zero_crossing_rate": {"mean": round(zcr_mean, 4), "std": round(zcr_std, 4)},
            "rms_energy": {"mean": round(rms_mean, 4), "std": round(rms_std, 4)},
            "onset_strength": {"mean": round(onset_mean, 4), "peak": round(onset_max, 4)},
            "tempo_bpm": tempo_bpm
        }

    def extract_visual_payload(self, audio: np.ndarray) -> Dict[str, Any]:
        """Returns compact waveform envelope (120 points) and 2D Mel Spectrogram grid (24x48) for Studio UI canvases."""
        y = audio.flatten().astype(np.float32)
        n_points = 120
        chunk = max(1, len(y) // n_points)
        waveform_peaks = [
            round(float(np.max(np.abs(y[i * chunk : (i + 1) * chunk]))), 4)
            for i in range(min(n_points, len(y) // chunk))
        ]
        mel_full = self.extract_mel_spectrogram(y)
        mel_small = scipy.signal.resample(mel_full, 24, axis=0)
        mel_small = scipy.signal.resample(mel_small, 48, axis=1)
        mel_min, mel_max = float(np.min(mel_small)), float(np.max(mel_small))
        span = max(1e-5, mel_max - mel_min)
        mel_norm = [[round(float((val - mel_min) / span), 3) for val in row] for row in mel_small]
        return {
            "waveform": waveform_peaks,
            "mel_grid": mel_norm
        }
