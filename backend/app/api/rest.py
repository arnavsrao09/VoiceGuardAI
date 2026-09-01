from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from app.api import schemas
import uuid

router = APIRouter()

@router.post("/speakers/enroll", response_model=schemas.SpeakerProfileResponse)
async def enroll_speaker(profile: schemas.SpeakerProfileCreate, db: AsyncSession = Depends(get_db)):
    # In a real scenario, this would accept an audio file upload, extract embedding, and store it.
    # For now, we mock the embedding extraction.
    import numpy as np
    mock_embedding = list(np.random.randn(192).astype(float))
    
    db_profile = await crud.create_voice_profile(
        db=db, 
        user_id=profile.user_id, 
        name=profile.name, 
        embedding=mock_embedding,
        language=profile.language
    )
    return db_profile

@router.get("/speakers/{profile_id}", response_model=schemas.SpeakerProfileResponse)
async def get_speaker(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    profile = await crud.get_voice_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return profile
