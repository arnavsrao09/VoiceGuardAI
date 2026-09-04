"""
Prosody forensics analyser for voice cloning detection.

Extracts microprosodic features that differ systematically between
natural human speech and neural-TTS / voice-cloned audio:

- **F0 (pitch)** — mean and standard deviation via pyworld's Harvest
  algorithm.  TTS tends to produce unnaturally smooth or quantised F0.
- **Jitter** — cycle-to-cycle period variation (natural < 1 %).
- **Shimmer** — cycle-to-cycle amplitude variation (natural < 3 %).
- **HNR** (Harmonics-to-Noise Ratio) — natural speech > 20 dB.
  Synthetic speech often has artificially high or low HNR.
- **Spectral Flatness** (Wiener entropy) — measures how tone-like vs.
  noise-like the spectrum is.  TTS produces unnaturally clean spectra
  with very low spectral flatness.

A weighted anomaly score aggregates all features into a single
``prosody_anomaly_score`` in [0, 1].
"""

from __future__ import annotations

import numpy as np
import parselmouth  # type: ignore
import pyworld as pw
from scipy.signal import welch


class ProsodyAnalyzer:
    """Full-spectrum prosody forensics analyser.

    Parameters
    ----------
    sample_rate : int
        Expected audio sample rate (default 16 000).
    """

    # ── Calibrated thresholds for conversational microphone speech
    #    Continuous conversational speech over microphones naturally exhibits
    #    3-4% jitter, 15-20% shimmer, and lower HNR than sustained vowels.
    _JITTER_NORMAL = 0.035         # 3.5 % (typical conversational baseline)
    _JITTER_ANOMALY_RANGE = 0.040  # anomaly ramps from 3.5% to 7.5%
    _SHIMMER_NORMAL = 0.160        # 16 %
    _SHIMMER_ANOMALY_RANGE = 0.100 # anomaly ramps from 16% to 26%
    _HNR_NORMAL = 9.0              # dB
    _HNR_ANOMALY_RANGE = 7.0       # anomaly ramps down from 9dB to 2dB
    _SPECTRAL_FLATNESS_HIGH = 0.15 # TTS tends to be < 0.015
    _F0_STD_NORMAL = 15.0          # Hz — conversational minimum variation

    # ── Anomaly score weights (sum = 1.0)
    # Spectral flatness and robotic pitch flatness are stronger TTS indicators
    _W_JITTER = 0.15
    _W_SHIMMER = 0.15
    _W_HNR = 0.15
    _W_SPECTRAL = 0.30
    _W_F0_STD = 0.25

    def __init__(self, sample_rate: int = 16000):
        self.sample_rate = sample_rate

    # ------------------------------------------------------------------
    #  Public API
    # ------------------------------------------------------------------

    def analyze(self, audio: np.ndarray) -> dict:
        """Perform full prosody analysis on an audio chunk.

        Parameters
        ----------
        audio : np.ndarray
            1-D float32/float64 waveform (≥0.5 s recommended).

        Returns
        -------
        dict
            Feature values and the composite anomaly score.
        """
        audio_f64 = audio.astype(np.float64)
        audio_f32 = audio.astype(np.float32)

        # 1. F0 via pyworld Harvest
        f0_mean, f0_std = self._extract_f0(audio_f64)

        # 2. Jitter, shimmer, HNR via Praat (parselmouth)
        jitter, shimmer, hnr = self._extract_praat_features(audio_f32)

        # 3. Spectral flatness via scipy Welch PSD
        spectral_flatness = self._spectral_flatness(audio_f32)

        # 4. Composite anomaly score
        anomaly = self._compute_anomaly(
            jitter, shimmer, hnr, spectral_flatness, f0_std,
        )

        return {
            "f0_mean": round(float(f0_mean), 2),
            "f0_std": round(float(f0_std), 2),
            "jitter": round(float(jitter), 6),
            "shimmer": round(float(shimmer), 6),
            "hnr": round(float(hnr), 2),
            "spectral_flatness": round(float(spectral_flatness), 6),
            "prosody_anomaly_score": round(float(anomaly), 4),
        }

    # ------------------------------------------------------------------
    #  Feature extractors
    # ------------------------------------------------------------------

    def _extract_f0(self, audio_f64: np.ndarray) -> tuple[float, float]:
        """Extract mean and std of F0 using pyworld Harvest."""
        try:
            f0, _t = pw.harvest(audio_f64, self.sample_rate)
            voiced = f0[f0 > 0]
            if len(voiced) > 2:
                return float(np.mean(voiced)), float(np.std(voiced))
        except Exception:
            pass
        return 0.0, 0.0

    def _extract_praat_features(
        self, audio: np.ndarray
    ) -> tuple[float, float, float]:
        """Extract jitter, shimmer, and HNR via Praat (parselmouth)."""
        try:
            snd = parselmouth.Sound(audio, sampling_frequency=self.sample_rate)

            # Point-process for period-based measures
            pp = parselmouth.praat.call(
                snd, "To PointProcess (periodic, cc)", 75.0, 600.0
            )

            jitter = parselmouth.praat.call(
                pp, "Get jitter (local)", 0.0, 0.0, 0.0001, 0.02, 1.3
            )

            shimmer = parselmouth.praat.call(
                [snd, pp],
                "Get shimmer (local)",
                0, 0, 0.0001, 0.02, 1.3, 1.6,
            )

            # HNR via harmonicity object
            harmonicity = parselmouth.praat.call(
                snd, "To Harmonicity (cc)", 0.01, 75.0, 0.1, 1.0
            )
            hnr = parselmouth.praat.call(
                harmonicity, "Get mean", 0.0, 0.0
            )

            # Praat returns -200 for unvoiced frames; clamp.
            jitter = jitter if jitter and jitter == jitter else 0.0
            shimmer = shimmer if shimmer and shimmer == shimmer else 0.0
            hnr = hnr if hnr and hnr > -100 else 0.0

            return float(jitter), float(shimmer), float(hnr)

        except Exception:
            return 0.0, 0.0, 0.0

    def _spectral_flatness(self, audio: np.ndarray) -> float:
        """Spectral flatness (Wiener entropy): geometric / arithmetic mean
        of the power spectrum.

        A value close to 1 indicates noise-like; close to 0 indicates
        tonal / harmonic content.
        """
        try:
            _, psd = welch(audio, fs=self.sample_rate, nperseg=1024)
            psd = psd[psd > 0]
            if len(psd) == 0:
                return 0.0
            geo_mean = np.exp(np.mean(np.log(psd + 1e-12)))
            arith_mean = np.mean(psd)
            return float(geo_mean / (arith_mean + 1e-12))
        except Exception:
            return 0.0

    # ------------------------------------------------------------------
    #  Anomaly scoring
    # ------------------------------------------------------------------

    def _compute_anomaly(
        self,
        jitter: float,
        shimmer: float,
        hnr: float,
        spectral_flatness: float,
        f0_std: float,
    ) -> float:
        """Compute a weighted anomaly score in [0, 1].

        Each feature is mapped to an anomaly value via a linear ramp
        between "normal" and "fully anomalous" bounds, then combined
        with learned weights.
        """
        j_anom = self._ramp(jitter, self._JITTER_NORMAL, self._JITTER_ANOMALY_RANGE)
        s_anom = self._ramp(shimmer, self._SHIMMER_NORMAL, self._SHIMMER_ANOMALY_RANGE)

        # HNR: *low* HNR is anomalous (inverted ramp)
        hnr_anom = self._ramp(
            self._HNR_NORMAL - hnr, 0.0, self._HNR_ANOMALY_RANGE
        ) if hnr > 0 else 0.5

        # Spectral flatness: very LOW flatness is suspicious for TTS
        # (unnaturally clean spectrum).  Very HIGH flatness is just noise.
        if spectral_flatness < 0.01:
            sf_anom = 0.9  # near-zero flatness → very suspicious
        elif spectral_flatness < self._SPECTRAL_FLATNESS_HIGH:
            sf_anom = max(0.0, 1.0 - spectral_flatness / self._SPECTRAL_FLATNESS_HIGH)
        else:
            sf_anom = 0.0  # normal-to-noisy range

        # F0 std: very LOW std (monotone) is suspicious
        if f0_std > 0:
            f0_anom = max(0.0, 1.0 - f0_std / self._F0_STD_NORMAL)
        else:
            f0_anom = 0.5  # no voicing detected

        score = (
            self._W_JITTER * j_anom
            + self._W_SHIMMER * s_anom
            + self._W_HNR * hnr_anom
            + self._W_SPECTRAL * sf_anom
            + self._W_F0_STD * f0_anom
        )

        return float(np.clip(score, 0.0, 1.0))

    # ------------------------------------------------------------------
    #  Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _ramp(value: float, threshold: float, range_: float) -> float:
        """Linear ramp: 0 at *threshold*, 1 at *threshold + range_*."""
        if range_ <= 0:
            return 0.0
        return float(np.clip((value - threshold) / range_, 0.0, 1.0))
