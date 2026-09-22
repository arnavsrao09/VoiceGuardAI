import pytest
from app.ml.risk_scorer import RiskScorer

def test_ema_isolation_and_smoothing():
    scorer1 = RiskScorer()
    scorer2 = RiskScorer()
    
    # First chunk initializes EMA
    res1 = scorer1.compute_score(deepfake_prob=0.8, speaker_match=0.9, prosody_anomaly=0.2)
    assert res1["chunk_index"] == 1
    assert res1["deepfake_score"] == 0.8
    
    # Second chunk smooths (alpha = 0.3)
    res2 = scorer1.compute_score(deepfake_prob=0.2, speaker_match=0.9, prosody_anomaly=0.2)
    # EMA = 0.3 * 0.2 + 0.7 * 0.8 = 0.06 + 0.56 = 0.62
    assert pytest.approx(res2["deepfake_score"], 0.01) == 0.62
    
    # Scorer 2 should be completely isolated
    res_s2 = scorer2.compute_score(deepfake_prob=0.1, speaker_match=0.9, prosody_anomaly=0.2)
    assert res_s2["chunk_index"] == 1
    assert res_s2["deepfake_score"] == 0.1

def test_confidence_gating():
    scorer = RiskScorer()
    # High deepfake prob (0.9), but low confidence (0.5)
    res = scorer.compute_score(deepfake_prob=0.9, speaker_match=0.9, prosody_anomaly=0.2, deepfake_confidence=0.5)
    
    # Check requires_review and capped level
    assert res["requires_review"] is True
    assert res["level"] == "MEDIUM"

def test_confidence_gating_high_confidence():
    scorer = RiskScorer()
    # High deepfake prob (0.9), high confidence (0.9)
    res = scorer.compute_score(deepfake_prob=0.9, speaker_match=0.9, prosody_anomaly=0.2, deepfake_confidence=0.9)
    
    assert res["requires_review"] is False
    assert res["level"] in ("HIGH", "CRITICAL")
