from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from app.api import schemas
from app.ml.pipeline import InferencePipeline
from app.api.deps import SECRET_KEY, ALGORITHM
from jose import jwt, JWTError
import uuid
import io
import numpy as np
import librosa

router = APIRouter()

def _extract_org_id_from_request(request: Request) -> uuid.UUID | None:
    """Optionally extract organization_id from JWT Bearer token. Returns None if no valid token."""
    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return None
    token = auth_header.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        org_id_str = payload.get("sub")
        if org_id_str:
            return uuid.UUID(org_id_str)
    except (JWTError, ValueError):
        pass
    return None

@router.post("/speakers/enroll", response_model=schemas.SpeakerProfileResponse)
async def enroll_speaker(
    request: Request,
    user_id: str = Form(...),
    name: str = Form(...),
    language: str = Form("en"),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    organization_id = _extract_org_id_from_request(request)
    
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
        organization_id=organization_id,
        external_user_id=user_id, 
        name=name, 
        embedding=embedding,
        language=language
    )
    return {
        "id": db_profile.id,
        "user_id": db_profile.external_user_id,
        "name": db_profile.name,
        "language": db_profile.language,
        "created_at": db_profile.created_at,
    }

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

@router.post("/speakers/verify")
async def verify_speaker(
    profile_id: uuid.UUID = Form(...),
    audio: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    profile = await crud.get_voice_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="Speaker profile not found")

    try:
        audio_bytes = await audio.read()
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)

        pipeline = InferencePipeline.get_instance()
        enrolled_emb = np.array(profile.embedding, dtype=np.float32)
        res = pipeline.verifier.verify_against_profile(y, enrolled_emb)

        return {
            "profile_id": str(profile.id),
            "profile_name": profile.name,
            "similarity": res["similarity"],
            "match_percentage": round(max(0, res["similarity"]) * 100, 1),
            "is_verified": res["is_verified"],
            "threshold": 0.75
        }
    except Exception as e:
        print(f"Verification Error: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to verify audio: {str(e)}")

