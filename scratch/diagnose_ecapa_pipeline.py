"""Diagnostic script to trace ECAPA speaker verification pipeline issues."""

from __future__ import annotations

import sys
import io
import uuid
import numpy as np
import librosa
from pathlib import Path
import asyncio

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier
from app.ml.pipeline import InferencePipeline
from app.core.audio_buffer import VADSpeechAccumulator
from app.config import settings

SR = 16000

def _generate_test_speech(f0: float = 130.0, duration: float = 5.0, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0_t = f0 * (1.0 + 0.015 * np.sin(2 * np.pi * 4.5 * t))
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
    print("=" * 80)
    print("ECAPA PIPELINE DIAGNOSTICS & COMPARISON TEST")
    print("=" * 80)

    verifier = SpeakerVerifier()

    # 1. Generate same speaker audio (Utterance 1 for enrollment, Utterance 2 for verification)
    audio_enrolled = _generate_test_speech(f0=130.0, duration=6.0, seed=42)
    audio_same = _generate_test_speech(f0=130.0, duration=6.0, seed=101)
    audio_diff = _generate_test_speech(f0=210.0, duration=6.0, seed=999)

    # Method A: verifier.extract_embedding (REST enrollment currently uses pipeline._extract_speaker_only)
    emb_enroll_direct = verifier.extract_embedding(audio_enrolled)
    
    # Method B: verifier.extract_enrollment_embedding
    emb_enroll_avg = verifier.extract_enrollment_embedding(audio_enrolled)

    print(f"Direct Enrollment Emb Shape: {emb_enroll_direct.shape}, Norm: {np.linalg.norm(emb_enroll_direct):.4f}")
    print(f"Averaged Enrollment Emb Shape: {emb_enroll_avg.shape}, Norm: {np.linalg.norm(emb_enroll_avg):.4f}")

    # Test REST-like verification against Direct vs Averaged Enrollment
    emb_same_full = verifier.extract_embedding(audio_same)
    sim_direct = verifier.compute_similarity(emb_same_full, emb_enroll_direct)
    sim_avg = verifier.compute_similarity(emb_same_full, emb_enroll_avg)

    print(f"\nSame Speaker (Full 6s audio vs Enrollment):")
    print(f"  vs Direct Enrollment Embedding:   {sim_direct:.4f}")
    print(f"  vs Averaged Enrollment Embedding: {sim_avg:.4f}")

    # Simulate WebSocket streaming in chunks (1024 samples PCM = 64ms chunks)
    print("\n" + "-" * 80)
    print("SIMULATING WEBSOCKET LIVE STREAMING (2s VADSpeechAccumulator windows)")
    print("-" * 80)

    for mode, emb_ref in [("Direct", emb_enroll_direct), ("Averaged", emb_enroll_avg)]:
        print(f"\n--- Testing WebSocket Live Streaming vs {mode} Enrollment ---")
        speaker_speech = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
        stable_speaker_sim = None
        speaker_ema_alpha = 0.4
        th = settings.speaker_verification_threshold

        chunk_size = 1024
        # Pass audio_same in chunks
        update_count = 0
        for i in range(0, len(audio_same), chunk_size):
            chunk = audio_same[i : i + chunk_size]
            # Convert float -> Int16 -> float32 (simulating browser PCM uint16 transmission)
            pcm16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
            reconstructed_float = pcm16.astype(np.float32) / 32768.0

            speaker_speech.add_frames(reconstructed_float)

            if speaker_speech.ready_for_embed():
                update_count += 1
                speech_window = speaker_speech.get_window()
                res = verifier.verify_against_profile(speech_window, emb_ref)
                raw_sim = float(res.get("similarity", 0.0))

                if stable_speaker_sim is None:
                    stable_speaker_sim = raw_sim
                else:
                    stable_speaker_sim = speaker_ema_alpha * raw_sim + (1 - speaker_ema_alpha) * stable_speaker_sim

                verified = stable_speaker_sim >= th
                print(f"Update {update_count:2d} (Window len: {len(speech_window):5d} samples, {len(speech_window)/16000:.2f}s): "
                      f"Raw Sim = {raw_sim:7.4f} | EMA Sim = {stable_speaker_sim:7.4f} | Verified = {verified}")

    # Now test DIFFERENT speaker through WebSocket
    print(f"\n--- Testing Different Speaker (f0=210Hz) vs Direct Enrollment ---")
    speaker_speech_diff = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim = None
    update_count = 0
    for i in range(0, len(audio_diff), chunk_size):
        chunk = audio_diff[i : i + chunk_size]
        pcm16 = (np.clip(chunk, -1.0, 1.0) * 32767).astype(np.int16)
        reconstructed_float = pcm16.astype(np.float32) / 32768.0

        speaker_speech_diff.add_frames(reconstructed_float)

        if speaker_speech_diff.ready_for_embed():
            update_count += 1
            speech_window = speaker_speech_diff.get_window()
            res = verifier.verify_against_profile(speech_window, emb_enroll_direct)
            raw_sim = float(res.get("similarity", 0.0))

            if stable_speaker_sim is None:
                stable_speaker_sim = raw_sim
            else:
                stable_speaker_sim = speaker_ema_alpha * raw_sim + (1 - speaker_ema_alpha) * stable_speaker_sim

            verified = stable_speaker_sim >= th
            print(f"Update {update_count:2d} (Window len: {len(speech_window):5d} samples, {len(speech_window)/16000:.2f}s): "
                  f"Raw Sim = {raw_sim:7.4f} | EMA Sim = {stable_speaker_sim:7.4f} | Verified = {verified}")

if __name__ == "__main__":
    main()
