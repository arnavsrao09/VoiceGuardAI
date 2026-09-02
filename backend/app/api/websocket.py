from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from sqlalchemy.ext.asyncio import AsyncSession
import json
import logging
from uuid import UUID
from datetime import datetime, timezone

from app.core.dependencies import get_db_session
from app.audio.buffer import AudioRingBuffer
from app.audio.preprocessing import preprocess_pcm_chunk
from app.audio.vad import vad_service
from app.ml.model_manager import model_manager
from app.db import crud
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

@router.websocket("/analyze")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    # We must manage the DB session manually in the websocket lifecycle
    # since Depends is not easily scoped to the entire WS session duration
    db_gen = get_db_session()
    db: AsyncSession = await anext(db_gen)
    
    session_id = None
    buffer = AudioRingBuffer()
    speaker_profile = None
    context_score = 0.0
    previous_smoothed_score = None
    chunk_index = 0
    
    try:
        # First message should be JSON config
        config_text = await websocket.receive_text()
        config = json.loads(config_text)
        
        if config.get("type") != "start":
            await websocket.close(code=1003, reason="Expected start config")
            return
            
        speaker_id = config.get("speaker_id")
        if speaker_id:
            speaker_profile = await crud.get_voice_profile(db, UUID(speaker_id))
            
        context_score = model_manager.context.analyze(
            transaction_type=config.get("transaction_type"),
            transaction_amount=config.get("transaction_amount", 0.0),
            known_contact=config.get("known_contact", False),
            urgency=config.get("urgency", False)
        )
        
        # Create detection session
        det_session = await crud.create_session(db, UUID(speaker_id) if speaker_id else None)
        session_id = det_session.id
        
        await websocket.send_json({"type": "session_started", "session_id": str(session_id)})
        
        while True:
            # Receive binary PCM chunks
            data = await websocket.receive_bytes()
            
            try:
                audio_np = preprocess_pcm_chunk(data)
                buffer.add_audio(audio_np)
                
                # We analyze every hop_samples (e.g. 250ms)
                # For simplicity, if we have a full window, we analyze and shift.
                # The ring buffer currently just returns the latest window.
                # In real time, we want to make sure we only analyze once every 250ms of NEW audio.
                
                # Check if we should analyze:
                # We added len(audio_np) samples.
                buffer.processed_samples += len(audio_np)
                
                if buffer.processed_samples >= buffer.hop_samples:
                    buffer.processed_samples = 0 # reset counter
                    
                    window = buffer.get_analysis_window()
                    if window is not None:
                        # VAD Check
                        is_speech = await vad_service.is_speech(window)
                        if not is_speech:
                            continue
                            
                        # Run ML Pipeline
                        deepfake_prob = await model_manager.aasist.predict(window, 16000)
                        
                        speaker_sim = None
                        if speaker_profile:
                            curr_emb = await model_manager.ecapa.extract_embedding(window, 16000)
                            speaker_sim = await model_manager.ecapa.compare(curr_emb, speaker_profile.embedding)
                            
                        prosody_res = await model_manager.prosody.analyze(window, 16000)
                        prosody_anomaly = prosody_res.get("anomaly_score", 0.0)
                        
                        raw_score = model_manager.risk_scorer.calculate_raw_score(
                            deepfake_prob, speaker_sim, prosody_anomaly, context_score
                        )
                        
                        smoothed_score = model_manager.risk_scorer.apply_ema(raw_score, previous_smoothed_score)
                        previous_smoothed_score = smoothed_score
                        
                        level = model_manager.risk_scorer.get_risk_level(smoothed_score)
                        
                        alert_msg = model_manager.risk_scorer.generate_alert_message(level, {
                            "deepfake_probability": deepfake_prob,
                            "speaker_similarity": speaker_sim,
                            "prosody_anomaly": prosody_anomaly,
                            "context_score": context_score
                        })
                        
                        # Persist Telemetry
                        await crud.create_telemetry(db, {
                            "session_id": session_id,
                            "chunk_index": chunk_index,
                            "risk_score": smoothed_score,
                            "deepfake_probability": deepfake_prob,
                            "speaker_similarity": speaker_sim,
                            "prosody_score": prosody_anomaly,
                            "context_score": context_score,
                            "risk_level": level,
                            "anomaly_flags": prosody_res
                        })
                        chunk_index += 1
                        
                        if level in ["HIGH", "CRITICAL"]:
                            await crud.create_alert(db, {
                                "session_id": session_id,
                                "severity": level,
                                "trigger_reason": alert_msg or "High risk detected",
                                "risk_score": smoothed_score
                            })
                            
                        # Send JSON update
                        await websocket.send_json({
                            "type": "risk_update",
                            "score": smoothed_score,
                            "level": level,
                            "deepfake_probability": deepfake_prob,
                            "speaker_similarity": speaker_sim,
                            "prosody_anomaly": prosody_anomaly,
                            "context_score": context_score,
                            "alert": alert_msg,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        
            except Exception as e:
                logger.error(f"Error processing WS chunk: {e}")
                
    except WebSocketDisconnect:
        logger.info(f"WebSocket disconnected for session {session_id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if session_id:
            await crud.complete_session(db, session_id, previous_smoothed_score or 0.0)
            
        try:
            await anext(db_gen)
        except StopAsyncIteration:
            pass
