"""Verification script to test ECAPA speaker verification fix over 10 consecutive live updates."""

from __future__ import annotations

import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier
from app.ml.pipeline import InferencePipeline
from app.core.audio_buffer import VADSpeechAccumulator
from app.config import settings

SR = 16000

def _generate_synthetic_speech(f0: float, duration: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0_t = f0 * (1.0 + 0.012 * np.sin(2 * np.pi * 4.5 * t))
    phase = 2 * np.pi * np.cumsum(f0_t) / SR
    y = np.zeros(n, dtype=np.float32)
    for h in range(1, 10):
        y += (0.28 / h) * np.sin(h * phase)
    env = 0.65 + 0.35 * np.sin(2 * np.pi * 3.5 * t + float(rng.uniform(0, 1)))
    y *= env.astype(np.float32)
    y += 0.008 * rng.standard_normal(n).astype(np.float32)
    peak = float(np.max(np.abs(y))) + 1e-8
    return (y / peak * 0.85).astype(np.float32)

def main():
    print("=" * 85)
    print("VERIFICATION OF ECAPA SPEAKER VERIFICATION FIX (10 CONSECUTIVE LIVE UPDATES)")
    print("=" * 85)

    verifier = SpeakerVerifier()
    pipeline = InferencePipeline.get_instance()
    th = settings.speaker_verification_threshold

    # 1. Enrolled Speaker Audio (6.0s)
    audio_enroll = _generate_synthetic_speech(f0=125.0, duration=6.0, seed=42)

    # 2. Extract enrollment embedding using updated extract_enrollment_embedding
    enrollment_emb = verifier.extract_enrollment_embedding(audio_enroll)
    # Simulate DB serialization (e.g. stored as JSON string or list or Vector)
    db_stored_embedding_str = str(enrollment_emb.tolist())

    # Safely load back through updated _l2_normalize
    loaded_enrollment_emb = verifier._l2_normalize(db_stored_embedding_str)

    print(f"Loaded Enrollment Emb Shape: {loaded_enrollment_emb.shape}, Norm: {np.linalg.norm(loaded_enrollment_emb):.4f}")

    # TEST A: SAME SPEAKER - 10 CONSECUTIVE LIVE UPDATES
    print("\n" + "-" * 85, flush=True)
    print("TEST A: SAME SPEAKER (ENROLLED) — 10 CONSECUTIVE LIVE WEBSOCKET UPDATES", flush=True)
    print("-" * 85, flush=True)
    print(f"{'Update':<8} | {'Raw Sim (Before EMA)':<22} | {'EMA Sim (After EMA)':<22} | {'Threshold':<12} | {'Verified':<10}", flush=True)
    print("-" * 85, flush=True)

    audio_same_speaker = _generate_synthetic_speech(f0=125.0, duration=25.0, seed=101)
    speaker_speech_same = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim = None
    speaker_ema_alpha = 0.4

    chunk_size = 1024
    update_count = 0
    same_speaker_all_above_threshold = True

    for i in range(0, len(audio_same_speaker), chunk_size):
        frame = audio_same_speaker[i : i + chunk_size]
        pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_array = pcm16.astype(np.float32) / 32768.0

        speech_prob = pipeline.vad.is_speech(audio_array)
        is_speech = pipeline.vad.update_state(speech_prob, len(audio_array))
        if is_speech:
            speaker_speech_same.add_frames(audio_array)

        if speaker_speech_same.ready_for_embed():
            update_count += 1
            speech_window = speaker_speech_same.get_window()
            spk_res = verifier.verify_against_profile(speech_window, loaded_enrollment_emb)
            raw_sim = float(spk_res.get("similarity", 0.0))

            if stable_speaker_sim is None:
                stable_speaker_sim = raw_sim
            else:
                stable_speaker_sim = speaker_ema_alpha * raw_sim + (1.0 - speaker_ema_alpha) * stable_speaker_sim

            verified = bool(stable_speaker_sim >= th)
            if not verified:
                same_speaker_all_above_threshold = False

            print(f"{update_count:<8d} | {raw_sim:<22.4f} | {stable_speaker_sim:<22.4f} | {th:<12.4f} | {str(verified):<10}", flush=True)

            if update_count >= 10:
                break

    # TEST B: DIFFERENT SPEAKER - 10 CONSECUTIVE LIVE UPDATES
    print("\n" + "-" * 85, flush=True)
    print("TEST B: DIFFERENT SPEAKER (UNENROLLED) — 10 CONSECUTIVE LIVE WEBSOCKET UPDATES", flush=True)
    print("-" * 85, flush=True)
    print(f"{'Update':<8} | {'Raw Sim (Before EMA)':<22} | {'EMA Sim (After EMA)':<22} | {'Threshold':<12} | {'Verified':<10}", flush=True)
    print("-" * 85, flush=True)

    audio_diff_speaker = _generate_synthetic_speech(f0=210.0, duration=25.0, seed=999)
    speaker_speech_diff = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim_diff = None

    update_count_diff = 0
    diff_speaker_all_below_threshold = True

    for i in range(0, len(audio_diff_speaker), chunk_size):
        frame = audio_diff_speaker[i : i + chunk_size]
        pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_array = pcm16.astype(np.float32) / 32768.0

        speech_prob = pipeline.vad.is_speech(audio_array)
        is_speech = pipeline.vad.update_state(speech_prob, len(audio_array))
        if is_speech:
            speaker_speech_diff.add_frames(audio_array)

        if speaker_speech_diff.ready_for_embed():
            update_count_diff += 1
            speech_window = speaker_speech_diff.get_window()
            spk_res = verifier.verify_against_profile(speech_window, loaded_enrollment_emb)
            raw_sim = float(spk_res.get("similarity", 0.0))

            if stable_speaker_sim_diff is None:
                stable_speaker_sim_diff = raw_sim
            else:
                stable_speaker_sim_diff = speaker_ema_alpha * raw_sim + (1.0 - speaker_ema_alpha) * stable_speaker_sim_diff

            verified = bool(stable_speaker_sim_diff >= th)
            if verified:
                diff_speaker_all_below_threshold = False

            print(f"{update_count_diff:<8d} | {raw_sim:<22.4f} | {stable_speaker_sim_diff:<22.4f} | {th:<12.4f} | {str(verified):<10}", flush=True)

            if update_count_diff >= 10:
                break

    print("=" * 85)
    print(f"RESULTS: Enrolled Speaker > {th}: {same_speaker_all_above_threshold}")
    print(f"RESULTS: Different Speaker < {th}: {diff_speaker_all_below_threshold}")
    print("=" * 85)

if __name__ == "__main__":
    main()
