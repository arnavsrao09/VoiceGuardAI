"""
Speaker verification module using ECAPA-TDNN embeddings.

Provides:
- 192-dimensional speaker embedding extraction via SpeechBrain EncoderClassifier
- Cosine-similarity-based speaker verification against enrolled profiles
- Mid-call speaker drift detection (detects voice identity changes)

All embeddings are L2-normalised before comparison — this is critical
for cosine similarity accuracy with ECAPA-TDNN.
"""

from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import torch
from numpy.linalg import norm

from app.config import settings

_ECAPA_SOURCE = "speechbrain/spkrec-ecapa-voxceleb"
_ECAPA_SAVEDIR = Path(__file__).resolve().parent / "models" / "spkrec-ecapa-voxceleb"
_TARGET_SR = 16000
_MIN_SAMPLES = 1600  # 0.1 s at 16 kHz
_ZERO_NORM = 1e-8


class SpeakerVerifier:
    """ECAPA-TDNN speaker verification engine.

    Loads SpeechBrain ``spkrec-ecapa-voxceleb`` and provides methods for
    embedding extraction, verification, and within-session drift
    detection.
    """

    EMBEDDING_DIM = 192

    def __init__(self):
        self._classifier = None
        self._device = "cuda" if torch.cuda.is_available() else "cpu"
        self._infer_lock = threading.Lock()
        try:
            from speechbrain.inference.speaker import EncoderClassifier
            from speechbrain.utils.fetching import LocalStrategy

            _ECAPA_SAVEDIR.mkdir(parents=True, exist_ok=True)
            self._classifier = EncoderClassifier.from_hparams(
                source=_ECAPA_SOURCE,
                savedir=str(_ECAPA_SAVEDIR),
                run_opts={"device": self._device},
                local_strategy=LocalStrategy.COPY,
            )
            self._classifier.eval()
            print(f"  [OK] ECAPA-TDNN SpeechBrain model loaded ({_ECAPA_SOURCE} on {self._device})")
        except Exception as e:
            print(f"  [ERROR] Failed to load SpeechBrain ECAPA: {e}. Running in mock mode.")
            self._classifier = None

        self._models_loaded = self._classifier is not None

        # Deterministic RNG for mock mode
        self._mock_rng = np.random.RandomState(123)

    # ------------------------------------------------------------------
    #  Embedding extraction
    # ------------------------------------------------------------------

    def extract_embedding(self, audio_chunk: np.ndarray) -> np.ndarray:
        """Extract an L2-normalised 192-dim speaker embedding with NaN immunity.

        Parameters
        ----------
        audio_chunk : np.ndarray
            1-D or 2-D waveform. Treated as 16 kHz mono float32 in [-1, 1].

        Returns
        -------
        np.ndarray
            192-dimensional unit-length embedding vector. Invalid
            (NaN/Inf/zero-norm) embeddings are rejected as an all-zero vector.
        """
        if not self._models_loaded:
            emb = self._mock_rng.randn(self.EMBEDDING_DIM).astype(np.float32)
            return self._l2_normalize(emb)

        audio_clean = self._preprocess_16k_mono(audio_chunk)
        if audio_clean is None:
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        try:
            wavs = torch.from_numpy(audio_clean).unsqueeze(0).to(self._device)
            wav_lens = torch.ones(1, device=self._device)
            with self._infer_lock:
                with torch.inference_mode():
                    raw = self._classifier.encode_batch(wavs, wav_lens)
            emb = raw.detach().float().cpu().numpy().reshape(-1).astype(np.float32)
            return self._finalize_embedding(emb)
        except Exception as e:
            print(f"  [WARN] ECAPA extraction error: {e}. Using zero embedding fallback.")
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

    # ------------------------------------------------------------------
    #  Verification
    # ------------------------------------------------------------------

    def verify_against_profile(
        self,
        audio_chunk: np.ndarray,
        enrolled_embedding: np.ndarray,
        threshold: float | None = None,
    ) -> dict:
        """Verify that audio matches an enrolled speaker. Guaranteed no NaNs.

        Parameters
        ----------
        audio_chunk : np.ndarray
            Live audio to verify.
        enrolled_embedding : np.ndarray
            The reference 192-dim embedding from enrolment.
        threshold : float | None
            Verification threshold override. If None, uses settings value.

        Returns
        -------
        dict
            ``similarity``    — cosine similarity [-1, 1].
            ``is_verified``   — True when similarity ≥ threshold.
            ``threshold``     — threshold used for verification.
            ``margin``        — difference between similarity and threshold.
            ``embedding``     — extracted embedding for downstream use.
        """
        th = threshold if threshold is not None else settings.speaker_verification_threshold
        emb = self.extract_embedding(audio_chunk)
        enrolled = self._l2_normalize(enrolled_embedding)
        sim = self.compute_similarity(emb, enrolled)

        if np.isnan(sim) or np.isinf(sim):
            sim = 0.0

        is_verified = bool(sim >= th)
        margin = float(sim - th)
        if np.isnan(margin) or np.isinf(margin):
            margin = float(-th)

        return {
            "similarity": round(float(sim), 4),
            "is_verified": is_verified,
            "threshold": round(float(th), 4),
            "margin": round(float(margin), 4),
            "embedding": emb,
        }

    def compute_similarity(self, emb1: np.ndarray, emb2: np.ndarray) -> float:
        """Cosine similarity between two embeddings with full NaN immunity."""
        if emb1 is None or emb2 is None:
            return 0.0

        e1 = self._l2_normalize(emb1)
        e2 = self._l2_normalize(emb2)

        norm1 = norm(e1)
        norm2 = norm(e2)

        if norm1 < _ZERO_NORM or norm2 < _ZERO_NORM or np.isnan(norm1) or np.isnan(norm2):
            return 0.0

        sim = float(np.dot(e1, e2) / (norm1 * norm2))
        if np.isnan(sim) or np.isinf(sim):
            return 0.0

        return float(np.clip(sim, -1.0, 1.0))

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
        """Detect mid-call speaker identity changes. Guaranteed no NaNs."""
        if not session_embeddings or len(session_embeddings) < 2:
            return 0.0

        # Filter out any zero or NaN vectors from session history
        valid_embeddings = [
            np.nan_to_num(e, nan=0.0, posinf=0.0, neginf=0.0)
            for e in session_embeddings[-window:]
            if norm(np.nan_to_num(e)) > _ZERO_NORM
        ]

        if not valid_embeddings:
            return 0.0

        centroid = np.mean(valid_embeddings, axis=0).astype(np.float32)
        centroid = self._l2_normalize(centroid)

        sim = self.compute_similarity(self._l2_normalize(current_emb), centroid)
        if np.isnan(sim) or np.isinf(sim):
            sim = 1.0

        # Convert similarity -> drift score (0 = same speaker, 1 = different)
        drift = max(0.0, min(1.0, 1.0 - sim))
        return round(float(drift), 4)

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _preprocess_16k_mono(audio: np.ndarray) -> np.ndarray | None:
        """Convert input to 16 kHz-assumed mono float32 in [-1, 1]."""
        if audio is None or len(audio) == 0:
            return None

        wav = np.asarray(audio, dtype=np.float32)
        wav = np.nan_to_num(wav, nan=0.0, posinf=0.0, neginf=0.0)

        if wav.ndim > 1:
            # [channels, time] if few rows, otherwise [time, channels]
            if wav.shape[0] <= 8 and wav.shape[0] < wav.shape[-1]:
                wav = np.mean(wav, axis=0)
            else:
                wav = np.mean(wav, axis=-1)
        wav = np.reshape(wav, -1).astype(np.float32, copy=False)

        peak = float(np.max(np.abs(wav))) if wav.size else 0.0
        if peak > 1.0:
            wav = wav / peak

        if len(wav) < _MIN_SAMPLES:
            padded = np.zeros(_MIN_SAMPLES, dtype=np.float32)
            padded[: len(wav)] = wav
            wav = padded

        return wav

    def _finalize_embedding(self, emb: np.ndarray) -> np.ndarray:
        """Keep the 192-d speaker vector; reject NaN/Inf/zero-norm; L2-normalise."""
        if emb is None:
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        vec = np.asarray(emb, dtype=np.float32).reshape(-1)
        if vec.size != self.EMBEDDING_DIM:
            print(f"  [WARN] Unexpected ECAPA embedding size {vec.size}; rejecting.")
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        if not np.isfinite(vec).all():
            print("  [WARN] ECAPA embedding contains NaN/Inf; rejecting.")
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        n = float(norm(vec))
        if n < _ZERO_NORM or np.isnan(n) or np.isinf(n):
            print("  [WARN] ECAPA embedding has zero/invalid norm; rejecting.")
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        return (vec / n).astype(np.float32)

    def extract_enrollment_embedding(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        window_sec: float = 2.0,
        hop_sec: float = 0.5,
        min_rms: float = 0.01,
    ) -> np.ndarray:
        """Average L2-normalised 2 s embeddings so enrollment matches live windows."""
        if audio is None or len(audio) == 0:
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        audio_clean = self._preprocess_16k_mono(audio)
        if audio_clean is None:
            return np.zeros(self.EMBEDDING_DIM, dtype=np.float32)

        window = int(window_sec * sample_rate)
        hop = int(hop_sec * sample_rate)
        if len(audio_clean) < window:
            return self.extract_embedding(audio_clean)

        embs: list[np.ndarray] = []
        for start in range(0, len(audio_clean) - window + 1, hop):
            chunk = audio_clean[start : start + window]
            rms = float(np.sqrt(np.mean(chunk ** 2)))
            if rms < min_rms:
                continue
            cand = self.extract_embedding(chunk)
            if float(norm(cand)) > _ZERO_NORM:
                embs.append(cand)

        if not embs:
            return self.extract_embedding(audio_clean)

        mean_emb = np.mean(np.stack(embs, axis=0), axis=0).astype(np.float32)
        return self._l2_normalize(mean_emb)

    @staticmethod
    def _l2_normalize(v: np.ndarray | list | str | None) -> np.ndarray:
        """L2-normalise a vector to unit length with full NaN & string parsing safety."""
        if v is None:
            return np.zeros(SpeakerVerifier.EMBEDDING_DIM, dtype=np.float32)

        if isinstance(v, str):
            import json
            try:
                v = json.loads(v)
            except Exception:
                try:
                    # Strip brackets if string like "[0.1, 0.2, ...]"
                    clean_str = v.strip().strip("[]").strip("()")
                    v = [float(x) for x in clean_str.split(",") if x.strip()]
                except Exception:
                    print("  [WARN] Failed to parse string embedding.")
                    return np.zeros(SpeakerVerifier.EMBEDDING_DIM, dtype=np.float32)

        arr = np.asarray(v, dtype=np.float32).reshape(-1)
        arr = np.nan_to_num(arr, nan=0.0, posinf=0.0, neginf=0.0)

        if arr.size != SpeakerVerifier.EMBEDDING_DIM:
            print(f"  [WARN] Invalid embedding size {arr.size} (expected {SpeakerVerifier.EMBEDDING_DIM}); rejecting.")
            return np.zeros(SpeakerVerifier.EMBEDDING_DIM, dtype=np.float32)

        if not np.isfinite(arr).all():
            return np.zeros(SpeakerVerifier.EMBEDDING_DIM, dtype=np.float32)

        n = float(norm(arr))
        if n > _ZERO_NORM and not np.isnan(n) and not np.isinf(n):
            return (arr / n).astype(np.float32)

        return np.zeros(SpeakerVerifier.EMBEDDING_DIM, dtype=np.float32)
