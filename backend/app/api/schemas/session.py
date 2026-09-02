from pydantic import BaseModel, UUID4
from typing import Optional, List
from datetime import datetime

class SessionResponse(BaseModel):
    id: UUID4
    caller_id: Optional[UUID4]
    start_time: datetime
    end_time: Optional[datetime]
    status: str
    avg_risk_score: Optional[float]
    created_at: datetime

    class Config:
        from_attributes = True

class SessionTimelineItem(BaseModel):
    chunk_index: int
    timestamp: datetime
    risk_score: float
    risk_level: str
    deepfake_probability: float
    speaker_similarity: Optional[float]
    prosody_score: float
    context_score: float

    class Config:
        from_attributes = True
