"""
Deepfake / synthetic-speech detector — dual-branch ensemble.

Branch 1 — **AASIST**  (primary):
    Graph-attention network operating directly on raw waveforms.
    Captures spectro-temporal synthesis artifacts simultaneously.
    Input : [batch, 32000]  (2 s @ 16 kHz)
    Output: logits [batch, 2]  ([bonafide, spoof])

Branch 2 — **XLS-R + linear head** (secondary, optional):
    Multilingual self-supervised backbone with a linear binary classifier.
    Better generalisation to unseen vocoders and Indian languages.
    Input : [batch, 32000]
    Output: logits [batch, 2]

If only one branch is available the detector falls back to single-model
mode.  If neither model is loaded it runs in **mock mode** with
deterministic seeded output for development.
"""

from __future__ import annotations

import numpy as np
import onnxruntime as ort

from app.config import settings


def _softmax(logits: np.ndarray) -> np.ndarray:
    """Row-wise softmax for 2-D logits."""
    e = np.exp(logits - np.max(logits, axis=-1, keepdims=True))
    return e / e.sum(axis=-1, keepdims=True)


class DeepfakeDetector:
    """Dual-branch deepfake detector with weighted ensemble fusion.

    Parameters
    ----------
    aasist_weight : float
        Ensemble weight for AASIST score (default 0.6).
    xlsr_weight : float
        Ensemble weight for XLS-R score (default 0.4).
        Ignored when XLS-R is unavailable — AASIST runs solo.
    """

    def __init__(
        self,
        aasist_weight: float = 0.6,
        xlsr_weight: float = 0.4,
    ):
        self.threshold = settings.deepfake_threshold
        self.aasist_weight = aasist_weight
        self.xlsr_weight = xlsr_weight

        # ── Load AASIST ONNX ──────────────────────────────────────────
        self._aasist_session: ort.InferenceSession | None = None
        try:
            self._aasist_session = ort.InferenceSession(
                settings.aasist_onnx_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            print("  [OK] AASIST ONNX model loaded")
        except Exception as e:
            print(f"  [ERROR] Failed to load AASIST ONNX: {e}")

        # ── Load XLS-R ONNX (optional) ────────────────────────────────
        self._xlsr_session: ort.InferenceSession | None = None
        try:
            self._xlsr_session = ort.InferenceSession(
                settings.xlsr_onnx_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            print("  [OK] XLS-R ONNX model loaded")
        except Exception as e:
            print(f"  [ERROR] Failed to load XLS-R ONNX: {e}  (optional — continuing)")

        self._models_loaded = (
            self._aasist_session is not None or self._xlsr_session is not None
        )

        # Deterministic RNG for mock mode (reproducible dev/test results)
        self._mock_rng = np.random.RandomState(42)

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def predict(self, audio_chunk: np.ndarray) -> dict:
        """Run deepfake detection on a 2-second audio chunk.

        Parameters
        ----------
        audio_chunk : np.ndarray
            1-D or 2-D float32 array.  If 1-D it is expanded to
            ``[1, N]``.

        Returns
        -------
        dict
            ``spoof_probability`` — ensemble probability that the audio
            is synthetic / spoofed (0 = definitely real, 1 = definitely
            fake).
            ``aasist_score`` — raw AASIST spoof probability.
            ``xlsr_score``  — raw XLS-R spoof probability (``None`` if
            model unavailable).
            ``confidence``  — inter-model agreement metric [0, 1].
        """
        if not self._models_loaded:
            return self._mock_predict()

        audio_chunk = self._prepare(audio_chunk)

        aasist_score = self._run_aasist(audio_chunk)
        xlsr_score = self._run_xlsr(audio_chunk)

        # ── Ensemble fusion ───────────────────────────────────────────
        if aasist_score is not None and xlsr_score is not None:
            spoof_prob = (
                self.aasist_weight * aasist_score
                + self.xlsr_weight * xlsr_score
            )
            # Confidence = 1 − |score_diff|  (agreement metric)
            confidence = 1.0 - abs(aasist_score - xlsr_score)
        elif aasist_score is not None:
            spoof_prob = aasist_score
            confidence = 0.7  # single model → lower confidence
        elif xlsr_score is not None:
            spoof_prob = xlsr_score
            confidence = 0.7
        else:
            return self._mock_predict()

        return {
            "spoof_probability": round(float(spoof_prob), 4),
            "aasist_score": round(float(aasist_score), 4) if aasist_score is not None else None,
            "xlsr_score": round(float(xlsr_score), 4) if xlsr_score is not None else None,
            "confidence": round(float(confidence), 4),
        }

    # ------------------------------------------------------------------
    #  Internal — model inference
    # ------------------------------------------------------------------

    def _run_aasist(self, audio: np.ndarray) -> float | None:
        """Run AASIST ONNX session.  Returns spoof probability or None."""
        if self._aasist_session is None:
            return None
        try:
            input_name = self._aasist_session.get_inputs()[0].name
            logits = self._aasist_session.run(None, {input_name: audio})[0]
            # logits shape: [batch, 2]  →  [bonafide, spoof]
            probs = _softmax(logits)[0]
            return float(probs[1])  # index 1 = spoof
        except Exception as e:
            print(f"  AASIST inference error: {e}")
            return None

    def _run_xlsr(self, audio: np.ndarray) -> float | None:
        """Run XLS-R ONNX session.  Returns spoof probability or None."""
        if self._xlsr_session is None:
            return None
        try:
            input_name = self._xlsr_session.get_inputs()[0].name
            logits = self._xlsr_session.run(None, {input_name: audio})[0]
            probs = _softmax(logits)[0]
            return float(probs[1])
        except Exception as e:
            print(f"  XLS-R inference error: {e}")
            return None

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare(audio: np.ndarray) -> np.ndarray:
        """Ensure ``[1, N]`` float32 shape."""
        if audio.ndim == 1:
            audio = np.expand_dims(audio, axis=0)
        return audio.astype(np.float32)

    def _mock_predict(self) -> dict:
        """Deterministic mock output for development without models."""
        score = float(self._mock_rng.beta(2, 5))  # skewed toward low risk
        return {
            "spoof_probability": round(score, 4),
            "aasist_score": round(score, 4),
            "xlsr_score": None,
            "confidence": 0.5,
        }
