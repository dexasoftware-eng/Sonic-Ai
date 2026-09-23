from typing import Dict, Any, List, Optional
from config.settings import load_rules

class ConsensusEngine:
    """
    Evaluates predictions from the Python Classifier and Google Teachable Machine:
    1. Compares predicted categories and confidence gap.
    2. Determines Model Consistency Status.
    3. Evaluates Audio Quality & Top-Two confidence margin.
    4. Applies Consecutive-Window Confirmation for Critical Threat sounds (Gunshots, Screams).
    5. Dispatches alerts or routes uncertain/disagreeing events to the Manual Review Queue.
    """

    def __init__(self):
        self.rules_config = load_rules()
        self.categories_map = {cat["name"]: cat for cat in self.rules_config.get("sound_categories", [])}
        self.consensus_rules = self.rules_config.get("system", {}).get("consensus_rules", {})
        
        # In-memory consecutive window history: stream_id -> [list of recent predictions]
        self._stream_history: Dict[str, List[str]] = {}

    def evaluate(
        self,
        python_prediction: Dict[str, Any],
        gtm_prediction: Dict[str, Any],
        audio_quality: Dict[str, Any],
        stream_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        python_prediction: {"predicted_class": str, "confidence": float, "all_confidences": dict}
        gtm_prediction: {"predicted_class": str, "confidence": float, "all_confidences": dict}
        audio_quality: {"quality": str, "is_silent": bool, "is_clipped": bool}
        """
        py_class = python_prediction.get("predicted_class", "Background Noise")
        py_conf = float(python_prediction.get("confidence", 0.0))
        
        gtm_class = gtm_prediction.get("predicted_class", "Background Noise")
        gtm_conf = float(gtm_prediction.get("confidence", 0.0))

        quality_status = audio_quality.get("quality", "Good")

        # 1. Model Agreement & Confidence Difference
        is_agreement = (py_class == gtm_class)
        conf_diff = round(abs(py_conf - gtm_conf), 4)

        # 2. Top-Two Confidence Margin calculation for Python model
        py_all = sorted(python_prediction.get("all_confidences", {}).values(), reverse=True)
        top_two_margin = round(py_all[0] - py_all[1], 4) if len(py_all) >= 2 else round(py_conf, 4)

        # 3. Category Rules
        cat_info = self.categories_map.get(py_class, {
            "severity": "Informational",
            "min_confidence": self.consensus_rules.get("default_min_confidence", 0.80),
            "top_two_margin": self.consensus_rules.get("default_top_two_margin", 0.15),
            "consecutive_windows_required": 1,
            "require_model_agreement": False,
            "recommended_action": "Log sound event."
        })

        min_conf = cat_info.get("min_confidence", 0.80)
        req_margin = cat_info.get("top_two_margin", 0.15)
        req_agreement = cat_info.get("require_model_agreement", False)
        consecutive_required = cat_info.get("consecutive_windows_required", 1)

        # 4. Determine Model Consistency Status
        if not is_agreement:
            consistency_status = "Model Disagreement"
        elif py_conf < min_conf or gtm_conf < min_conf:
            consistency_status = "Weak Match"
        elif quality_status in ["Poor", "Unusable"] or top_two_margin < req_margin:
            consistency_status = "Uncertain Result"
        else:
            consistency_status = "Acceptable Match"

        # 5. Consecutive Window Confirmation Check
        consecutive_count = 1
        if stream_id:
            history = self._stream_history.setdefault(stream_id, [])
            history.append(py_class)
            if len(history) > 10:
                history.pop(0)
            
            # Count consecutive occurrences of py_class from end of list
            consecutive_count = 0
            for item in reversed(history):
                if item == py_class:
                    consecutive_count += 1
                else:
                    break

        consecutive_satisfied = (consecutive_count >= consecutive_required)

        # 6. Manual Review Requirement Logic
        needs_manual_review = False
        review_reasons = []

        if not is_agreement:
            needs_manual_review = True
            review_reasons.append(f"Model Disagreement: Python ({py_class}) vs GTM ({gtm_class})")

        if py_conf < min_conf:
            needs_manual_review = True
            review_reasons.append(f"Low Python Model Confidence ({py_conf*100:.1f}% < {min_conf*100:.1f}%)")

        if quality_status in ["Poor", "Unusable"]:
            needs_manual_review = True
            review_reasons.append(f"Audio Quality degraded: {quality_status}")

        if top_two_margin < req_margin:
            needs_manual_review = True
            review_reasons.append(f"Top-Two Margin too close ({top_two_margin:.2f} < {req_margin:.2f})")

        # 7. Final Alert Decision
        # An alert is confirmed only if agreement rules & consecutive rules are satisfied
        alert_triggered = False
        final_category = py_class

        if not needs_manual_review and consecutive_satisfied:
            if cat_info["severity"] in ["Critical", "High"]:
                alert_triggered = True
        elif not is_agreement and gtm_conf > py_conf + 0.20:
            # If GTM is drastically higher and they disagreed
            final_category = "Uncertain / " + py_class

        return {
            "final_category": final_category,
            "severity": cat_info.get("severity", "Informational"),
            "model_agreement": is_agreement,
            "consistency_status": consistency_status,
            "confidence_difference": conf_diff,
            "top_two_margin": top_two_margin,
            "alert_triggered": alert_triggered,
            "needs_manual_review": needs_manual_review,
            "review_reasons": review_reasons,
            "consecutive_count": consecutive_count,
            "consecutive_required": consecutive_required,
            "consecutive_satisfied": consecutive_satisfied,
            "recommended_action": cat_info.get("recommended_action", "No action needed."),
            "department": cat_info.get("department", "General")
        }
