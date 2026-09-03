"""Compare extract_embedding vs extract_enrollment_embedding against 2s live windows."""

from __future__ import annotations

import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier
from app.ml.pipeline import InferencePipeline

SR = 16000

def _harmonic_voice(f0: float, duration: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0_t = f0 * (1.0 + 0.015 * np.sin(2 * np.pi * 4.5 * t))
    phase = 2 * np.pi * np.cumsum(f0_t) / SR
    y = np.zeros(n, dtype=np.float32)
    for h in range(1, 10):
        y += (0.28 / h) * np.sin(h * phase)
    # Add varying energy envelope with pauses
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 1.5 * t + float(rng.uniform(0, 1)))
    # Add a silent pause in middle (1.5s - 2.5s)
    env[int(1.5*SR):int(2.5*SR)] = 0.001
    y *= env.astype(np.float32)
    y += 0.005 * rng.standard_normal(n).astype(np.float32)
    peak = float(np.max(np.abs(y))) + 1e-8
    return (y / peak * 0.85).astype(np.float32)

def main():
    verifier = SpeakerVerifier()
    pipeline = InferencePipeline.get_instance()

    # 10 second audio file with speech and pauses
    audio_full = _harmonic_voice(f0=125.0, duration=10.0, seed=42)

    # Method 1: Current REST enrollment (_extract_speaker_only -> extract_embedding on 10s audio)
    emb_full_raw = pipeline._extract_speaker_only(audio_full)["embedding"]

    # Method 2: extract_enrollment_embedding (sliding 2s windows averaged)
    emb_full_avg = verifier.extract_enrollment_embedding(audio_full)

    print("Raw Full Audio Embedding Norm:", np.linalg.norm(emb_full_raw))
    print("Averaged Enrollment Embedding Norm:", np.linalg.norm(emb_full_avg))

    # Compare similarities over 5 different 2s speech chunks from the same audio
    print("\n--- Comparing Live 2s Chunks against Enrollment Methods ---")
    for i in range(5):
        chunk = audio_full[i*2*SR : (i+1)*2*SR]
        emb_chunk = verifier.extract_embedding(chunk)
        
        sim_raw = verifier.compute_similarity(emb_chunk, emb_full_raw)
        sim_avg = verifier.compute_similarity(emb_chunk, emb_full_avg)

        print(f"Chunk {i+1} (sec {i*2}-{(i+1)*2}): vs Raw Full = {sim_raw:.4f} | vs Averaged = {sim_avg:.4f}")

if __name__ == "__main__":
    main()
