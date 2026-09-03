"""Test 10 consecutive live updates with simulated speech frames passing VAD."""

from __future__ import annotations

import sys
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier
from app.core.audio_buffer import VADSpeechAccumulator
from app.config import settings

SR = 16000

def _speech_signal(f0: float, duration: float, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    n = int(duration * SR)
    t = np.arange(n, dtype=np.float32) / SR
    f0_t = f0 * (1.0 + 0.02 * np.sin(2 * np.pi * 4.0 * t))
    phase = 2 * np.pi * np.cumsum(f0_t) / SR
    y = np.zeros(n, dtype=np.float32)
    for h in range(1, 8):
        y += (0.3 / h) * np.sin(h * phase)
    # Formant envelope
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 2.5 * t + float(rng.uniform(0, 1)))
    y *= env.astype(np.float32)
    y += 0.01 * rng.standard_normal(n).astype(np.float32)
    peak = float(np.max(np.abs(y))) + 1e-8
    return (y / peak * 0.85).astype(np.float32)

def main():
    verifier = SpeakerVerifier()
    th = settings.speaker_verification_threshold

    # 1. Enrolled Speaker
    audio_enroll = _speech_signal(f0=125.0, duration=6.0, seed=42)
    enrollment_emb = verifier.extract_enrollment_embedding(audio_enroll)
    
    # Store and reload via _l2_normalize
    loaded_enrollment_emb = verifier._l2_normalize(str(enrollment_emb.tolist()))

    print(f"Loaded Enrollment Emb Shape: {loaded_enrollment_emb.shape}, Norm: {np.linalg.norm(loaded_enrollment_emb):.4f}")

    # TEST A: SAME SPEAKER (ENROLLED)
    print("\n" + "=" * 90)
    print("TEST A: SAME SPEAKER (ENROLLED) — 10 CONSECUTIVE LIVE WEBSOCKET UPDATES")
    print("=" * 90)
    print(f"{'Update':<8} | {'Raw Sim (Before EMA)':<22} | {'EMA Sim (After EMA)':<22} | {'Threshold':<12} | {'Verified':<10}")
    print("-" * 90)

    audio_same = _speech_signal(f0=125.0, duration=20.0, seed=101)
    speaker_speech_same = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim = None
    speaker_ema_alpha = 0.4

    chunk_size = 1024
    update_count = 0

    for i in range(0, len(audio_same), chunk_size):
        frame = audio_same[i : i + chunk_size]
        pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_array = pcm16.astype(np.float32) / 32768.0

        # Simulate VAD active speech buffering
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
            print(f"{update_count:<8d} | {raw_sim:<22.4f} | {stable_speaker_sim:<22.4f} | {th:<12.4f} | {str(verified):<10}")

            if update_count >= 10:
                break

    # TEST B: DIFFERENT SPEAKER (UNENROLLED)
    print("\n" + "=" * 90)
    print("TEST B: DIFFERENT SPEAKER (UNENROLLED) — 10 CONSECUTIVE LIVE WEBSOCKET UPDATES")
    print("=" * 90)
    print(f"{'Update':<8} | {'Raw Sim (Before EMA)':<22} | {'EMA Sim (After EMA)':<22} | {'Threshold':<12} | {'Verified':<10}")
    print("-" * 90)

    audio_diff = _speech_signal(f0=210.0, duration=20.0, seed=999)
    speaker_speech_diff = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim_diff = None
    update_count_diff = 0

    for i in range(0, len(audio_diff), chunk_size):
        frame = audio_diff[i : i + chunk_size]
        pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_array = pcm16.astype(np.float32) / 32768.0

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
            print(f"{update_count_diff:<8d} | {raw_sim:<22.4f} | {stable_speaker_sim_diff:<22.4f} | {th:<12.4f} | {str(verified):<10}")

            if update_count_diff >= 10:
                break

if __name__ == "__main__":
    main()
