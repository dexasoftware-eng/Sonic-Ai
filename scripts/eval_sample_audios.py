import os
import sys
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import glob
from src.audio.validator import AudioValidator, AudioValidationError
from src.audio.quality_checker import AudioQualityChecker
from src.audio.preprocessor import AudioPreprocessor
from src.models.model_pipeline import PythonSoundClassifier
from src.models.gtm_inference import GTMClassifier
from src.consensus.consensus_engine import ConsensusEngine

def evaluate_samples():
    preprocessor = AudioPreprocessor(target_sr=16000, target_duration=2.0)
    py_classifier = PythonSoundClassifier()
    gtm_classifier = GTMClassifier()
    consensus = ConsensusEngine()

    samples = sorted(glob.glob("sample_audio/*.wav"))
    print(f"Total files in sample_audio directory: {len(samples)}\n")

    correct_py = 0
    correct_gtm = 0
    correct_consensus = 0
    total = 0

    header = f"{'Filename':<22} | {'Ground Truth':<18} | {'Python Model':<18} | {'PyConf':<6} | {'GTM Model':<18} | {'Consensus Final':<18} | {'Match'}"
    print(header)
    print("=" * len(header))

    for s in samples:
        fname = Path(s).name

        # Edge case files testing
        if fname.startswith("test_"):
            try:
                AudioValidator.inspect_and_validate(Path(s))
                raw_aud, sr = preprocessor.load_and_preprocess(s)
                q = AudioQualityChecker.analyze_quality(raw_aud, sr)
                val_stat = f"Quality: {q['quality']}"
            except AudioValidationError as e:
                val_stat = f"REJECTED: {e}"
            except Exception as e:
                val_stat = f"ERR: {e}"
            print(f"{fname:<22} | {'[System Check]':<18} | {val_stat:<18} | {'-':<6} | {'-':<18} | {'-':<18} | CHECK")
            continue

        gt = fname.replace(".wav", "").replace("_", " ").title()

        try:
            AudioValidator.inspect_and_validate(Path(s))
            raw_aud, sr = preprocessor.load_and_preprocess(s)
            quality_info = AudioQualityChecker.analyze_quality(raw_aud, sr)
            segments = preprocessor.segment_audio(raw_aud)
            primary_seg = segments[0]["audio"] if segments else raw_aud
        except Exception as e:
            print(f"{fname:<22} | {gt:<18} | REJECTED: {e} | - | - | - | FAIL")
            total += 1
            continue

        # 1. Python Model Prediction (Pure acoustic physics engine without filename hint)
        py_pred = py_classifier.predict(primary_seg, filename_hint=None)
        py_cls = py_pred["predicted_class"]
        py_conf = py_pred["confidence"]

        # 2. GTM Model Prediction (Independent)
        gtm_pred = gtm_classifier.predict(primary_seg, filename_hint=None)
        gtm_cls = gtm_pred["predicted_class"]

        # 3. Consensus Engine Evaluation
        eval_res = consensus.evaluate(py_pred, gtm_pred, quality_info)
        final_cls = eval_res["final_category"]

        # Normalize string for fuzzy match
        gt_norm = gt.lower().replace("alarm siren", "alarm").replace("asking help", "help")
        py_norm = py_cls.lower().replace(" or ", " ").replace("_", " ")
        gtm_norm = gtm_cls.lower().replace(" or ", " ").replace("_", " ")
        final_norm = final_cls.lower().replace(" or ", " ").replace("_", " ")

        py_match = any(w in py_norm for w in gt_norm.split() if len(w) > 3)
        gtm_match = any(w in gtm_norm for w in gt_norm.split() if len(w) > 3)
        final_match = any(w in final_norm for w in gt_norm.split() if len(w) > 3)

        if py_match:
            correct_py += 1
        if gtm_match:
            correct_gtm += 1
        if final_match:
            correct_consensus += 1
        total += 1

        status_str = "YES" if final_match else "NO"
        print(f"{fname:<22} | {gt:<18} | {py_cls:<18} | {py_conf:<6.2f} | {gtm_cls:<18} | {final_cls:<18} | {status_str}")

    print("=" * len(header))
    print(f"\n--- ACCURACY REPORT ON SAMPLE AUDIOS ---")
    print(f"Total Sound Event Classes Tested: {total}")
    print(f"1. Python Acoustic Model Accuracy:   {correct_py}/{total} ({(correct_py/total)*100:.1f}%)")
    print(f"2. GTM Model Accuracy:               {correct_gtm}/{total} ({(correct_gtm/total)*100:.1f}%)")
    print(f"3. Dual-Model Consensus Accuracy:    {correct_consensus}/{total} ({(correct_consensus/total)*100:.1f}%)")

if __name__ == "__main__":
    evaluate_samples()
