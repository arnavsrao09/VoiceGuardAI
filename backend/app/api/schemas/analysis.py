from pydantic import BaseModel, UUID4, Field
from typing import Optional, List, Dict
from datetime import datetime

class AnalysisRequest(BaseModel):
    speaker_id: Optional[UUID4] = None
    transaction_type: Optional[str] = None
    transaction_amount: Optional[float] = 0.0
    known_contact: Optional[bool] = False
    urgency: Optional[bool] = False

class RiskScoreResponse(BaseModel):
    session_id: UUID4
    score: float
    level: str
    deepfake_probability: float
    speaker_similarity: Optional[float]
    prosody_anomaly: float
    context_score: float
    alert: Optional[str] = None
