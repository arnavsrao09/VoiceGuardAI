from fastapi import APIRouter, File, UploadFile, Form, Depends, HTTPException
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID

from app.core.dependencies import get_db
from app.audio.preprocessing import preprocess_audio
from app.audio.vad import vad_service
from app.audio.buffer import AudioRingBuffer
from app.ml.model_manager import model_manager
from app.api.schemas.analysis import RiskScoreResponse
from app.db import crud

router = APIRouter()

@router.post("/analyze/file", response_model=RiskScoreResponse)
async def analyze_file(
    file: UploadFile = File(...),
    speaker_id: Optional[UUID] = Form(None),
    transaction_type: Optional[str] = Form(None),
    transaction_amount: Optional[float] = Form(0.0),
    known_contact: Optional[bool] = Form(False),
    urgency: Optional[bool] = Form(False),
    db: AsyncSession = Depends(get_db)
):
    """
    Analyze an uploaded audio file.
    """
    # 1. Read Audio
    audio_bytes = await file.read()
    if not audio_bytes:
        raise HTTPException(status_code=400, detail="Empty audio file")

    # 2. Preprocess
    try:
        audio_np = preprocess_audio(audio_bytes, 16000)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

    # 3. Session creation
    session = await crud.create_session(db)

    # 4. We will treat the whole file as one window for simplicity in the file endpoint.
    # In a real scenario, we might iterate if it's very long, but for a 4s chunk we just pad/truncate.
    buffer = AudioRingBuffer()
    buffer.add_audio(audio_np)
    window = buffer.get_all_padded()

    # VAD check
    has_speech = await vad_service.is_speech(window)
    if not has_speech:
        await crud.complete_session(db, session.id, 0.0)
        return RiskScoreResponse(
            session_id=session.id,
            score=0.0,
            level="LOW",
            deepfake_probability=0.0,
            speaker_similarity=None,
            prosody_anomaly=0.0,
            context_score=0.0,
            alert="No speech detected"
        )

    # 5. ML Inference
    deepfake_prob = await model_manager.aasist.predict(window, 16000)
    
    speaker_sim = None
    if speaker_id:
        profile = await crud.get_voice_profile(db, speaker_id)
        if profile:
            current_emb = await model_manager.ecapa.extract_embedding(window, 16000)
            speaker_sim = await model_manager.ecapa.compare(current_emb, profile.embedding)

    prosody_results = await model_manager.prosody.analyze(window, 16000)
    prosody_anomaly = prosody_results.get("anomaly_score", 0.0)

    context_score = model_manager.context.analyze(
        transaction_type=transaction_type,
        transaction_amount=transaction_amount,
        known_contact=known_contact,
        urgency=urgency
    )

    # 6. Risk Scoring
    raw_score = model_manager.risk_scorer.calculate_raw_score(
        deepfake_prob, speaker_sim, prosody_anomaly, context_score
    )
    
    # EMA isn't super useful for a single file unless it's a sequence of chunks, but we apply it raw
    final_score = raw_score
    level = model_manager.risk_scorer.get_risk_level(final_score)
    
    alert_msg = model_manager.risk_scorer.generate_alert_message(level, {
        "deepfake_probability": deepfake_prob,
        "speaker_similarity": speaker_sim,
        "prosody_anomaly": prosody_anomaly,
        "context_score": context_score
    })

    # 7. Persist Telemetry & Alert
    await crud.create_telemetry(db, {
        "session_id": session.id,
        "chunk_index": 0,
        "risk_score": final_score,
        "deepfake_probability": deepfake_prob,
        "speaker_similarity": speaker_sim,
        "prosody_score": prosody_anomaly,
        "context_score": context_score,
        "risk_level": level,
        "anomaly_flags": prosody_results
    })

    if level in ["HIGH", "CRITICAL"]:
        await crud.create_alert(db, {
            "session_id": session.id,
            "severity": level,
            "trigger_reason": alert_msg or "High risk detected",
            "risk_score": final_score
        })

    await crud.complete_session(db, session.id, final_score)

    return RiskScoreResponse(
        session_id=session.id,
        score=final_score,
        level=level,
        deepfake_probability=deepfake_prob,
        speaker_similarity=speaker_sim,
        prosody_anomaly=prosody_anomaly,
        context_score=context_score,
        alert=alert_msg
    )
