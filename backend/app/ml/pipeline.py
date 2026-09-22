"""
Central inference pipeline orchestrator.

``InferencePipeline`` is a **singleton** that owns the lifecycle of every
ML component (VAD, feature extractor, deepfake detector, speaker verifier,
prosody analyser).  It coordinates concurrent inference via
``asyncio.gather`` + ``asyncio.to_thread`` so the event loop stays
unblocked.

Usage::

    from app.ml.pipeline import InferencePipeline

    pipeline = InferencePipeline.get_instance()  # loads models once
    pipeline.warmup()                              # optional: pre-warm ONNX

    result = await pipeline.process_chunk(audio, enrollment_emb)
"""

from __future__ import annotations

import asyncio
import time
from typing import ClassVar, Optional

import numpy as np

from app.core.feature_extraction import FeatureExtractor
from app.core.vad import SileroVADWrapper
from app.ml.deepfake_detector import DeepfakeDetector
from app.ml.prosody_analyzer import ProsodyAnalyzer
from app.ml.speaker_verifier import SpeakerVerifier
from app.logging_config import get_logger

logger = get_logger("pipeline")


class InferencePipeline:
    """Singleton ML inference pipeline.

    Loads all models once on first instantiation, then re-uses them for
    every call to :meth:`process_chunk`.
    """

    _instance: ClassVar[Optional["InferencePipeline"]] = None

    def __init__(self):
        logger.info("Loading ML models...")

        self.feature_extractor = FeatureExtractor()
        self.detector = DeepfakeDetector()
        self.verifier = SpeakerVerifier()
        self.prosody = ProsodyAnalyzer()

        logger.info("Model loading complete.")

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------

    @classmethod
    def get_instance(cls) -> "InferencePipeline":
        """Return the shared pipeline instance (lazy-loaded)."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Warmup
    # ------------------------------------------------------------------

    def warmup(self):
        """Run dummy inference to warm up ONNX sessions.

        ONNX Runtime JIT-compiles kernels on first run, so the very
        first real request would be slow without warmup.
        """
        logger.info("Warming up inference pipeline...")
        dummy = np.zeros(32000, dtype=np.float32)  # 2 s of silence

        t0 = time.perf_counter()
        self.detector.predict(dummy)
        self.verifier.extract_embedding(dummy)
        self.prosody.analyze(dummy)
        elapsed = (time.perf_counter() - t0) * 1000

        logger.info("Warmup complete in %.0f ms", elapsed)

    # ------------------------------------------------------------------
    # Main inference
    # ------------------------------------------------------------------

    async def process_chunk(
        self,
        audio: np.ndarray,
        enrollment_embedding: np.ndarray | None = None,
        session_embeddings: list[np.ndarray] | None = None,
        skip_speaker: bool = False,
    ) -> dict:
        """Run the full ML pipeline on one audio window.

        All three model branches (deepfake, speaker, prosody) run
        **concurrently** via ``asyncio.gather``.

        Parameters
        ----------
        audio : np.ndarray
            2-second audio window (32 000 samples at 16 kHz), float32.
        enrollment_embedding : np.ndarray | None
            192-dim enrolled speaker embedding for verification.
            If ``None``, speaker verification is skipped.
        session_embeddings : list[np.ndarray] | None
            Prior embeddings from this session for drift detection.

        Returns
        -------
        dict
            Combined results from all models:
            ``deepfake``, ``speaker``, ``prosody``, ``latency_ms``.
        """
        t0 = time.perf_counter()

        # ── Concurrent inference ──────────────────────────────────────
        prosody_task = asyncio.to_thread(self.prosody.analyze, audio)

        if skip_speaker:
            async def mock_speaker_task():
                return {
                    "similarity": 0.0, "is_verified": False,
                    "threshold": 0.72, "margin": -0.72,
                    "embedding": None,
                }
            speaker_task = asyncio.create_task(mock_speaker_task())
        elif enrollment_embedding is not None:
            speaker_task = asyncio.to_thread(
                self.verifier.verify_against_profile, audio, enrollment_embedding
            )
        else:
            # Just extract an embedding for drift tracking
            speaker_task = asyncio.to_thread(
                self._extract_speaker_only, audio
            )

        prosody_result = await prosody_task
        if isinstance(prosody_result, Exception):
            logger.debug("Prosody inference error: %s", prosody_result)
            prosody_result = {
                "f0_mean": 0.0, "f0_std": 0.0, "jitter": 0.0,
                "shimmer": 0.0, "hnr": 0.0, "spectral_flatness": 0.0,
                "prosody_anomaly_score": 0.2,
            }

        prosody_anomaly = float(prosody_result.get("prosody_anomaly_score", 0.2))
        deepfake_task = asyncio.to_thread(self.detector.predict, audio, prosody_anomaly)

        deepfake_result, speaker_result = await asyncio.gather(
            deepfake_task, speaker_task, return_exceptions=True
        )

        # ── Handle exceptions gracefully ──────────────────────────────
        if isinstance(deepfake_result, Exception):
            logger.debug("Deepfake inference error: %s", deepfake_result)
            deepfake_result = {
                "spoof_probability": 0.2, "aasist_score": None,
                "xlsr_score": None, "confidence": 0.0,
                "is_synthetic": False,
            }
        if isinstance(speaker_result, Exception):
            logger.debug("Speaker inference error: %s", speaker_result)
            speaker_result = {
                "similarity": 0.0, "is_verified": False,
                "threshold": 0.72, "margin": -0.72,
                "embedding": np.zeros(192, dtype=np.float32),
            }

        # ── Speaker drift detection ───────────────────────────────────
        drift_score = 0.0
        current_emb = speaker_result.get("embedding")
        if current_emb is not None and session_embeddings and len(session_embeddings) >= 2:
            try:
                drift_score = self.verifier.detect_drift(
                    current_emb, session_embeddings
                )
            except Exception as e:
                logger.debug("Drift detection error: %s", e)

        elapsed_ms = (time.perf_counter() - t0) * 1000

        return {
            "deepfake": deepfake_result,
            "speaker": speaker_result,
            "prosody": prosody_result,
            "speaker_drift": drift_score,
            "latency_ms": round(elapsed_ms, 1),
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _extract_speaker_only(self, audio: np.ndarray) -> dict:
        """Extract embedding without verification when no enrolment exists."""
        emb = self.verifier.extract_embedding(audio)
        return {
            "similarity": 0.0,
            "is_verified": False,
            "embedding": emb,
        }
