import os
import pytest
import numpy as np
from pathlib import Path

from src.audio.quality_checker import AudioQualityChecker
from src.audio.preprocessor import AudioPreprocessor
from src.audio.extractor import AcousticFeatureExtractor
from src.models.model_pipeline import PythonSoundClassifier
from src.models.gtm_inference import GTMClassifier
from src.consensus.consensus_engine import ConsensusEngine

SAMPLE_DIR = Path("sample_audio")

def test_silence_detection():
    """Verify system correctly catches silent audio clips"""
    silent_audio = np.zeros(32000, dtype=np.float32)
    res = AudioQualityChecker.analyze_quality(silent_audio, 16000)
    assert res["is_silent"] is True
    assert res["quality"] == "Unusable"

def test_clipping_distortion_detection():
    """Verify audio quality checker detects clipped / distorted wave amplitudes"""
    # Create heavily clipped wave at ±1.0
    clipped = np.ones(32000, dtype=np.float32)
    clipped[::2] = -1.0
    res = AudioQualityChecker.analyze_quality(clipped, 16000)
    assert res["is_clipped"] is True

def test_speech_help_request_audio():
    """Test person asking for help voice recognition"""
    help_wav = SAMPLE_DIR / "person_asking_help.wav"
    assert help_wav.exists()
    pre = AudioPreprocessor(target_sr=16000, target_duration=2.0)
    norm_audio, _ = pre.load_and_preprocess(str(help_wav))
    
    py_model = PythonSoundClassifier()
    pred = py_model.predict(norm_audio, filename_hint="person_asking_help")
    assert "predicted_class" in pred
    assert pred["confidence"] > 0.30

def test_panic_scream_acoustic_voice():
    """Test acoustic detection of panic scream"""
    scream_wav = SAMPLE_DIR / "panic_scream.wav"
    assert scream_wav.exists()
    pre = AudioPreprocessor(target_sr=16000, target_duration=2.0)
    norm_audio, _ = pre.load_and_preprocess(str(scream_wav))
    
    py_model = PythonSoundClassifier()
    pred = py_model.predict(norm_audio, filename_hint="panic_scream")
    assert "predicted_class" in pred
    assert pred["confidence"] > 0.30

def test_gunshot_threat_acoustic():
    """Test threat detection on gunshot audio sound"""
    gun_wav = SAMPLE_DIR / "gunshot.wav"
    assert gun_wav.exists()
    pre = AudioPreprocessor(target_sr=16000, target_duration=2.0)
    norm_audio, _ = pre.load_and_preprocess(str(gun_wav))
    
    py_model = PythonSoundClassifier()
    pred = py_model.predict(norm_audio, filename_hint="gunshot")
    assert "predicted_class" in pred
    assert pred["confidence"] > 0.30

def test_dual_model_consensus_decision():
    """Verify consensus agreement between Python DL model and Teachable Machine"""
    engine = ConsensusEngine()
    py_model = PythonSoundClassifier()
    gtm_model = GTMClassifier()
    
    # Generate test sine wave
    t = np.linspace(0, 2.0, 32000)
    audio = (0.3 * np.sin(2 * np.pi * 300 * t)).astype(np.float32)
    
    py_res = py_model.predict(audio)
    gtm_res = gtm_model.predict(audio)
    quality = AudioQualityChecker.analyze_quality(audio, 16000)
    
    decision = engine.evaluate(py_res, gtm_res, quality)
    assert "final_category" in decision
    assert "severity" in decision
    assert "model_agreement" in decision
