from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.database import get_db
from app.db import crud
from app.db.models import ApiKey
from app.api.deps import verify_api_key
from app.api import schemas
from app.ml.pipeline import InferencePipeline
from app.ml.risk_scorer import RiskScorer
import io
import librosa
import numpy as np

router = APIRouter()

@router.post("/enroll", response_model=schemas.SpeakerProfileResponse)
async def b2b_enroll(
    external_user_id: str = Form(...),
    name: str = Form(...),
    language: str = Form("en"),
    audio: UploadFile = File(...),
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Enroll a user's voice for a specific organization using external_user_id."""
    try:
        audio_bytes = await audio.read()
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
        
        pipeline = InferencePipeline.get_instance()
        embedding_result = pipeline._extract_speaker_only(y)

        if embedding_result.get("embedding") is not None:
            embedding = embedding_result["embedding"].tolist()
        else:
            raise ValueError("Embedding extraction returned None.")
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to process audio: {str(e)}")

    db_profile = await crud.create_voice_profile(
        db=db, 
        organization_id=api_key.organization_id,
        external_user_id=external_user_id, 
        name=name, 
        embedding=embedding,
        language=language
    )
    
    # We need to adapt the db_profile to schemas.SpeakerProfileResponse which expects `user_id`
    # Let's map external_user_id to user_id for the response schema compatibility,
    # or better, just create a dict
    return {
        "id": db_profile.id,
        "user_id": db_profile.external_user_id,
        "name": db_profile.name,
        "language": db_profile.language,
        "created_at": db_profile.created_at
    }

@router.post("/detect", response_model=schemas.RiskScoreResponse)
async def b2b_detect(
    audio: UploadFile = File(...),
    external_user_id: str = Form(None),
    api_key: ApiKey = Depends(verify_api_key),
    db: AsyncSession = Depends(get_db)
):
    """Detect voice cloning risk on an audio file. If external_user_id is provided, verify speaker."""
    try:
        audio_bytes = await audio.read()
        y, sr = librosa.load(io.BytesIO(audio_bytes), sr=16000, mono=True)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to load audio: {str(e)}")
        
    enrollment_embedding = None
    if external_user_id:
        profile = await crud.get_voice_profile_by_external_id(db, external_user_id, api_key.organization_id)
        if profile and profile.embedding:
            enrollment_embedding = np.array(profile.embedding, dtype=np.float32)
            
    caller_label = f"B2B ({external_user_id})" if external_user_id else "B2B Upload"
    session = await crud.create_detection_session(db, caller_id=caller_label, organization_id=api_key.organization_id, api_key_id=api_key.id)

    try:
        pipeline = InferencePipeline.get_instance()
        ml_result = await pipeline.process_chunk(
            y,
            enrollment_embedding=enrollment_embedding,
            session_embeddings=[]
        )
        
        scorer = RiskScorer()
        result = scorer.compute_score(
            deepfake_prob=ml_result["deepfake"]["spoof_probability"],
            speaker_match=ml_result["speaker"]["similarity"],
            prosody_anomaly=ml_result["prosody"]["prosody_anomaly_score"],
            speaker_drift=0.0,
            deepfake_confidence=ml_result["deepfake"]["confidence"],
            has_enrollment=(enrollment_embedding is not None)
        )
        
        # Save score and end session
        session.avg_risk_score = round(float(result["score"]), 3)
        session.status = "ended"
        
        if result["should_alert"] and result["alert_reason"]:
            await crud.create_alert(
                db,
                session_id=session.session_id,
                severity=result["level"].upper(),
                trigger_reason=result["alert_reason"],
                risk_score=result["score"],
                organization_id=api_key.organization_id
            )
            
        await db.commit()
        
        return schemas.RiskScoreResponse(
            score=result["score"],
            level=result["level"],
            threat_category=result["threat_category"],
            action_recommendation=result["action_recommendation"],
            is_same_speaker=result["is_same_speaker"],
            speaker_similarity=result["speaker_similarity"],
            deepfake_score=result["deepfake_score"],
            raw_components=schemas.RiskScoreComponents(
                deepfake=ml_result["deepfake"]["spoof_probability"],
                speaker=ml_result["speaker"]["similarity"] if enrollment_embedding is not None else 0.0,
                prosody=ml_result["prosody"]["prosody_anomaly_score"],
                aasist=ml_result["deepfake"].get("aasist_score"),
                xlsr=ml_result["deepfake"].get("xlsr_score"),
                speaker_drift=ml_result.get("speaker_drift", 0.0),
            )
        )
        
    except Exception as e:
        session.status = "error"
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Inference error: {str(e)}")

@router.get("/sessions", response_model=list[schemas.DetectionSessionResponse])
async def list_org_sessions(api_key: ApiKey = Depends(verify_api_key), db: AsyncSession = Depends(get_db)):
    """List detection sessions for this organization."""
    return await crud.get_all_sessions(db, organization_id=api_key.organization_id)
