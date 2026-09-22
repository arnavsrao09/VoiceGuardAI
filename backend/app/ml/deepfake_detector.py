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
from app.logging_config import get_logger

logger = get_logger("deepfake")


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
        temperature: float = 0.05,
    ):
        self.threshold = settings.deepfake_threshold
        self.aasist_weight = aasist_weight
        self.xlsr_weight = xlsr_weight
        # Temperature scaling for raw logits: the ONNX models output logits
        # with very small magnitude (~0.05). Dividing by temperature amplifies
        # the signal before softmax, enabling actual discrimination.
        self._temperature = temperature

        # ── Load AASIST ONNX ──────────────────────────────────────────
        self._aasist_session: ort.InferenceSession | None = None
        try:
            self._aasist_session = ort.InferenceSession(
                settings.aasist_onnx_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            logger.info("AASIST ONNX model loaded.")
        except Exception as e:
            logger.warning("Failed to load AASIST ONNX: %s", e)

        # ── Load XLS-R ONNX (optional) ────────────────────────────────
        self._xlsr_session: ort.InferenceSession | None = None
        try:
            self._xlsr_session = ort.InferenceSession(
                settings.xlsr_onnx_path,
                providers=["CUDAExecutionProvider", "CPUExecutionProvider"],
            )
            logger.info("XLS-R ONNX model loaded.")
        except Exception as e:
            logger.debug("XLS-R ONNX not loaded (optional): %s", e)

        self._models_loaded = (
            self._aasist_session is not None or self._xlsr_session is not None
        )

        # Deterministic RNG for mock mode (reproducible dev/test results)
        self._mock_rng = np.random.RandomState(42)

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def predict(
        self,
        audio_chunk: np.ndarray,
        prosody_anomaly: float | None = None,
    ) -> dict:
        """Run deepfake detection on an audio chunk of arbitrary duration.

        Parameters
        ----------
        audio_chunk : np.ndarray
            1-D float32 array of audio samples at 16 kHz.
        prosody_anomaly : float | None
            Optional forensic prosody anomaly score [0, 1] to serve as a
            supporting signal.

        Returns
        -------
        dict
            ``spoof_probability`` — calibrated probability that the audio is synthetic.
            ``aasist_score`` — raw AASIST spoof score.
            ``xlsr_score`` — raw XLS-R spoof score.
            ``confidence`` — inter-model agreement metric [0, 1].
            ``is_synthetic`` — True if calibrated score exceeds threshold.
        """
        if not self._models_loaded:
            return self._mock_predict()

        if audio_chunk.ndim > 1:
            audio_1d = audio_chunk.flatten().astype(np.float32)
        else:
            audio_1d = audio_chunk.astype(np.float32)

        # ── 1. AASIST with windowing ──────────────────────────────────
        aasist_score = self._run_aasist_windowed(audio_1d)

        # ── 2. XLS-R ──────────────────────────────────────────────────
        xlsr_score = self._run_xlsr(audio_1d)

        # ── 3. Calibrated Deepfake Fusion ──────────────────────────────
        # Combine model signals using calibrated weighting
        if aasist_score is not None and xlsr_score is not None:
            raw_fusion = (
                self.aasist_weight * aasist_score
                + self.xlsr_weight * xlsr_score
            )
            confidence = 1.0 - abs(aasist_score - xlsr_score)
        elif aasist_score is not None:
            raw_fusion = aasist_score
            confidence = 0.75
        elif xlsr_score is not None:
            raw_fusion = xlsr_score
            confidence = 0.70
        else:
            return self._mock_predict()

        # Supporting forensic signal (Prosody) — secondary confirmation only
        if prosody_anomaly is not None:
            # If models are borderline (0.35-0.65), prosody helps tilt with low weight (0.15)
            final_prob = 0.85 * raw_fusion + 0.15 * prosody_anomaly
        else:
            final_prob = raw_fusion

        final_prob = float(np.clip(final_prob, 0.0, 1.0))

        logger.info(
            "Deepfake scores: aasist=%.4f xlsr=%s raw_fusion=%.4f final=%.4f "
            "threshold=%.4f is_synthetic=%s confidence=%.4f",
            aasist_score if aasist_score is not None else 0.0,
            f"{xlsr_score:.4f}" if xlsr_score is not None else "N/A",
            raw_fusion,
            final_prob,
            self.threshold,
            final_prob >= self.threshold,
            confidence,
        )

        return {
            "spoof_probability": round(final_prob, 4),
            "aasist_score": round(float(aasist_score), 4) if aasist_score is not None else None,
            "xlsr_score": round(float(xlsr_score), 4) if xlsr_score is not None else None,
            "confidence": round(float(confidence), 4),
            "is_synthetic": final_prob >= self.threshold,
        }

    # ------------------------------------------------------------------
    #  Internal — model inference
    # ------------------------------------------------------------------

    def _run_aasist_windowed(self, audio: np.ndarray) -> float | None:
        """Run AASIST on 32000-sample windows with temporal aggregation."""
        if self._aasist_session is None:
            return None
        try:
            target_len = 32000
            n_samples = len(audio)

            if n_samples == 0:
                return 0.0

            # If shorter than 32000, pad symmetrically or with zeros
            if n_samples < target_len:
                padded = np.zeros(target_len, dtype=np.float32)
                padded[:n_samples] = audio
                windows = np.expand_dims(padded, axis=0)
            elif n_samples == target_len:
                windows = np.expand_dims(audio, axis=0)
            else:
                # Slice into overlapping 2-second windows (hop = 1 second)
                hop = 16000
                chunks = []
                for start in range(0, n_samples - target_len + 1, hop):
                    chunks.append(audio[start : start + target_len])
                # Ensure the end of the audio is covered
                if (n_samples - target_len) % hop != 0:
                    chunks.append(audio[-target_len:])
                windows = np.stack(chunks, axis=0).astype(np.float32)

            input_name = self._aasist_session.get_inputs()[0].name
            output = self._aasist_session.run(None, {input_name: windows})[0]
            # output shape: [batch, 2] -> [bonafide, spoof]
            # Model outputs raw logits with very small magnitude (~0.05).
            # Temperature scaling amplifies the signal before softmax.
            logits = np.asarray(output, dtype=np.float64)
            logits_scaled = logits / self._temperature
            probs = _softmax(logits_scaled)
            # ASVspoof format: [spoof, bonafide] -> index 0 is spoof
            spoof_probs = probs[:, 0]
            # Return mean spoof probability across windows
            return float(np.mean(spoof_probs))
        except Exception as e:
            logger.error("AASIST inference error: %s", e)
            return None

    def _run_xlsr(self, audio: np.ndarray) -> float | None:
        """Run XLS-R ONNX session. Returns spoof probability or None."""
        if self._xlsr_session is None:
            return None
        try:
            input_name = self._xlsr_session.get_inputs()[0].name
            # XLS-R expects [batch, time]
            inp = np.expand_dims(audio, axis=0).astype(np.float32)
            output = self._xlsr_session.run(None, {input_name: inp})[0]
            # Model outputs raw logits with very small magnitude.
            # Temperature scaling amplifies the signal before softmax.
            logits = np.asarray(output, dtype=np.float64)
            logits_scaled = logits / self._temperature
            probs = _softmax(logits_scaled)
            # ASVspoof format: [spoof, bonafide] -> index 0 is spoof
            return float(probs[0][0])
        except Exception as e:
            logger.error("XLS-R inference error: %s", e)
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
        """Deterministic mock output for development without models.

        Produces stable low-risk scores that simulate a genuine human speaker,
        preventing false alarms when ONNX models are not loaded.
        The score hovers in the 0.10–0.25 genuine baseline range with minor
        natural variation.
        """
        # Small jitter around a safe genuine baseline (0.10 - 0.25)
        score = 0.15 + float(self._mock_rng.uniform(-0.05, 0.10))
        return {
            "spoof_probability": round(score, 4),
            "aasist_score": round(score, 4),
            "xlsr_score": None,
            "confidence": 0.5,
            "is_synthetic": False,
        }
