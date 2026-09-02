"""
WebSocket endpoint for real-time audio streaming and analysis.

Protocol:
    Client → Server:  binary PCM frames (16-bit, 16 kHz, mono)
    Server → Client:  JSON risk score updates (every ~250 ms hop)

Each WebSocket connection gets its own:
- CircularAudioBuffer (2 s window, 250 ms hop)
- RiskScorer (with EMA smoothing)
- Session embedding history (for drift detection)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.audio_buffer import CircularAudioBuffer
from app.ml.pipeline import InferencePipeline
from app.ml.risk_scorer import RiskScorer
from app.db.database import AsyncSessionLocal
from sqlalchemy import select, update
from app.db import crud
from app.db.models import DetectionSession

router = APIRouter()


@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time audio analysis over WebSocket.

    Accepts binary PCM audio chunks (16-bit, 16 kHz, mono), buffers
    them into 2-second windows with 250 ms hop, runs the full ML
    pipeline, and returns JSON risk scores.
    """
    await websocket.accept()

    # Query param: profile_id
    query_params = websocket.query_params
    profile_id_param = query_params.get("profile_id")

    # ── Per-session state ─────────────────────────────────────────────
    buffer = CircularAudioBuffer()
    risk_scorer = RiskScorer()
    session_embeddings: list[np.ndarray] = []
    session_risk_scores: list[float] = []
    enrollment_embedding: np.ndarray | None = None
    profile_name: str | None = None

    pipeline = InferencePipeline.get_instance()

    # Load speaker profile embedding if profile_id provided
    if profile_id_param:
        try:
            profile_uuid = uuid.UUID(profile_id_param)
            async with AsyncSessionLocal() as db:
                prof = await crud.get_voice_profile(db, profile_uuid)
                if prof and prof.embedding:
                    enrollment_embedding = np.array(prof.embedding, dtype=np.float32)
                    profile_name = prof.name
                    print(f"[WS] Loaded speaker profile '{prof.name}' ({profile_uuid})")
        except Exception as e:
            print(f"[WS] Failed to load profile {profile_id_param}: {e}")

    # Create session in DB
    caller_label = f"Stream ({profile_name})" if profile_name else "Live Stream"
    async with AsyncSessionLocal() as db:
        db_session = await crud.create_detection_session(db, caller_id=caller_label)
        session_id = db_session.session_id

    print(f"[WS] Session {session_id} — client connected (Profile: {profile_name or 'None'})")

    try:
        while True:
            data = await websocket.receive()

            # ── Handle binary PCM audio ───────────────────────────────
            if "bytes" in data and data["bytes"]:
                raw = data["bytes"]
                audio_array = (
                    np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
                )

                # VAD check — only buffer speech
                speech_prob = pipeline.vad.is_speech(audio_array)
                is_speech = pipeline.vad.update_state(
                    speech_prob, len(audio_array)
                )

                if is_speech:
                    buffer.add_frames(audio_array)

                # ── Run inference when buffer is ready ────────────────
                if buffer.is_ready_for_inference():
                    window = buffer.get_window()

                    # Run the full ML pipeline (concurrent)
                    ml_result = await pipeline.process_chunk(
                        window,
                        enrollment_embedding=enrollment_embedding,
                        session_embeddings=session_embeddings,
                    )

                    # Track embeddings for drift detection
                    emb = ml_result["speaker"].get("embedding")
                    if emb is not None:
                        session_embeddings.append(emb)
                        # Keep only last 20 embeddings to bound memory
                        if len(session_embeddings) > 20:
                            session_embeddings = session_embeddings[-20:]

                    # Compute risk score
                    result = risk_scorer.compute_score(
                        deepfake_prob=ml_result["deepfake"]["spoof_probability"],
                        speaker_match=ml_result["speaker"]["similarity"],
                        prosody_anomaly=ml_result["prosody"]["prosody_anomaly_score"],
                        speaker_drift=ml_result["speaker_drift"],
                        deepfake_confidence=ml_result["deepfake"]["confidence"],
                        has_enrollment=(enrollment_embedding is not None),
                    )

                    # Track scores for average calculation
                    session_risk_scores.append(result["score"])

                    # Enrich with metadata
                    result["session_id"] = str(session_id)
                    result["timestamp"] = datetime.now(timezone.utc).isoformat()
                    result["latency_ms"] = ml_result["latency_ms"]
                    result["speech_probability"] = round(speech_prob, 3)
                    result["profile_name"] = profile_name

                    # Include per-model detail
                    result["model_detail"] = {
                        "aasist_score": ml_result["deepfake"].get("aasist_score"),
                        "xlsr_score": ml_result["deepfake"].get("xlsr_score"),
                        "prosody": ml_result["prosody"],
                        "speaker_verified": ml_result["speaker"]["is_verified"],
                        "speaker_similarity": ml_result["speaker"]["similarity"],
                    }

                    # Continuously persist latest risk score to DetectionSession in DB
                    async with AsyncSessionLocal() as db:
                        stmt = (
                            update(DetectionSession)
                            .where(DetectionSession.session_id == session_id)
                            .values(avg_risk_score=round(float(result["score"]), 3))
                        )
                        await db.execute(stmt)
                        if result["should_alert"] and result["alert_reason"]:
                            await crud.create_alert(
                                db,
                                session_id=session_id,
                                severity=result["level"].upper(),
                                trigger_reason=result["alert_reason"],
                                risk_score=result["score"]
                            )
                        await db.commit()

                    await websocket.send_json(result)

            # ── Handle JSON text messages (config, enrollment, etc.) ──
            elif "text" in data and data["text"]:
                # Reserved for future commands (e.g. set enrollment)
                pass

    except WebSocketDisconnect:
        print(f"[WS] Session {session_id} — client disconnected")
    except Exception as e:
        print(f"[WS] Session {session_id} — error: {e}")
    finally:
        buffer.clear()
        risk_scorer.reset()
        pipeline.vad.reset()
        session_embeddings.clear()
        
        # End session in DB and store final risk score
        async with AsyncSessionLocal() as db:
            stmt = select(DetectionSession).where(DetectionSession.session_id == session_id)
            res = await db.execute(stmt)
            sess = res.scalar_one_or_none()
            if sess:
                sess.end_time = datetime.utcnow()
                sess.status = "ended"
                if session_risk_scores:
                    # Save final risk score when user stops recording
                    sess.avg_risk_score = round(float(session_risk_scores[-1]), 3)
                await db.commit()
