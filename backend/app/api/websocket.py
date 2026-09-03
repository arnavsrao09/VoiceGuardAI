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

import asyncio
import uuid
from datetime import datetime, timezone

import numpy as np
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import jwt, JWTError

from app.core.audio_buffer import CircularAudioBuffer, VADSpeechAccumulator
from app.ml.pipeline import InferencePipeline
from app.ml.risk_scorer import RiskScorer
from app.db.database import AsyncSessionLocal
from sqlalchemy import select, update
from app.db import crud
from app.db.models import DetectionSession
from app.api.deps import SECRET_KEY, ALGORITHM
from app.config import settings

router = APIRouter()


@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time audio analysis over WebSocket.

    Accepts binary PCM audio chunks (16-bit, 16 kHz, mono), buffers
    them into 2-second windows with 250 ms hop, runs the full ML
    pipeline, and returns JSON risk scores.
    """
    await websocket.accept()

    # Query params
    query_params = websocket.query_params
    profile_id_param = query_params.get("profile_id")
    token_param = query_params.get("token")

    # ── Resolve organization_id from JWT token ────────────────────────
    organization_id: uuid.UUID | None = None
    if token_param:
        try:
            payload = jwt.decode(token_param, SECRET_KEY, algorithms=[ALGORITHM])
            org_id_str = payload.get("sub")
            if org_id_str:
                organization_id = uuid.UUID(org_id_str)
                print(f"[WS] Authenticated org: {organization_id}")
        except (JWTError, ValueError) as e:
            print(f"[WS] Token decode failed (proceeding without org): {e}")

    # ── Per-session state ─────────────────────────────────────────────
    buffer = CircularAudioBuffer()
    speaker_speech = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    risk_scorer = RiskScorer()
    session_embeddings: list[np.ndarray] = []
    session_risk_scores: list[float] = []
    enrollment_embedding: np.ndarray | None = None
    profile_name: str | None = None
    
    session_max_alert_reason: str | None = None
    session_max_level: str = "LOW"
    stable_speaker_sim: float | None = None
    stable_speaker_verified = False
    speaker_ema_alpha = 0.4
    session_speaker_drift = 0.0

    pipeline = InferencePipeline.get_instance()

    # Load speaker profile embedding if profile_id provided
    if profile_id_param:
        try:
            profile_uuid = uuid.UUID(profile_id_param)
            async with AsyncSessionLocal() as db:
                prof = await crud.get_voice_profile(db, profile_uuid, organization_id=organization_id)
                if not prof and organization_id is not None:
                    # Fallback lookup in case profile was created without org scoping
                    prof = await crud.get_voice_profile(db, profile_uuid)
                if prof and prof.embedding:
                    enrollment_embedding = pipeline.verifier._l2_normalize(prof.embedding)
                    profile_name = prof.name
                    print(
                        f"[WS] Loaded speaker profile '{prof.name}' ({profile_uuid}) "
                        f"shape={enrollment_embedding.shape}, norm={np.linalg.norm(enrollment_embedding):.4f}"
                    )
        except Exception as e:
            print(f"[WS] Failed to load profile {profile_id_param}: {e}")

    # Create session in DB with organization_id
    caller_label = f"Stream ({profile_name})" if profile_name else "Live Stream"
    async with AsyncSessionLocal() as db:
        db_session = await crud.create_detection_session(db, caller_id=caller_label, organization_id=organization_id)
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
                    speaker_speech.add_frames(audio_array)

                # Speaker ECAPA: only on 1.5–3 s of accumulated VAD speech, 1 s hop.
                if speaker_speech.ready_for_embed():
                    speech_window = speaker_speech.get_window()
                    if len(speech_window) > 0:
                        if enrollment_embedding is not None:
                            speaker_result = await asyncio.to_thread(
                                pipeline.verifier.verify_against_profile,
                                speech_window,
                                enrollment_embedding,
                            )
                            raw_sim = float(speaker_result.get("similarity", 0.0))
                            if np.isnan(raw_sim) or np.isinf(raw_sim):
                                raw_sim = 0.0
                            if stable_speaker_sim is None:
                                stable_speaker_sim = raw_sim
                            else:
                                stable_speaker_sim = (
                                    speaker_ema_alpha * raw_sim
                                    + (1.0 - speaker_ema_alpha) * stable_speaker_sim
                                )
                            th = float(
                                speaker_result.get("threshold")
                                or settings.speaker_verification_threshold
                            )
                            stable_speaker_verified = bool(stable_speaker_sim >= th)
                            print(
                                f"[SPEAKER UPDATE] raw_sim={raw_sim:.4f}, "
                                f"ema_sim={stable_speaker_sim:.4f}, "
                                f"threshold={th:.4f}, "
                                f"verified={stable_speaker_verified}"
                            )
                        else:
                            emb = await asyncio.to_thread(
                                pipeline.verifier.extract_embedding,
                                speech_window
                            )
                            speaker_result = {"embedding": emb}

                        emb = speaker_result.get("embedding")
                        if emb is not None:
                            if len(session_embeddings) >= 2:
                                session_speaker_drift = pipeline.verifier.detect_drift(emb, session_embeddings)
                            
                            session_embeddings.append(emb)
                            if len(session_embeddings) > 20:
                                session_embeddings = session_embeddings[-20:]

                # ── Run inference when buffer is ready ────────────────
                if buffer.is_ready_for_inference():
                    window = buffer.get_window()

                    # Deepfake/prosody on the hop window. Speaker identity is
                    # overlaid from the aggregated speech evidence above.
                    ml_result = await pipeline.process_chunk(
                        window,
                        skip_speaker=True
                    )

                    th = settings.speaker_verification_threshold
                    if enrollment_embedding is not None and stable_speaker_sim is not None:
                        ml_result["speaker"]["similarity"] = round(float(stable_speaker_sim), 4)
                        ml_result["speaker"]["is_verified"] = bool(stable_speaker_verified)
                        ml_result["speaker"]["threshold"] = round(float(th), 4)
                        ml_result["speaker"]["margin"] = round(float(stable_speaker_sim - th), 4)
                    else:
                        ml_result["speaker"]["similarity"] = 0.0
                        ml_result["speaker"]["is_verified"] = False

                    # Compute risk score
                    result = risk_scorer.compute_score(
                        deepfake_prob=ml_result["deepfake"]["spoof_probability"],
                        speaker_match=ml_result["speaker"]["similarity"],
                        prosody_anomaly=ml_result["prosody"]["prosody_anomaly_score"],
                        speaker_drift=session_speaker_drift,
                        deepfake_confidence=ml_result["deepfake"]["confidence"],
                        has_enrollment=(
                            enrollment_embedding is not None
                            and stable_speaker_sim is not None
                        ),
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
                        "speaker_similarity": max(0.0, float(ml_result["speaker"]["similarity"])),
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
                            session_max_alert_reason = result["alert_reason"]
                            session_max_level = result["level"].upper()
                            
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
        speaker_speech.clear()
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
                    final_score = round(float(session_risk_scores[-1]), 3)
                    sess.avg_risk_score = final_score
                    
                    if session_max_alert_reason:
                        await crud.create_alert(
                            db,
                            session_id=session_id,
                            severity=session_max_level,
                            trigger_reason=session_max_alert_reason,
                            risk_score=final_score,
                            organization_id=organization_id
                        )
                await db.commit()
