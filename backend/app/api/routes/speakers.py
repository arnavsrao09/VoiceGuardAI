from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from typing import List
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.dependencies import get_db
from app.api.schemas.speaker import SpeakerResponse, SpeakerEnrollResponse
from app.db import crud
from app.audio.preprocessing import preprocess_audio
from app.ml.model_manager import model_manager

router = APIRouter()

@router.post("/enroll", response_model=SpeakerEnrollResponse)
async def enroll_speaker(
    name: str = Form(...),
    language: str = Form(None),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    audio_bytes = await audio.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    try:
        audio_np = preprocess_audio(audio_bytes, 16000)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    embedding = await model_manager.ecapa.extract_embedding(audio_np, 16000)
    
    # Store in DB
    profile = await crud.create_voice_profile(
        db=db,
        name=name,
        language=language,
        embedding=embedding.tolist()
    )

    return SpeakerEnrollResponse(
        id=profile.id,
        name=profile.name,
        language=profile.language,
        message="Speaker enrolled successfully"
    )

@router.get("", response_model=List[SpeakerResponse])
async def list_speakers(skip: int = 0, limit: int = 100, db: AsyncSession = Depends(get_db)):
    profiles = await crud.get_voice_profiles(db, skip=skip, limit=limit)
    return profiles

@router.get("/{speaker_id}", response_model=SpeakerResponse)
async def get_speaker(speaker_id: UUID, db: AsyncSession = Depends(get_db)):
    profile = await crud.get_voice_profile(db, speaker_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return profile

@router.delete("/{speaker_id}")
async def delete_speaker(speaker_id: UUID, db: AsyncSession = Depends(get_db)):
    success = await crud.delete_voice_profile(db, speaker_id)
    if not success:
        raise HTTPException(status_code=404, detail="Speaker not found")
    return {"message": "Speaker deleted"}
