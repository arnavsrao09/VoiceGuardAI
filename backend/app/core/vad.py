"""
Voice Activity Detection wrapper using Silero VAD.

Uses the modern `silero-vad` pip package (v5+) which provides a simpler API
than the old torch.hub approach.  Falls back gracefully if the model cannot
be loaded (e.g. first run without internet).
"""

import numpy as np
import torch
from app.config import settings


class SileroVADWrapper:
    """Streaming-friendly VAD built on Silero VAD.

    Parameters
    ----------
    sample_rate : int
        Audio sample rate. Silero VAD supports 8000 and 16000.
    min_speech_duration_ms : int
        Minimum contiguous speech duration (ms) before we consider the
        segment "active".  Helps ignore transient pops / clicks.
    min_silence_duration_ms : int
        Minimum silence duration (ms) before we consider speech ended.
    """

    # Silero VAD at 16 kHz accepts chunks of exactly 512 samples (32 ms)
    CHUNK_SAMPLES_16K = 512

    def __init__(
        self,
        sample_rate: int = 16000,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 300,
    ):
        self.sample_rate = sample_rate
        self.threshold = settings.vad_threshold

        # Onset / offset tracking state
        self.min_speech_samples = int(min_speech_duration_ms * sample_rate / 1000)
        self.min_silence_samples = int(min_silence_duration_ms * sample_rate / 1000)
        self._speech_samples = 0
        self._silence_samples = 0
        self._is_speech_active = False

        # Load Silero VAD model via the pip package API
        try:
            model, utils = torch.hub.load(
                repo_or_dir="snakers4/silero-vad",
                model="silero_vad",
                force_reload=False,
                trust_repo=True,
            )
            self.model = model
            self._model_loaded = True
        except Exception as e:
            print(f"Warning: Failed to load Silero VAD: {e}. Using energy-based fallback.")
            self.model = None
            self._model_loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def is_speech(self, audio_chunk: np.ndarray) -> float:
        """Return speech probability for *audio_chunk*.

        Parameters
        ----------
        audio_chunk : np.ndarray
            1-D float32 array in [-1, 1].  Any length is accepted; the
            method internally re-chunks to 512-sample frames and returns
            the **maximum** speech probability across sub-frames.
        """
        if not self._model_loaded:
            return self._energy_fallback(audio_chunk)

        audio_chunk = audio_chunk.astype(np.float32)

        # Split into 512-sample sub-chunks (Silero requirement at 16 kHz)
        chunk_size = self.CHUNK_SAMPLES_16K
        n_full = len(audio_chunk) // chunk_size
        if n_full == 0:
            # Pad short chunks to the required size
            padded = np.zeros(chunk_size, dtype=np.float32)
            padded[: len(audio_chunk)] = audio_chunk
            return self._infer_single(padded)

        max_prob = 0.0
        for i in range(n_full):
            sub = audio_chunk[i * chunk_size : (i + 1) * chunk_size]
            prob = self._infer_single(sub)
            max_prob = max(max_prob, prob)

        return max_prob

    def update_state(self, speech_prob: float, n_samples: int) -> bool:
        """Update onset/offset state and return whether speech is active.

        Call this **after** ``is_speech`` to apply hysteresis so that
        transient blips don't toggle the flag.
        """
        if speech_prob >= self.threshold:
            self._speech_samples += n_samples
            self._silence_samples = 0
            if self._speech_samples >= self.min_speech_samples:
                self._is_speech_active = True
        else:
            self._silence_samples += n_samples
            self._speech_samples = 0
            if self._silence_samples >= self.min_silence_samples:
                self._is_speech_active = False

        return self._is_speech_active

    @property
    def is_active(self) -> bool:
        """Whether the VAD currently considers the stream as speech."""
        return self._is_speech_active

    def reset(self):
        """Reset internal state (call when a new session starts)."""
        self._speech_samples = 0
        self._silence_samples = 0
        self._is_speech_active = False
        if self._model_loaded:
            self.model.reset_states()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _infer_single(self, chunk_512: np.ndarray) -> float:
        """Run Silero VAD on a single 512-sample chunk."""
        tensor = torch.from_numpy(chunk_512)
        with torch.no_grad():
            prob = self.model(tensor, self.sample_rate).item()
        return float(prob)

    @staticmethod
    def _energy_fallback(audio_chunk: np.ndarray) -> float:
        """Simple RMS energy-based speech detector used when the model
        is unavailable."""
        rms = float(np.sqrt(np.mean(audio_chunk ** 2)))
        # Map RMS energy to a pseudo-probability.  Typical speech RMS
        # on normalised [-1,1] audio is 0.02 – 0.15.
        if rms < 0.005:
            return 0.0
        if rms > 0.08:
            return 1.0
        return min(1.0, rms / 0.08)
