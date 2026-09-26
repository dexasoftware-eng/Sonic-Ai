import os
from pathlib import Path
from typing import Dict, Any, Tuple
import soundfile as sf

# Allowed audio file extensions for enterprise ingestion
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".flac", ".ogg", ".m4a"}
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MIN_FILE_SIZE_BYTES = 1024  # 1 KB
MIN_DURATION_SECONDS = 0.5
MAX_DURATION_SECONDS = 300.0  # 5 minutes

class AudioValidationError(Exception):
    """Custom exception raised when an audio file fails validation."""
    pass

class AudioValidator:
    """
    Validates uploaded and captured audio files for:
    - Supported format
    - File size limits
    - Duration bounds
    - Readable audio frames and file integrity
    """

    @staticmethod
    def validate_file_basics(file_path: Path) -> Tuple[bool, str]:
        """Validates extension and file size existence"""
        if not file_path.exists():
            return False, f"File does not exist: {file_path.name}"

        ext = file_path.suffix.lower()
        if ext not in ALLOWED_AUDIO_EXTENSIONS:
            return False, f"Unsupported format '{ext}'. Supported: {', '.join(sorted(ALLOWED_AUDIO_EXTENSIONS))}"

        size = file_path.stat().st_size
        if size < MIN_FILE_SIZE_BYTES:
            return False, f"Audio file is too small or empty ({size} bytes)."
        if size > MAX_FILE_SIZE_BYTES:
            return False, f"File exceeds maximum allowed size of 50 MB ({size / (1024*1024):.1f} MB)."

        return True, "File basics valid"

    @classmethod
    def inspect_and_validate(cls, file_path: Path) -> Dict[str, Any]:
        """
        Performs in-depth audio validation and extracts technical metadata.
        Returns a dictionary with validation status and audio facts.
        """
        is_basic_valid, msg = cls.validate_file_basics(file_path)
        if not is_basic_valid:
            raise AudioValidationError(msg)

        try:
            # SoundFile provides fast C-level header inspection
            info = sf.info(str(file_path))
            duration = float(info.duration)
            sample_rate = int(info.samplerate)
            channels = int(info.channels)
            frames = int(info.frames)
            format_name = str(info.format)
            subtype = str(info.subtype)

            if duration < MIN_DURATION_SECONDS:
                raise AudioValidationError(f"Audio duration ({duration:.2f}s) is shorter than minimum {MIN_DURATION_SECONDS}s.")
            if duration > MAX_DURATION_SECONDS:
                raise AudioValidationError(f"Audio duration ({duration:.2f}s) exceeds maximum {MAX_DURATION_SECONDS}s.")
            if frames == 0:
                raise AudioValidationError("Audio file contains zero audio frames.")

            return {
                "valid": True,
                "filename": file_path.name,
                "file_size_bytes": file_path.stat().st_size,
                "duration_seconds": round(duration, 3),
                "sample_rate": sample_rate,
                "channels": channels,
                "frames": frames,
                "format": format_name,
                "subtype": subtype
            }

        except AudioValidationError:
            raise
        except Exception as e:
            # Try fallback check or raise integrity error
            raise AudioValidationError(f"Corrupt or unreadable audio file: {str(e)}")
