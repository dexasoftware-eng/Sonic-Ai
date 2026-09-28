import numpy as np
from typing import Dict, Any, Tuple

class AudioQualityChecker:
    """
    Evaluates audio signal health:
    - Root-Mean-Square (RMS) Energy & Silence detection
    - Peak Amplitude & Severe clipping detection
    - Signal-to-Noise Ratio (SNR) estimation
    - Overall quality rating: Good | Acceptable | Poor | Unusable
    """

    SILENCE_RMS_THRESHOLD = 0.005
    CLIPPING_PEAK_THRESHOLD = 0.99
    MAX_PERMISSIBLE_CLIPPED_RATIO = 0.02  # 2% of samples clipped = severe

    @classmethod
    def analyze_quality(cls, audio_array: np.ndarray, sample_rate: int) -> Dict[str, Any]:
        """
        Analyzes floating point audio array normalized between [-1.0, 1.0]
        """
        if audio_array.size == 0:
            return {
                "quality": "Unusable",
                "is_silent": True,
                "is_clipped": False,
                "rms_energy": 0.0,
                "snr_db": 0.0,
                "message": "Empty audio buffer"
            }

        # Calculate RMS Energy
        rms = float(np.sqrt(np.mean(audio_array ** 2)))
        peak = float(np.max(np.abs(audio_array)))

        # Silence Detection
        is_silent = rms < cls.SILENCE_RMS_THRESHOLD

        # Clipping Detection
        clipped_samples = np.sum(np.abs(audio_array) >= cls.CLIPPING_PEAK_THRESHOLD)
        clipped_ratio = float(clipped_samples / audio_array.size)
        is_clipped = clipped_ratio > 0.0005  # More than 0.05% clipped

        # SNR Estimation (Signal RMS vs Estimated Noise Floor RMS)
        frame_len = max(16, min(int(sample_rate * 0.05), max(16, len(audio_array) // 4)))
        frames = [audio_array[i:i+frame_len] for i in range(0, len(audio_array), frame_len) if len(audio_array[i:i+frame_len]) > 0]
        frame_rms = np.array([np.sqrt(np.mean(f ** 2)) for f in frames], dtype=np.float64)
        if frame_rms.size >= 2:
            sorted_rms = np.sort(frame_rms)
            noise_floor = float(np.mean(sorted_rms[:max(1, int(len(sorted_rms) * 0.15))])) + 1e-7
            signal_floor = float(np.mean(sorted_rms[int(len(sorted_rms) * 0.70):])) + 1e-7
            snr_db = float(20.0 * np.log10(max(signal_floor, rms + 1e-7) / noise_floor))
        else:
            noise_floor = float(np.percentile(np.abs(audio_array), 15)) + 1e-7
            snr_db = float(20.0 * np.log10((rms + 1e-7) / noise_floor))

        # Classify Audio Quality Rating
        if is_silent:
            quality = "Unusable"
            msg = "Clip is essentially silent - audio below audible detection threshold."
        elif clipped_ratio > cls.MAX_PERMISSIBLE_CLIPPED_RATIO:
            quality = "Unusable"
            msg = f"Severe microphone clipping distortion ({clipped_ratio*100:.1f}% clipped)."
        elif snr_db < 5.0:
            quality = "Poor"
            msg = "High background noise interference (SNR < 5 dB)."
        elif is_clipped or snr_db < 12.0:
            quality = "Acceptable"
            msg = "Minor noise or slight clipping detected."
        else:
            quality = "Good"
            msg = "Clear, clean audio signal."

        return {
            "quality": quality,
            "rms_energy": round(rms, 5),
            "peak_amplitude": round(peak, 4),
            "snr_db": round(snr_db, 2),
            "is_silent": is_silent,
            "is_clipped": is_clipped,
            "clipped_ratio": round(clipped_ratio, 4),
            "quality_message": msg
        }
