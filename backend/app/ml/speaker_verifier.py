"""
Speaker verification module using ECAPA-TDNN embeddings.

Provides:
- 192-dimensional speaker embedding extraction via ONNX Runtime
- Cosine-similarity-based speaker verification against enrolled profiles
- Mid-call speaker drift detection (detects voice identity changes)

All embeddings are L2-normalised before comparison — this is critical
for cosine similarity accuracy with ECAPA-TDNN.
"""

from __future__ import annotations

import numpy as np
import onnxruntime as ort
from numpy.linalg import norm

from app.config import settings


class SpeakerVerifier:
    """ECAPA-TDNN speaker verification engine.

    Loads an ONNX-exported ECAPA-TDNN model and provides methods for
    embedding extraction, verification, and within-session drift
    detection.
    """

    EMBEDDING_DIM = 192

    def __init__(self):
        self._session: ort.InferenceSession | None = None
        try:
            self._session = ort.InferenceSession(
                settings.ecapa_onnx_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            print("  [OK] ECAPA-TDNN ONNX model loaded")
        except Exception as e:
            print(f"  [ERROR] Failed to load ECAPA-TDNN ONNX: {e}. Running in mock mode.")

        self._models_loaded = self._session is not None

        # Deterministic RNG for mock mode
        self._mock_rng = np.random.RandomState(123)

    # ------------------------------------------------------------------
    #  Embedding extraction
    # ------------------------------------------------------------------

    def extract_embedding(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Extract an L2-normalised 192-dim speaker embedding.

        Parameters
        ----------
        audio_chunk : np.ndarray
            1-D or 2-D float32 waveform (e.g. 2 s at 16 kHz).

        Returns
        -------
        np.ndarray
            192-dimensional unit-length embedding vector.
        """
        if not self._models_loaded:
            # Deterministic mock embedding
            emb = self._mock_rng.randn(self.EMBEDDING_DIM).astype(np.float32)
            return self._l2_normalize(emb)

        audio = self._prepare(audio_chunk)
        input_name = self._session.get_inputs()[0].name
        raw_emb = self._session.run(None, {input_name: audio})[0]

        emb = raw_emb.flatten().astype(np.float32)
        return self._l2_normalize(emb)

    # ------------------------------------------------------------------
    #  Verification
    # ------------------------------------------------------------------

    def verify_against_profile(
        self,
        audio_chunk: np.ndarray,
        enrolled_embedding: np.ndarray,
    ) -> dict:
        """Verify that audio matches an enrolled speaker.

        Parameters
        ----------
        audio_chunk : np.ndarray
            Live audio to verify.
        enrolled_embedding : np.ndarray
            The reference 192-dim embedding from enrolment.

        Returns
        -------
        dict
            ``similarity``    — cosine similarity [-1, 1].
            ``is_verified``   — True when similarity ≥ threshold.
            ``embedding``     — extracted embedding for downstream use.
        """
        emb = self.extract_embedding(audio_chunk)
        enrolled = self._l2_normalize(enrolled_embedding)
        sim = self.compute_similarity(emb, enrolled)

        return {
            "similarity": round(float(sim), 4),
            "is_verified": sim >= settings.speaker_verification_threshold,
            "embedding": emb,
        }

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two (ideally L2-normalised) embeddings."""
        return float(np.dot(emb1, emb2) / (norm(emb1) * norm(emb2) + 1e-8))

    # ------------------------------------------------------------------
    #  Drift detection
    # ------------------------------------------------------------------

    def detect_drift(
        self,
        current_emb: np.ndarray,
        session_embeddings: list[np.ndarray],
        *,
        window: int = 5,
    ) -> float:
        """Detect mid-call speaker identity changes.

        Compares the current embedding against the rolling mean of the
        last *window* embeddings from this session.  A high drift score
        (close to 1) suggests the speaker has changed.

        Parameters
        ----------
        current_emb : np.ndarray
            The latest 192-dim embedding.
        session_embeddings : list[np.ndarray]
            All prior embeddings collected in this session.
        window : int
            Number of recent embeddings to average for comparison.

        Returns
        -------
        float
            Drift score in [0, 1].  0 = perfectly consistent,
            1 = completely different speaker.
        """
        if len(session_embeddings) < 2:
            return 0.0

        # Take the last `window` embeddings and compute their centroid
        recent = session_embeddings[-window:]
        centroid = np.mean(recent, axis=0).astype(np.float32)
        centroid = self._l2_normalize(centroid)

        sim = self.compute_similarity(
            self._l2_normalize(current_emb), centroid
        )

        # Convert similarity → drift score (0 = same speaker, 1 = different)
        drift = max(0.0, 1.0 - sim)
        return round(float(drift), 4)

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare(audio: np.ndarray) -> np.ndarray:
        """Ensure ``[1, N]`` float32 shape."""
        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=0)
        return audio.astype(np.float32)

    @staticmethod
    def _l2_normalize(v: np.ndarray) -> np.ndarray:
        """L2-normalise a vector to unit length."""
        n = norm(v)
        if n > 0:
            return v / n
        return v
