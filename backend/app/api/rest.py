from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from app.api import schemas
from app.ml.pipeline import InferencePipeline
import uuid
import io
import librosa

router = APIRouter()

@router.post("/speakers/enroll", response_model=schemas.SpeakerProfileResponse)
async def enroll_speaker(
    user_id: str = Form(...),
    name: str = Form(...),
    language: str = Form("en"),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    try:
        audio_bytes = await audio.read()
        
        # Load audio and resample to 16000Hz mono
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
        
        # Extract ECAPA-TDNN embedding
        pipeline = InferencePipeline.get_instance()
        embedding_result = pipeline._extract_speaker_only(y)
        
        if embedding_result.get("embedding") is not None:
            embedding = embedding_result["embedding"].tolist()
        else:
            raise ValueError("Embedding extraction returned None.")
            
    except Exception as e:
        print(f"Enrollment Error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to process audio: {str(e)}")

    db_profile = await crud.create_voice_profile(
        db=db, 
        user_id=user_id, 
        name=name, 
        embedding=embedding,
        language=language
    )
    return db_profile

@router.get("/speakers/{profile_id}", response_model=schemas.SpeakerProfileResponse)
async def get_speaker(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    profile = await crud.get_voice_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return profile

@router.get("/speakers", response_model=list[schemas.SpeakerProfileResponse])
async def list_speakers(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_voice_profiles(db)

@router.delete("/speakers/{profile_id}")
async def delete_speaker(profile_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    deleted = await crud.delete_voice_profile(db, profile_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Speaker profile not found")
    return {"detail": "Profile deleted successfully"}

@router.get("/sessions", response_model=list[schemas.DetectionSessionResponse])
async def list_sessions(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_sessions(db)

@router.get("/alerts", response_model=list[schemas.AlertResponse])
async def list_alerts(db: AsyncSession = Depends(get_db)):
    return await crud.get_all_alerts(db)
