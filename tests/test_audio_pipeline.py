import pytest
import numpy as np
from src.audio.validator import AudioValidator, AudioValidationError
from src.audio.quality_checker import AudioQualityChecker
from src.audio.preprocessor import AudioPreprocessor
from src.audio.extractor import AcousticFeatureExtractor
from src.consensus.consensus_engine import ConsensusEngine
from src.models.model_pipeline import PythonSoundClassifier
from src.models.gtm_inference import GTMClassifier

def test_quality_checker_silence():
    """Verify silence detection spots empty audio"""
    silent_audio = np.zeros(16000, dtype=np.float32)
    res = AudioQualityChecker.analyze_quality(silent_audio, 16000)
    assert res["is_silent"] is True
    assert res["quality"] == "Unusable"

def test_quality_checker_normal_sound():
    """Verify normal signal is rated good"""
    t = np.linspace(0, 1.0, 16000)
    normal_audio = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    res = AudioQualityChecker.analyze_quality(normal_audio, 16000)
    assert res["is_silent"] is False
    assert res["quality"] in ["Good", "Acceptable"]

def test_preprocessor_segmentation():
    """Verify 4 seconds of audio is cut into overlapping 2.0s segments"""
    preprocessor = AudioPreprocessor(target_sr=16000, target_duration=2.0)
    audio = np.ones(16000 * 4, dtype=np.float32) * 0.1
    segments = preprocessor.segment_audio(audio, overlap=0.5)
    assert len(segments) >= 3
    assert len(segments[0]["audio"]) == 32000  # 2.0s * 16000

def test_feature_extractor():
    """Verify feature extractor returns full numerical vectors"""
    extractor = AcousticFeatureExtractor(sample_rate=16000)
    audio = np.random.normal(0, 0.2, 32000).astype(np.float32)
    feats = extractor.extract_tabular_features(audio)
    assert "feature_vector" in feats
    assert len(feats["feature_vector"]) > 50
    assert "spectral_centroid" in feats

def test_dual_model_inference():
    """Verify Python model and GTM model generate valid probability distributions"""
    py_model = PythonSoundClassifier()
    gtm_model = GTMClassifier()
    
    audio = np.random.normal(0, 0.1, 32000).astype(np.float32)
    
    py_res = py_model.predict(audio)
    gtm_res = gtm_model.predict(audio)
    
    assert "predicted_class" in py_res
    assert 0.0 <= py_res["confidence"] <= 1.0
    assert abs(sum(py_res["all_confidences"].values()) - 1.0) < 0.05
    
    assert "predicted_class" in gtm_res
    assert 0.0 <= gtm_res["confidence"] <= 1.0

def test_consensus_engine_disagreement():
    """Verify disagreement causes routing to manual review queue"""
    engine = ConsensusEngine()
    py_pred = {"predicted_class": "Gunshot", "confidence": 0.90, "all_confidences": {"Gunshot": 0.90, "Fireworks": 0.05}}
    gtm_pred = {"predicted_class": "Machinery Fault", "confidence": 0.70, "all_confidences": {"Machinery Fault": 0.70}}
    quality = {"quality": "Good", "is_silent": False, "is_clipped": False}
    
    eval_res = engine.evaluate(py_pred, gtm_pred, quality)
    assert eval_res["model_agreement"] is False
    assert eval_res["consistency_status"] == "Model Disagreement"
    assert eval_res["needs_manual_review"] is True
