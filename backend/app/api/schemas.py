from pydantic import BaseModel, Field, field_serializer
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import uuid

def _ensure_utc(dt: Optional[datetime]) -> Optional[str]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.isoformat()

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
    
    @field_serializer("created_at")
    def serialize_created_at(self, dt: datetime, _info):
        return _ensure_utc(dt)

    model_config = {"from_attributes": True}

class RiskScoreComponents(BaseModel):
    deepfake: float
    speaker: float
    prosody: float

class RiskScoreResponse(BaseModel):
    score: float
    level: str
    raw_components: RiskScoreComponents
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    @field_serializer("timestamp")
    def serialize_ts(self, dt: datetime, _info):
        return _ensure_utc(dt)

class AlertResponse(BaseModel):
    id: uuid.UUID
    session_id: uuid.UUID
    severity: str
    trigger_reason: str
    risk_score: float
    created_at: datetime
    
    @field_serializer("created_at")
    def serialize_alert_dt(self, dt: datetime, _info):
        return _ensure_utc(dt)

    model_config = {"from_attributes": True}

class DetectionSessionResponse(BaseModel):
    id: uuid.UUID = Field(alias="session_id")
    caller_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    avg_risk_score: Optional[float] = None
    status: str

    @field_serializer("start_time", "end_time")
    def serialize_session_dt(self, dt: Optional[datetime], _info):
        return _ensure_utc(dt)

    model_config = {"from_attributes": True, "populate_by_name": True}
