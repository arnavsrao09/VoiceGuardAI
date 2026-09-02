from typing import Optional, Tuple
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class RiskScorer:
    def __init__(self):
        self.ema_alpha = settings.EMA_ALPHA
        self.deepfake_weight = settings.DEEPFAKE_WEIGHT
        self.speaker_weight = settings.SPEAKER_WEIGHT
        self.prosody_weight = settings.PROSODY_WEIGHT
        self.context_weight = settings.CONTEXT_WEIGHT

    def get_risk_level(self, score: float) -> str:
        if score >= settings.HIGH_RISK_THRESHOLD:
            return "CRITICAL"
        elif score >= settings.MEDIUM_RISK_THRESHOLD:
            return "HIGH"
        elif score >= settings.LOW_RISK_THRESHOLD:
            return "MEDIUM"
        else:
            return "LOW"

    def calculate_raw_score(
        self,
        deepfake_prob: float,
        speaker_sim: Optional[float],
        prosody_anomaly: float,
        context_score: float
    ) -> float:
        """
        Calculate raw risk score.
        If speaker_sim is unavailable (None), renormalize weights.
        Note: lower speaker similarity -> higher risk. So mismatch = 1.0 - sim.
        """
        active_weights = {
            "deepfake": self.deepfake_weight,
            "prosody": self.prosody_weight,
            "context": self.context_weight
        }
        
        scores = {
            "deepfake": deepfake_prob,
            "prosody": prosody_anomaly,
            "context": context_score
        }

        if speaker_sim is not None:
            active_weights["speaker"] = self.speaker_weight
            scores["speaker"] = 1.0 - speaker_sim # Mismatch score

        total_weight = sum(active_weights.values())
        
        weighted_sum = sum(
            scores[k] * active_weights[k]
            for k in active_weights.keys()
        )
        
        return min(max(weighted_sum / total_weight, 0.0), 1.0)

    def apply_ema(self, current_raw: float, previous_smoothed: Optional[float]) -> float:
        if previous_smoothed is None:
            return current_raw
        
        return (self.ema_alpha * current_raw) + ((1.0 - self.ema_alpha) * previous_smoothed)

    def generate_alert_message(self, level: str, raw_components: dict) -> Optional[str]:
        if level in ["HIGH", "CRITICAL"]:
            reasons = []
            if raw_components.get("deepfake_probability", 0) > 0.7:
                reasons.append("High synthetic speech probability")
            if raw_components.get("speaker_similarity") is not None and raw_components["speaker_similarity"] < settings.SPEAKER_SIMILARITY_THRESHOLD:
                reasons.append("Speaker mismatch detected")
            if raw_components.get("prosody_anomaly", 0) > 0.7:
                reasons.append("Anomalous vocal prosody")
            if raw_components.get("context_score", 0) > 0.7:
                reasons.append("High-risk context flags")
                
            if not reasons:
                reasons.append("Elevated overall risk score")
                
            return "Alert: " + " | ".join(reasons)
        return None
