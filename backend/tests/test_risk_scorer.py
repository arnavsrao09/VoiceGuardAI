import pytest
from app.ml.risk_scorer import RiskScorer
from app.core.config import settings

def test_raw_score_calculation():
    scorer = RiskScorer()
    
    # Scenario: Genuine speech
    score1 = scorer.calculate_raw_score(
        deepfake_prob=0.1,
        speaker_sim=0.9, # Match -> mismatch = 0.1
        prosody_anomaly=0.1,
        context_score=0.1
    )
    assert score1 < settings.LOW_RISK_THRESHOLD
    
    # Scenario: High deepfake
    score2 = scorer.calculate_raw_score(
        deepfake_prob=0.9,
        speaker_sim=0.8, # Good match
        prosody_anomaly=0.7,
        context_score=0.1
    )
    assert score2 >= settings.MEDIUM_RISK_THRESHOLD
    
    # Scenario: Missing speaker verification
    score3 = scorer.calculate_raw_score(
        deepfake_prob=0.9,
        speaker_sim=None,
        prosody_anomaly=0.7,
        context_score=0.5
    )
    assert score3 > 0.5

def test_risk_levels():
    scorer = RiskScorer()
    assert scorer.get_risk_level(0.1) == "LOW"
    assert scorer.get_risk_level(0.4) == "MEDIUM"
    assert scorer.get_risk_level(0.7) == "HIGH"
    assert scorer.get_risk_level(0.9) == "CRITICAL"
