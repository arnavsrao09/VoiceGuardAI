from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

class AlertResponse(BaseModel):
    id: UUID4
    session_id: UUID4
    severity: str
    trigger_reason: str
    risk_score: float
    acknowledged: bool
    acknowledged_at: Optional[datetime]
    action_taken: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True

class AlertAcknowledgeRequest(BaseModel):
    action_taken: Optional[str] = None
