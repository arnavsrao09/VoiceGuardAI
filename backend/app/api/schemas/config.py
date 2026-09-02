from pydantic import BaseModel

class ThresholdConfigUpdate(BaseModel):
    vad_threshold: float
    deepfake_weight: float
    speaker_weight: float
    prosody_weight: float
    context_weight: float
    ema_alpha: float
    low_risk_threshold: float
    medium_risk_threshold: float
    high_risk_threshold: float
    speaker_similarity_threshold: float
