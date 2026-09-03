"""Test and log 10 consecutive ECAPA EMA speaker updates."""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier
from app.config import settings

SR = 16000

def _harmonic_voice(f0: float, duration: float, rng: np.random.Generator, vibrato_hz: float) -> np.ndarray:
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0_t = f0 * (1.0 + 0.012 * np.sin(2 * np.pi * vibrato_hz * t))
    phase = 2 * np.pi * np.cumsum(f0_t) / SR
    y = np.zeros(n, dtype=np.float32)
    for h in range(1, 10):
        y += (0.28 / h) * np.sin(h * phase)
    env = 0.65 + 0.35 * np.sin(2 * np.pi * 3.5 * t + float(rng.uniform(0, 1)))
    y *= env.astype(np.float32)
    y += 0.008 * rng.standard_normal(n).astype(np.float32)
    peak = float(np.max(np.abs(y))) + 1e-8
    return (y / peak * 0.85).astype(np.float32)

def main() -> None:
    verifier = SpeakerVerifier()
    rng_enrolled = np.random.default_rng(42)
    rng_stream = np.random.default_rng(101)

    # Generate enrolled voice sample and extract profile embedding
    enrolled_audio = _harmonic_voice(f0=130.0, duration=5.0, rng=rng_enrolled, vibrato_hz=4.5)
    enrolled_emb = verifier.extract_embedding(enrolled_audio)

    # Session EMA state (same logic as websocket.py)
    stable_speaker_sim: float | None = None
    speaker_ema_alpha = 0.4
    threshold = settings.speaker_verification_threshold

    print("=" * 80)
    print("ECAPA EMA SPEAKER VERIFICATION LOG (10 CONSECUTIVE UPDATES)")
    print(f"Initial threshold (unchanged): {threshold}")
    print("=" * 80)
    print(f"{'Update':<8} | {'Raw ECAPA Sim':<15} | {'EMA-Smoothed Sim':<18} | {'Threshold':<12} | {'Speaker Verified':<16}")
    print("-" * 80)

    # Simulate 10 consecutive speaker updates
    for update_idx in range(1, 11):
        # Generate 2.0s speech window (varying slightly around enrolled speaker pitch)
        f0_var = 130.0 + (rng_stream.uniform(-5.0, 5.0) if update_idx <= 7 else rng_stream.uniform(-35.0, -25.0))
        chunk = _harmonic_voice(f0=f0_var, duration=2.0, rng=rng_stream, vibrato_hz=4.5)

        res = verifier.verify_against_profile(chunk, enrolled_emb)
        raw_sim = float(res.get("similarity", 0.0))
        if np.isnan(raw_sim) or np.isinf(raw_sim):
            raw_sim = 0.0

        if stable_speaker_sim is None:
            # Verification step: MUST be initialized with first valid similarity, NOT 0.0
            stable_speaker_sim = raw_sim
        else:
            stable_speaker_sim = (
                speaker_ema_alpha * raw_sim + (1.0 - speaker_ema_alpha) * stable_speaker_sim
            )

        speaker_verified = bool(stable_speaker_sim >= threshold)

        print(
            f"{update_idx:<8} | "
            f"{raw_sim:<15.4f} | "
            f"{stable_speaker_sim:<18.4f} | "
            f"{threshold:<12.4f} | "
            f"{str(speaker_verified):<16}"
        )

    print("=" * 80)
    print("Initialization Check: First update EMA-smoothed similarity equals raw ECAPA similarity.")
    print("=" * 80)

if __name__ == "__main__":
    main()
