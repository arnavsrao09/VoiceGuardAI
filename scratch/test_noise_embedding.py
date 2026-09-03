"""Test ECAPA similarity on background noise, quiet speech, and low-volume frames."""

from __future__ import annotations

import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier

SR = 16000

def main():
    verifier = SpeakerVerifier()

    # Create reference enrolled voice
    rng = np.random.default_rng(42)
    t = np.arange(3 * SR, dtype=np.float32) / SR
    speech = (0.5 * np.sin(2 * np.pi * 130 * t) * (1 + 0.3 * np.sin(2 * np.pi * 3 * t))).astype(np.float32)
    emb_ref = verifier.extract_embedding(speech)

    print("Reference embedding norm:", np.linalg.norm(emb_ref))

    # 1. Test pure silence / near-zero audio
    silence = np.zeros(2 * SR, dtype=np.float32)
    res_silence = verifier.verify_against_profile(silence, emb_ref)
    print(f"Silence similarity: {res_silence['similarity']:.4f}")

    # 2. Test quiet white noise / background mic hum (RMS = 0.003)
    quiet_noise = (0.003 * rng.standard_normal(2 * SR)).astype(np.float32)
    res_noise = verifier.verify_against_profile(quiet_noise, emb_ref)
    print(f"Quiet background noise similarity: {res_noise['similarity']:.4f}")

    # 3. Test noise mixed with speech (low SNR)
    noisy_speech = speech[: 2 * SR] * 0.1 + quiet_noise
    res_noisy = verifier.verify_against_profile(noisy_speech, emb_ref)
    print(f"Low-volume speech similarity: {res_noisy['similarity']:.4f}")

if __name__ == "__main__":
    main()
