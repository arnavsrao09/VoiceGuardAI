from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid

class SpeakerProfileCreate(BaseModel):
    user_id: str
    name: str
    language: str = "en"

class SpeakerProfileResponse(BaseModel):
    id: uuid.UUID
    user_id: str
    name: str
    language: str
    created_at: datetime
    
    model_config = {"from_attributes": True}

class RiskScoreComponents(BaseModel):
    deepfake: float
    speaker: float
    prosody: float

class RiskScoreResponse(BaseModel):
    score: float
    level: str
    raw_components: RiskScoreComponents
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class AlertResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    severity: str
    trigger_reason: str
    risk_score: float
    created_at: datetime
    
    model_config = {"from_attributes": True}
