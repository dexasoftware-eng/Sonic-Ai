import os
from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import joblib

from config.settings import settings, get_mandatory_classes
from src.audio.extractor import AcousticFeatureExtractor

class PythonSoundClassifier:
    """
    Python-based Sound Event Classifier:
    1. Extracts acoustic feature fingerprints from audio segments.
    2. Loads trained ML/DL model from `src/python_models/saved_models/` when available.
    3. Provides fallback acoustic-feature classifier for rapid development & verification.
    4. Outputs top predicted class and full confidence distribution across all 10 mandatory classes.
    """

    def __init__(self, model_path: Optional[str] = None):
        self.classes = get_mandatory_classes()
        self.feature_extractor = AcousticFeatureExtractor(sample_rate=settings.SAMPLE_RATE)
        self.model_version = "v1.0-cnn-acoustic"
        self.model = None
        self.scaler = None
        
        # Check for saved model
        target_path = Path(model_path) if model_path else settings.SAVED_MODELS_DIR / "classifier.joblib"
        if target_path.exists():
            self._load_model(target_path)

    def _load_model(self, path: Path):
        try:
            bundle = joblib.load(path)
            self.model = bundle.get("model")
            self.scaler = bundle.get("scaler")
            self.classes = bundle.get("classes", self.classes)
            self.model_version = bundle.get("version", "v1.0-trained")
        except Exception as e:
            print(f"Notice: Could not load model from {path}: {e}")

    def predict(self, audio_segment: np.ndarray) -> Dict[str, Any]:
        """
        Classifies audio segment (e.g. 2.0s 16kHz audio array).
        Returns predicted class, top confidence, and all 10 class probabilities.
        """
        feats = self.feature_extractor.extract_tabular_features(audio_segment)
        vector = np.array(feats["feature_vector"]).reshape(1, -1)

        # 1. Use trained model if available
        if self.model is not None:
            if self.scaler is not None:
                vector = self.scaler.transform(vector)
            probabilities = self.model.predict_proba(vector)[0]
            conf_dict = {cls_name: round(float(prob), 4) for cls_name, prob in zip(self.classes, probabilities)}
            top_class = self.classes[int(np.argmax(probabilities))]
            top_conf = round(float(np.max(probabilities)), 4)
            return {
                "predicted_class": top_class,
                "confidence": top_conf,
                "all_confidences": conf_dict,
                "model_version": self.model_version
            }

        # 2. Physics-based Acoustic Heuristic Classifier (Fallback until training finishes)
        centroid = feats["spectral_centroid"]["mean"]
        zcr = feats["zero_crossing_rate"]["mean"]
        rms = feats["rms_energy"]["mean"]
        rolloff = feats["spectral_rolloff"]["mean"]

        scores = {cls_name: 0.05 for cls_name in self.classes}

        # Acoustic rule heuristics based on sound physics
        if rms < 0.01:
            scores["Background Noise"] += 0.85
        elif zcr > 0.18 and centroid > 3200:
            scores["Glass Breaking"] += 0.80
            scores["Gunshot"] += 0.15
        elif rms > 0.25 and rolloff > 3500 and zcr > 0.12:
            scores["Gunshot"] += 0.82
            scores["Glass Breaking"] += 0.10
        elif centroid > 2200 and rms > 0.08:
            scores["Panic Scream"] += 0.80
            scores["Alarm or Siren"] += 0.12
        elif 800 < centroid < 2200 and rms > 0.06:
            if zcr > 0.08:
                scores["Aggression"] += 0.75
                scores["Person Asking for Help"] += 0.18
            else:
                scores["Person Asking for Help"] += 0.76
                scores["Aggression"] += 0.15
        elif 300 < centroid < 1200 and zcr < 0.06:
            scores["Machinery Fault"] += 0.78
            scores["Vehicle Horn"] += 0.15
        elif 1200 < centroid < 2600:
            scores["Alarm or Siren"] += 0.75
            scores["Vehicle Horn"] += 0.20
        else:
            scores["Background Noise"] += 0.50
            scores["Animal Sound"] += 0.30

        # Apply Softmax to normalize to valid probability distribution summing to 1.0
        exp_scores = np.exp(np.array(list(scores.values())))
        softmax_probs = exp_scores / np.sum(exp_scores)

        conf_dict = {cls_name: round(float(prob), 4) for cls_name, prob in zip(scores.keys(), softmax_probs)}
        sorted_items = sorted(conf_dict.items(), key=lambda x: x[1], reverse=True)
        top_class, top_conf = sorted_items[0]

        return {
            "predicted_class": top_class,
            "confidence": top_conf,
            "all_confidences": conf_dict,
            "model_version": "v1.0-acoustic-engine"
        }
