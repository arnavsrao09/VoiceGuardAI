"""ECAPA embedding sanity checks (SpeechBrain EncoderClassifier)."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier  # noqa: E402

SR = 16000


def _harmonic_voice(f0: float, duration: float, rng: np.random.Generator, vibrato_hz: float) -> np.ndarray:
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0_t = f0 * (1.0 + 0.012 * np.sin(2 * np.pi * vibrato_hz * t))
    phase = 2 * np.pi * np.cumsum(f0_t) / SR
    y = np.zeros(n, dtype=np.float32)
    for h in range(1, 10):
        y += (0.28 / h) * np.sin(h * phase)
    # Mild formant-like emphasis via a moving-average envelope
    env = 0.65 + 0.35 * np.sin(2 * np.pi * 3.5 * t + float(rng.uniform(0, 1)))
    y *= env.astype(np.float32)
    y += 0.008 * rng.standard_normal(n).astype(np.float32)
    peak = float(np.max(np.abs(y))) + 1e-8
    return (y / peak * 0.85).astype(np.float32)


def main() -> None:
    verifier = SpeakerVerifier()

    rng_a = np.random.default_rng(7)
    rng_b = np.random.default_rng(99)

    speaker_a = _harmonic_voice(f0=118.0, duration=6.0, rng=rng_a, vibrato_hz=4.8)
    rec_a1 = speaker_a[: 3 * SR]
    rec_a2 = speaker_a[3 * SR : 6 * SR]
    rec_b = _harmonic_voice(f0=205.0, duration=3.0, rng=rng_b, vibrato_hz=5.6)

    emb_a1 = verifier.extract_embedding(rec_a1)
    emb_a1_again = verifier.extract_embedding(rec_a1.copy())
    emb_a2 = verifier.extract_embedding(rec_a2)
    emb_b = verifier.extract_embedding(rec_b)

    print("embedding shape:", tuple(emb_a1.shape))
    print("embedding norm:", float(np.linalg.norm(emb_a1)))
    print("same audio vs itself similarity:", round(verifier.compute_similarity(emb_a1, emb_a1_again), 4))
    print(
        "same speaker different recordings similarity:",
        round(verifier.compute_similarity(emb_a1, emb_a2), 4),
    )
    print("different speaker similarity:", round(verifier.compute_similarity(emb_a1, emb_b), 4))


if __name__ == "__main__":
    main()
