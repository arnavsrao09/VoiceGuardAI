from pydantic import BaseModel, UUID4
from typing import Optional
from datetime import datetime

class SpeakerEnrollResponse(BaseModel):
    id: UUID4
    name: str
    language: Optional[str]
    message: str

class SpeakerResponse(BaseModel):
    id: UUID4
    name: str
    language: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
