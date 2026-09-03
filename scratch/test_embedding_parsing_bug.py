"""Test the hypothesis of embedding parsing bug."""

from __future__ import annotations

import sys
import numpy as np
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

from app.ml.speaker_verifier import SpeakerVerifier

def main():
    verifier = SpeakerVerifier()

    # Generate a real 192-dim live embedding
    rng = np.random.default_rng(42)
    audio = rng.standard_normal(16000 * 2).astype(np.float32)
    live_emb = verifier.extract_embedding(audio)

    # 1. Correct enrolled embedding (192 float elements)
    correct_enrolled = live_emb.copy()
    sim_correct = verifier.compute_similarity(live_emb, correct_enrolled)
    print(f"Correct 192-dim embedding similarity: {sim_correct:.4f}")

    # 2. What happens if DB returns a string representation '[0.1, 0.2, ...]'?
    string_emb_from_db = json.dumps(live_emb.tolist())
    # If code does: np.array(prof.embedding, dtype=np.float32) when prof.embedding is a string or invalid type:
    try:
        parsed_wrong = np.array(string_emb_from_db, dtype=np.float32)
        print("parsed_wrong shape:", parsed_wrong.shape, "size:", parsed_wrong.size)
    except Exception as e:
        print("Parsing string directly as float32 raised:", e)

    # What if string was converted via np.fromstring or json.loads or string representation?
    # Suppose v has size 1 or incomplete size:
    v_corrupted = np.array([live_emb[0]], dtype=np.float32) # size = 1
    # See what verifier._l2_normalize does:
    normalized_corrupted = verifier._l2_normalize(v_corrupted)
    sim_corrupted = verifier.compute_similarity(live_emb, normalized_corrupted)
    print(f"Corrupted (size=1) embedding similarity (Component 0): {sim_corrupted:.4f}")
    print(f"Exact Component 0 of live_emb: {live_emb[0]:.4f}")

if __name__ == "__main__":
    main()
