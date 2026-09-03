"""Controlled comparison tests for ECAPA Speaker Verification pipeline.

Runs:
1. Same audio file -> REST vs REST
2. Same audio file -> REST enrollment vs WebSocket verification
3. Same speaker -> live WebSocket
4. Different speaker -> live WebSocket
"""

from __future__ import annotations

import sys
import uuid
import asyncio
import numpy as np
import librosa
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier
from app.ml.pipeline import InferencePipeline
from app.core.audio_buffer import VADSpeechAccumulator
from app.db.database import AsyncSessionLocal
from app.db import crud
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

async def run_controlled_tests():
    print("=" * 80)
    print("CONTROLLED TEST SUITE FOR ECAPA SPEAKER VERIFICATION")
    print("=" * 80)

    verifier = SpeakerVerifier()
    pipeline = InferencePipeline.get_instance()

    # Audio A (Enrolled Speaker) - 6 seconds
    audio_a_enroll = _generate_synthetic_speech(f0=120.0, duration=6.0, seed=1)
    audio_a_test1 = _generate_synthetic_speech(f0=120.0, duration=6.0, seed=2) # Same speaker
    audio_b_test2 = _generate_synthetic_speech(f0=210.0, duration=6.0, seed=99) # Different speaker

    # -------------------------------------------------------------------------
    # TEST 1: Same audio file -> REST enrollment vs REST verification
    # -------------------------------------------------------------------------
    print("\n--- TEST 1: Same Audio File -> REST Enrollment vs REST Verification ---")
    # REST enrollment currently calls pipeline._extract_speaker_only(y)
    rest_enroll_emb = pipeline._extract_speaker_only(audio_a_enroll)["embedding"]
    print(f"Enrolled embedding shape: {rest_enroll_emb.shape}, norm: {np.linalg.norm(rest_enroll_emb):.4f}")

    # Verify audio_a_enroll against itself
    res_self = verifier.verify_against_profile(audio_a_enroll, rest_enroll_emb)
    print(f"Self-verification similarity: {res_self['similarity']:.4f} (Expected: ~1.0)")

    # Verify audio_a_test1 (same speaker, different recording) via REST
    res_same_rest = verifier.verify_against_profile(audio_a_test1, rest_enroll_emb)
    print(f"Same speaker REST verification similarity: {res_same_rest['similarity']:.4f}")

    # -------------------------------------------------------------------------
    # TEST 2: Same audio file -> REST enrollment vs WebSocket live verification
    # -------------------------------------------------------------------------
    print("\n--- TEST 2: Same Audio File -> REST Enrollment vs WebSocket Live Verification ---")
    speaker_speech = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim = None
    speaker_ema_alpha = 0.4
    th = settings.speaker_verification_threshold

    # Feed audio_a_test1 in 1024-sample PCM frames over simulated WebSocket
    chunk_size = 1024
    ws_updates = []
    for i in range(0, len(audio_a_test1), chunk_size):
        frame = audio_a_test1[i : i + chunk_size]
        pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_array = pcm16.astype(np.float32) / 32768.0

        speech_prob = pipeline.vad.is_speech(audio_array)
        is_speech = pipeline.vad.update_state(speech_prob, len(audio_array))
        if is_speech:
            speaker_speech.add_frames(audio_array)

        if speaker_speech.ready_for_embed():
            speech_window = speaker_speech.get_window()
            spk_res = verifier.verify_against_profile(speech_window, rest_enroll_emb)
            raw_sim = float(spk_res.get("similarity", 0.0))
            if stable_speaker_sim is None:
                stable_speaker_sim = raw_sim
            else:
                stable_speaker_sim = speaker_ema_alpha * raw_sim + (1.0 - speaker_ema_alpha) * stable_speaker_sim
            
            verified = bool(stable_speaker_sim >= th)
            ws_updates.append((raw_sim, stable_speaker_sim, verified))
            print(f"Update {len(ws_updates):2d}: Raw Sim = {raw_sim:.4f} | EMA Sim = {stable_speaker_sim:.4f} | Verified = {verified}")

    # -------------------------------------------------------------------------
    # TEST 3: DB Profile Check & Organization Scope
    # -------------------------------------------------------------------------
    print("\n--- TEST 3: Voice Profile Database Lookup Test ---")
    async with AsyncSessionLocal() as db:
        # Create a test organization
        org = await crud.create_organization(db, name="ECAPA Test Org", email=f"test_{uuid.uuid4().hex[:6]}@org.com", hashed_password="pass")
        # Enroll voice profile under org
        profile = await crud.create_voice_profile(
            db, organization_id=org.id, external_user_id="user_1", name="Test Speaker", embedding=rest_enroll_emb.tolist()
        )
        print(f"Created VoiceProfile ID: {profile.id} under Org ID: {org.id}")

        # Try retrieving profile WITH matching org_id
        prof_matched = await crud.get_voice_profile(db, profile.id, organization_id=org.id)
        print(f"Lookup WITH matching org: Found = {prof_matched is not None}")

        # Try retrieving profile WITH mismatched org_id (e.g. None or random org_id)
        prof_mismatched = await crud.get_voice_profile(db, profile.id, organization_id=uuid.uuid4())
        print(f"Lookup WITH mismatched org: Found = {prof_mismatched is not None}")

        # Try retrieving profile with organization_id = None
        prof_no_org = await crud.get_voice_profile(db, profile.id, organization_id=None)
        print(f"Lookup WITH organization_id=None: Found = {prof_no_org is not None}")

    # -------------------------------------------------------------------------
    # TEST 4: Different Speaker -> Live WebSocket
    # -------------------------------------------------------------------------
    print("\n--- TEST 4: Different Speaker -> Live WebSocket Verification ---")
    speaker_speech_b = VADSpeechAccumulator(min_sec=1.5, max_sec=3.0, hop_sec=1.0)
    stable_speaker_sim_b = None
    ws_updates_b = []
    for i in range(0, len(audio_b_test2), chunk_size):
        frame = audio_b_test2[i : i + chunk_size]
        pcm16 = (np.clip(frame, -1.0, 1.0) * 32767).astype(np.int16)
        audio_array = pcm16.astype(np.float32) / 32768.0

        speech_prob = pipeline.vad.is_speech(audio_array)
        is_speech = pipeline.vad.update_state(speech_prob, len(audio_array))
        if is_speech:
            speaker_speech_b.add_frames(audio_array)

        if speaker_speech_b.ready_for_embed():
            speech_window = speaker_speech_b.get_window()
            spk_res = verifier.verify_against_profile(speech_window, rest_enroll_emb)
            raw_sim = float(spk_res.get("similarity", 0.0))
            if stable_speaker_sim_b is None:
                stable_speaker_sim_b = raw_sim
            else:
                stable_speaker_sim_b = speaker_ema_alpha * raw_sim + (1.0 - speaker_ema_alpha) * stable_speaker_sim_b
            
            verified = bool(stable_speaker_sim_b >= th)
            ws_updates_b.append((raw_sim, stable_speaker_sim_b, verified))
            print(f"Update {len(ws_updates_b):2d}: Raw Sim = {raw_sim:.4f} | EMA Sim = {stable_speaker_sim_b:.4f} | Verified = {verified}")

if __name__ == "__main__":
    asyncio.run(run_controlled_tests())
