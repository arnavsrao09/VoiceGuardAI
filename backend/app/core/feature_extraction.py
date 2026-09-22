"""
Audio feature extraction utilities.

Provides mel-spectrogram, LFCC, and pre-processing helpers used by the
ML inference pipeline.  All operations are NumPy / torchaudio-based and
run on CPU.
"""

import numpy as np
import librosa
import torch
import torchaudio


class FeatureExtractor:
    """Multi-domain audio feature extractor for deepfake detection."""

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

        # Pre-build the LFCC transform (torchaudio)
        self._lfcc_transform = torchaudio.transforms.LFCC(
            sample_rate=sample_rate,
            n_lfcc=40,
            speckwargs={
                "n_fft": 1024,
                "hop_length": 256,
                "win_length": 1024,
            },
        )

    # ------------------------------------------------------------------
    # Pre-processing
    # ------------------------------------------------------------------

    @staticmethod
    def normalize(audio: np.ndarray) -> np.ndarray:
        """Peak-normalise audio to [-1, 1]."""
        peak = np.max(np.abs(audio))
        if peak > 0:
            return audio / peak
        return audio

    @staticmethod
    def pre_emphasis(audio: np.ndarray, coeff: float = 0.97) -> np.ndarray:
        """Apply a first-order pre-emphasis filter to boost high frequencies."""
        return np.append(audio[0], audio[1:] - coeff * audio[:-1])

    # ------------------------------------------------------------------
    # Feature extraction
    # ------------------------------------------------------------------

    def get_mel_spectrogram(
        self,
        audio: np.ndarray,
        n_mels: int = 80,
        apply_preemph: bool = True,
    ) -> np.ndarray:
        """Return log-mel spectrogram of shape ``[1, n_mels, time]``.

        Parameters
        ----------
        audio : np.ndarray
            1-D float32 audio waveform.
        n_mels : int
            Number of mel filter-banks.
        apply_preemph : bool
            Whether to apply pre-emphasis before extraction.
        """
        if apply_preemph:
            audio = self.pre_emphasis(audio)

        S = librosa.feature.melspectrogram(
            y=audio.astype(np.float32),
            sr=self.sample_rate,
            n_mels=n_mels,
            n_fft=1024,
            hop_length=256,
        )
        S_dB = librosa.power_to_db(S, ref=np.max)
        return np.expand_dims(S_dB, axis=0).astype(np.float32)  # [1, n_mels, T]

    def get_lfcc(self, audio: np.ndarray, n_lfcc: int = 40) -> np.ndarray:
        """Return LFCC features of shape ``[1, n_lfcc, time]``.

        LFCCs capture high-frequency vocoder artefacts better than MFCCs
        because they use a *linear* (not mel) filter-bank, preserving
        detail above 4 kHz where most synthesis artifacts reside.

        Parameters
        ----------
        audio : np.ndarray
            1-D float32 audio waveform.
        n_lfcc : int
            Number of LFCC coefficients.
        """
        waveform = torch.from_numpy(audio.astype(np.float32)).unsqueeze(0)  # [1, N]

        # Rebuild transform if n_lfcc changed from default
        if n_lfcc != self._lfcc_transform.n_lfcc:
            transform = torchaudio.transforms.LFCC(
                sample_rate=self.sample_rate,
                n_lfcc=n_lfcc,
                speckwargs={
                    "n_fft": 1024,
                    "hop_length": 256,
                    "win_length": 1024,
                },
            )
        else:
            transform = self._lfcc_transform

        with torch.no_grad():
            lfcc = transform(waveform)  # [1, n_lfcc, T]

        return lfcc.numpy().astype(np.float32)

    # ------------------------------------------------------------------
    # Batch helpers
    # ------------------------------------------------------------------

    def extract_all(self, audio: np.ndarray) -> dict:
        """Extract all features required by the downstream models.

        Returns a dict with keys ``raw``, ``mel``, ``lfcc`` — each ready
        to be fed to its corresponding ONNX model.

        Parameters
        ----------
        audio : np.ndarray
            1-D float32 waveform (expected ~2 s at 16 kHz = 32 000 samples).
        """
        audio = self.normalize(audio).astype(np.float32)
        raw = audio[np.newaxis, :]  # [1, N] for AASIST
        mel = self.get_mel_spectrogram(audio)
        lfcc = self.get_lfcc(audio)

        return {
            "raw": raw,
            "mel": mel,
            "lfcc": lfcc,
        }
