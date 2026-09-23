import numpy as np
import scipy.signal
from typing import List, Dict, Any, Tuple
import soundfile as sf
from config.settings import settings

class AudioPreprocessor:
    """
    Standardizes audio streams and files for the AI Model Pipeline:
    - Resampling to target rate (16,000 Hz)
    - Stereo to Mono conversion
    - Peak Amplitude Normalization
    - Silence trimming
    - Fixed-duration window segmentation (e.g., 2.0s segments)
    - Padding / Truncation for uniform neural network inputs
    """

    def __init__(self, target_sr: int = 16000, target_duration: float = 2.0):
        self.target_sr = target_sr
        self.target_duration = target_duration
        self.target_samples = int(target_sr * target_duration)

    def load_and_preprocess(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Loads audio file, converts to mono, resamples, and normalizes"""
        data, sr = sf.read(file_path, dtype='float32')

        # 1. Convert to Mono if multi-channel
        if data.ndim > 1:
            data = np.mean(data, axis=1)

        # 2. Resample if necessary using scipy
        if sr != self.target_sr:
            num_target_samples = int(len(data) * self.target_sr / sr)
            data = scipy.signal.resample(data, num_target_samples)
            sr = self.target_sr

        # 3. Peak Amplitude Normalization
        peak = np.max(np.abs(data))
        if peak > 1e-5:
            data = data / peak * 0.95

        return data.astype(np.float32), sr

    def trim_silence(self, audio: np.ndarray, threshold: float = 0.01) -> np.ndarray:
        """Trims leading and trailing silence"""
        above_threshold = np.where(np.abs(audio) > threshold)[0]
        if len(above_threshold) == 0:
            return audio  # All silent
        return audio[above_threshold[0]:above_threshold[-1] + 1]

    def pad_or_truncate(self, audio: np.ndarray) -> np.ndarray:
        """Ensures the audio segment is exactly target_samples long"""
        if len(audio) < self.target_samples:
            # Zero-padding
            pad_width = self.target_samples - len(audio)
            return np.pad(audio, (0, pad_width), mode='constant')
        else:
            # Truncate
            return audio[:self.target_samples]

    def segment_audio(self, audio: np.ndarray, overlap: float = 0.5) -> List[Dict[str, Any]]:
        """
        Segments continuous audio into fixed-duration chunks with start & end timestamps.
        Step (hop) size is controlled by overlap (default 50% overlap).
        """
        hop_samples = int(self.target_samples * (1.0 - overlap))
        total_len = len(audio)

        # If audio is shorter than window, pad it to single segment
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
                # Skip tiny dangling tail (< 30% of window)
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
