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

router = APIRouter()


@router.websocket("/ws/stream")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time audio analysis over WebSocket.

    Accepts binary PCM audio chunks (16-bit, 16 kHz, mono), buffers
    them into 2-second windows with 250 ms hop, runs the full ML
    pipeline, and returns JSON risk scores.
    """
    await websocket.accept()

    # ── Per-session state ─────────────────────────────────────────────
    session_id = uuid.uuid4()
    buffer = CircularAudioBuffer()
    risk_scorer = RiskScorer()
    session_embeddings: list[np.ndarray] = []
    enrollment_embedding: np.ndarray | None = None  # TODO: load from DB on connect

    pipeline = InferencePipeline.get_instance()

    print(f"[WS] Session {session_id} — client connected")

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
                    )

                    # Enrich with metadata
                    result["session_id"] = str(session_id)
                    result["timestamp"] = datetime.now(timezone.utc).isoformat()
                    result["latency_ms"] = ml_result["latency_ms"]
                    result["speech_probability"] = round(speech_prob, 3)

                    # Include per-model detail
                    result["model_detail"] = {
                        "aasist_score": ml_result["deepfake"].get("aasist_score"),
                        "xlsr_score": ml_result["deepfake"].get("xlsr_score"),
                        "prosody": ml_result["prosody"],
                        "speaker_verified": ml_result["speaker"]["is_verified"],
                    }

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
