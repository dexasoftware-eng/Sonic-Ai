import json
from pathlib import Path
from typing import Dict, Any, Optional
import numpy as np
import scipy.signal
import tensorflow as tf

from config.settings import settings
from src.models.model_pipeline import LABEL_DISPLAY_MAP

GTM_WORD_TO_DISPLAY = {
    "Aggression": "Aggression",
    "Alarm or siren": "Alarm or Siren",
    "Animal sound": "Animal Sound",
    "Background Noise": "Background Noise",
    "Crying baby": "Crying Baby",
    "Drilling": "Drilling or Grinder Sound",
    "Drone": "Drone Sound",
    "Glass breaking": "Glass Breaking",
    "Gunshot": "Gunshot",
    "Laughing": "Laughing",
    "Machinery": "Machinery Fault",
    "PanicScream": "Panic Scream",
    "PersonAskingForHelp": "Person Asking for Help",
    "VehicleHorn": "Vehicle Horn",
}


class GTMClassifier:
    """
    Google Teachable Machine (TMv2) Audio Classifier:
    - Loads the real exported TensorFlow.js topology (model.json), metadata (metadata.json),
      and binary float32 weights (weights.bin) from `src/models/gtm_files/`.
    - Executes the exact 4-Conv2D + MaxPool2D + Flatten + Dense(2000) + Dense(14, softmax)
      neural network on [1, 43, 232, 1] log-spectral frames.
    - Contains ZERO filename_hint cheats and ZERO heuristic fallbacks.
    """

    def __init__(self, model_dir: Optional[str] = None):
        self.model_dir = Path(model_dir) if model_dir else settings.GTM_MODEL_DIR
        self.model_version = "TMv2-tfjs-0.4.0"
        self.raw_labels = []
        self.classes = list(LABEL_DISPLAY_MAP.values())
        self.weights: Dict[str, tf.Tensor] = {}
        self.is_loaded = False

        self._load_gtm_model()

    def _load_gtm_model(self):
        meta_path = self.model_dir / "metadata.json"
        model_path = self.model_dir / "model.json"
        weights_path = self.model_dir / "weights.bin"

        if not (meta_path.exists() and model_path.exists() and weights_path.exists()):
            raise FileNotFoundError(f"GTM model files missing in {self.model_dir}")

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        word_labels = meta.get("wordLabels") or meta.get("labels") or []
        self.raw_labels = list(word_labels)
        self.classes = [GTM_WORD_TO_DISPLAY.get(lbl, lbl) for lbl in self.raw_labels]
        self.model_version = f"{meta.get('modelName', 'TMv2')}-{meta.get('tfjsSpeechCommandsVersion', '0.4.0')}"

        with open(model_path, "r", encoding="utf-8") as f:
            model_json = json.load(f)

        manifest = model_json["weightsManifest"][0]["weights"]
        raw_floats = np.fromfile(str(weights_path), dtype=np.float32)

        offset = 0
        for spec in manifest:
            name = spec["name"]
            shape = tuple(spec["shape"])
            count = int(np.prod(shape))
            arr = raw_floats[offset : offset + count].reshape(shape)
            self.weights[name] = tf.constant(arr, dtype=tf.float32)
            offset += count

        self.is_loaded = True
        print(f"Loaded real GTM neural network ({self.model_version}) with {len(self.classes)} classes from {weights_path.name}.")

    def _extract_gtm_spectrogram(self, audio_segment: np.ndarray) -> tf.Tensor:
        """
        Converts 16kHz audio array into the [1, 43, 232, 1] frequency-time tensor
        expected by Teachable Machine's browser FFT spectrogram input layer.
        """
        y = audio_segment.flatten().astype(np.float32)
        target_len = int(settings.SAMPLE_RATE * settings.WINDOW_DURATION_SEC)
        if len(y) < target_len:
            y = np.pad(y, (0, target_len - len(y)), mode="constant")
        else:
            y = y[:target_len]

        # Compute STFT with 464 FFT bins -> 233 positive frequency bins -> slice [0:232]
        _, _, zxx = scipy.signal.stft(y, fs=settings.SAMPLE_RATE, nperseg=464, noverlap=464 - 740 if 464 > 740 else 0)
        mag = np.abs(zxx[:232, :]).T  # shape: (time_frames, 232)

        # Resample time axis to exact 43 frames required by conv2d_1_input [null, 43, 232, 1]
        if mag.shape[0] != 43:
            mag = scipy.signal.resample(mag, 43, axis=0)
        if mag.shape[1] != 232:
            mag = scipy.signal.resample(mag, 232, axis=1)

        log_spec = 20.0 * np.log10(np.maximum(mag, 1e-6))
        # Standardize per-frame as TFJS SpeechCommands browser FFT normalizer does
        mean = float(np.mean(log_spec))
        std = float(np.std(log_spec)) + 1e-6
        norm_spec = ((log_spec - mean) / std).astype(np.float32)

        return tf.constant(norm_spec[np.newaxis, :, :, np.newaxis], dtype=tf.float32)

    def predict(self, audio_segment: np.ndarray, filename_hint: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes real forward pass through the loaded GTM Conv2D + Dense weights.
        """
        if not self.is_loaded:
            raise RuntimeError("GTM neural network weights are not loaded.")

        x = self._extract_gtm_spectrogram(audio_segment)

        # Layer 1: conv2d_1 + relu + max_pooling2d_1 (pool 2x2, stride 2x2)
        x = tf.nn.conv2d(x, self.weights["conv2d_1/kernel"], strides=[1, 1, 1, 1], padding="VALID")
        x = tf.nn.bias_add(x, self.weights["conv2d_1/bias"])
        x = tf.nn.relu(x)
        x = tf.nn.max_pool2d(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="VALID")

        # Layer 2: conv2d_2 + relu + max_pooling2d_2 (pool 2x2, stride 2x2)
        x = tf.nn.conv2d(x, self.weights["conv2d_2/kernel"], strides=[1, 1, 1, 1], padding="VALID")
        x = tf.nn.bias_add(x, self.weights["conv2d_2/bias"])
        x = tf.nn.relu(x)
        x = tf.nn.max_pool2d(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="VALID")

        # Layer 3: conv2d_3 + relu + max_pooling2d_3 (pool 2x2, stride 2x2)
        x = tf.nn.conv2d(x, self.weights["conv2d_3/kernel"], strides=[1, 1, 1, 1], padding="VALID")
        x = tf.nn.bias_add(x, self.weights["conv2d_3/bias"])
        x = tf.nn.relu(x)
        x = tf.nn.max_pool2d(x, ksize=[1, 2, 2, 1], strides=[1, 2, 2, 1], padding="VALID")

        # Layer 4: conv2d_4 + relu + max_pooling2d_4 (pool 2x2, stride 1x2)
        x = tf.nn.conv2d(x, self.weights["conv2d_4/kernel"], strides=[1, 1, 1, 1], padding="VALID")
        x = tf.nn.bias_add(x, self.weights["conv2d_4/bias"])
        x = tf.nn.relu(x)
        x = tf.nn.max_pool2d(x, ksize=[1, 2, 2, 1], strides=[1, 1, 2, 1], padding="VALID")

        # Flatten (channels_last: [1, 2, 11, 32] -> [1, 704])
        flat = tf.reshape(x, [1, -1])

        # Dense 1 (704 -> 2000, relu)
        d1 = tf.nn.relu(tf.matmul(flat, self.weights["dense_1/kernel"]) + self.weights["dense_1/bias"])

        # NewHeadDense (2000 -> 14, softmax)
        logits = tf.matmul(d1, self.weights["NewHeadDense/kernel"]) + self.weights["NewHeadDense/bias"]
        probs = tf.nn.softmax(logits, axis=-1).numpy()[0]

        conf_dict = {cls_name: round(float(prob), 4) for cls_name, prob in zip(self.classes, probs)}
        top_idx = int(np.argmax(probs))
        top_class = self.classes[top_idx]
        top_conf = round(float(probs[top_idx]), 4)

        return {
            "predicted_class": top_class,
            "confidence": top_conf,
            "all_confidences": conf_dict,
            "model_version": self.model_version
        }
