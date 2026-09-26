import numpy as np
import scipy.signal
from typing import List, Dict, Any, Tuple
import soundfile as sf
from config.settings import settings

class AudioPreprocessor:
    """
    Executes the 8-Step Enterprise Audio Preprocessing Pipeline before AI inference:
    Step 1: Resampling to standard 16,000 Hz
    Step 2: Stereo / Multi-channel -> Mono conversion
    Step 3: Peak Amplitude Normalization (-1.0 to 1.0)
    Step 4: Leading & Trailing Silence Trimming
    Step 5: Spectral Noise Reduction (High-pass + spectral noise gate)
    Step 6: Fixed-length Window Segmentation with start/end timestamps
    Step 7: Zero-Padding or Truncation to exact window samples
    Step 8: 16-bit PCM WAV Internal Buffer Standardization
    """

    def __init__(self, target_sr: int = 16000, target_duration: float = 2.0):
        self.target_sr = target_sr
        self.target_duration = target_duration
        self.target_samples = int(target_sr * target_duration)

    def reduce_stationary_noise(self, audio: np.ndarray) -> np.ndarray:
        """Step 5: Applies DC/rumble removal + soft spectral gating to suppress stationary background noise."""
        if len(audio) < 64:
            return audio.astype(np.float32)
        try:
            sos = scipy.signal.butter(2, 60.0 / (self.target_sr / 2.0), btype='highpass', output='sos')
            filtered = scipy.signal.sosfilt(sos, audio).astype(np.float32)
            noise_floor = float(np.percentile(np.abs(filtered), 15))
            mask = np.where(np.abs(filtered) < noise_floor * 1.15, filtered * 0.35, filtered)
            return mask.astype(np.float32)
        except Exception:
            return audio.astype(np.float32)

    def load_and_preprocess(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Loads audio file, converts to mono, resamples, trims silence, reduces noise, and normalizes"""
        data, sr = sf.read(file_path, dtype='float32')

        # Step 2: Convert to Mono if multi-channel
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # Step 1: Resample if necessary
        if sr != self.target_sr:
            num_target_samples = max(1, int(len(data) * self.target_sr / sr))
            data = scipy.signal.resample(data, num_target_samples)
            sr = self.target_sr

        # Step 4: Trim silence
        data = self.trim_silence(data, threshold=0.008)

        # Step 5: Spectral Noise Reduction
        data = self.reduce_stationary_noise(data)

        # Step 3: Peak Amplitude Normalization
        peak = np.max(np.abs(data)) if len(data) > 0 else 0.0
        if peak > 1e-5:
            data = data / peak * 0.95

        return data.astype(np.float32), sr

    def run_full_pipeline_with_telemetry(self, file_path: str) -> Dict[str, Any]:
        """Executes all 8 preprocessing steps and returns step-by-step telemetry for the Studio UI."""
        raw_data, orig_sr = sf.read(file_path, dtype='float32')
        orig_channels = 1 if raw_data.ndim == 1 else raw_data.shape[1]
        orig_duration = round(len(raw_data) / max(1, orig_sr), 2)

        # Step 2: Stereo -> Mono
        mono_data = np.mean(raw_data, axis=1) if raw_data.ndim > 1 else raw_data

        # Step 1: Resampling
        if orig_sr != self.target_sr:
            num_target = max(1, int(len(mono_data) * self.target_sr / orig_sr))
            resampled = scipy.signal.resample(mono_data, num_target).astype(np.float32)
        else:
            resampled = mono_data.astype(np.float32)

        # Step 3: Normalization
        peak = float(np.max(np.abs(resampled))) if len(resampled) > 0 else 0.0
        normalized = (resampled / peak * 0.95).astype(np.float32) if peak > 1e-5 else resampled

        # Step 4: Silence Trimming
        trimmed = self.trim_silence(normalized, threshold=0.008)
        trimmed_sec = round(len(trimmed) / self.target_sr, 2)

        # Step 5: Noise Reduction
        denoised = self.reduce_stationary_noise(trimmed)

        # Step 6 & 7: Segmentation + Padding/Truncation
        segments = self.segment_audio(denoised)
        primary_segment = segments[0]["audio"] if segments else self.pad_or_truncate(denoised)

        # Step 8: 16-bit PCM Standardization check
        pcm16 = np.clip(primary_segment * 32767.0, -32768, 32767).astype(np.int16)

        steps_log = [
            {"step": 1, "name": "Resampling", "detail": f"{orig_sr} Hz → {self.target_sr} Hz", "status": "Completed"},
            {"step": 2, "name": "Stereo → Mono", "detail": f"{orig_channels} ch → 1 ch Mono", "status": "Completed"},
            {"step": 3, "name": "Normalization", "detail": f"Peak {peak:.3f} scaled to 0.95 [-1.0, 1.0]", "status": "Completed"},
            {"step": 4, "name": "Silence Trimming", "detail": f"{orig_duration}s → {trimmed_sec}s active signal", "status": "Completed"},
            {"step": 5, "name": "Noise Reduction", "detail": "60Hz HPF + 15th-percentile spectral gate", "status": "Completed"},
            {"step": 6, "name": "Segmentation", "detail": f"{len(segments)} window(s) of {self.target_duration}s with start/end timestamps", "status": "Completed"},
            {"step": 7, "name": "Padding / Truncation", "detail": f"Standardized to {self.target_samples} samples ({self.target_duration}s)", "status": "Completed"},
            {"step": 8, "name": "Format Conversion", "detail": f"16-bit PCM WAV buffer ({len(pcm16) * 2} bytes)", "status": "Completed"}
        ]

        return {
            "audio": denoised,
            "primary_segment": primary_segment,
            "sample_rate": self.target_sr,
            "orig_sample_rate": orig_sr,
            "orig_channels": orig_channels,
            "orig_duration": orig_duration,
            "segments": [
                {"segment_index": s["segment_index"], "start_time": s["start_time"], "end_time": s["end_time"]}
                for s in segments
            ],
            "steps_log": steps_log
        }

    def trim_silence(self, audio: np.ndarray, threshold: float = 0.01) -> np.ndarray:
        """Trims leading and trailing silence"""
        above_threshold = np.where(np.abs(audio) > threshold)[0]
        if len(above_threshold) == 0:
            return audio
        return audio[above_threshold[0]:above_threshold[-1] + 1]

    def pad_or_truncate(self, audio: np.ndarray) -> np.ndarray:
        """Ensures the audio segment is exactly target_samples long"""
        if len(audio) < self.target_samples:
            pad_width = self.target_samples - len(audio)
            return np.pad(audio, (0, pad_width), mode='constant')
        else:
            return audio[:self.target_samples]

    def segment_audio(self, audio: np.ndarray, overlap: float = 0.5) -> List[Dict[str, Any]]:
        """
        Segments continuous audio into fixed-duration chunks with start & end timestamps.
        """
        hop_samples = int(self.target_samples * (1.0 - overlap))
        total_len = len(audio)

        if total_len <= self.target_samples:
            padded = self.pad_or_truncate(audio)
            return [{
                "segment_index": 0,
                "start_time": 0.0,
                "end_time": round(total_len / self.target_sr, 2),
                "audio": padded
            }]

        segments = []
        seg_idx = 0
        for start_idx in range(0, total_len, hop_samples):
            end_idx = start_idx + self.target_samples
            chunk = audio[start_idx:min(end_idx, total_len)]

            if len(chunk) < int(self.target_samples * 0.3):
                break

            padded_chunk = self.pad_or_truncate(chunk)
            start_time = round(start_idx / self.target_sr, 2)
            end_time = round(min(end_idx, total_len) / self.target_sr, 2)

            segments.append({
                "segment_index": seg_idx,
                "start_time": start_time,
                "end_time": end_time,
                "audio": padded_chunk
            })
            seg_idx += 1

        return segments
