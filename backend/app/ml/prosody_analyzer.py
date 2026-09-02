import numpy as np
import logging
import asyncio
import pyworld as pw
import parselmouth
from parselmouth.praat import call
from typing import Dict

from app.ml.base import ProsodyAnalyzer

logger = logging.getLogger(__name__)

class PyWorldProsodyAnalyzer(ProsodyAnalyzer):
    async def analyze(self, audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
        return await asyncio.to_thread(self._analyze_sync, audio, sample_rate)
        
    def _analyze_sync(self, audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
        try:
            # Ensure float64 for pyworld
            audio_f64 = audio.astype(np.float64)
            
            # PyWorld features
            _f0, t = pw.dio(audio_f64, sample_rate)
            f0 = pw.stonemask(audio_f64, _f0, t, sample_rate)
            
            # Praat features via parselmouth
            snd = parselmouth.Sound(audio, sampling_frequency=sample_rate)
            pitch = call(snd, "To Pitch", 0.0, 75, 600)
            pointProcess = call(snd, "To PointProcess (periodic, cc)", 75, 600)
            
            # Jitter, Shimmer, HNR
            jitter = call(pointProcess, "Get jitter (local)", 0.0001, 0.02, 1.3)
            shimmer = call([snd, pointProcess], "Get shimmer (local)", 0, 0, 0.0001, 0.02, 1.3, 1.6)
            harmonicity = call(snd, "To Harmonicity (cc)", 0.01, 75, 0.1, 1.0)
            hnr = call(harmonicity, "Get mean", 0, 0)
            
            # Clean up potential NaNs
            def safe_val(val, default=0.0):
                return float(val) if val == val and val is not None else default

            f0_mean = safe_val(np.mean(f0[f0 > 0]))
            jitter_val = safe_val(jitter)
            shimmer_val = safe_val(shimmer)
            hnr_val = safe_val(hnr)
            
            # Heuristic anomaly score (simplified)
            # Typically, synthetic speech might have extremely low jitter/shimmer (too perfect)
            # or weird HNR. We'll just define a naive heuristic mapping for the prototype.
            anomaly_score = 0.0
            if jitter_val < 0.005: anomaly_score += 0.2
            if shimmer_val < 0.02: anomaly_score += 0.2
            if hnr_val > 25: anomaly_score += 0.2
            
            return {
                "f0_mean": f0_mean,
                "jitter": jitter_val,
                "shimmer": shimmer_val,
                "hnr": hnr_val,
                "spectral_flatness": 0.0, # Placeholder
                "anomaly_score": min(anomaly_score, 1.0)
            }
        except Exception as e:
            logger.error(f"Prosody analysis error: {e}")
            return {
                "f0_mean": 0.0,
                "jitter": 0.0,
                "shimmer": 0.0,
                "hnr": 0.0,
                "spectral_flatness": 0.0,
                "anomaly_score": 0.5 # Default uncertain
            }
