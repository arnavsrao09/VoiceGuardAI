from fastapi import APIRouter
from app.core.config import settings
from app.api.schemas.config import ThresholdConfigUpdate

router = APIRouter()

@router.get("/thresholds")
async def get_thresholds():
    return {
        "vad_threshold": settings.VAD_THRESHOLD,
        "deepfake_weight": settings.DEEPFAKE_WEIGHT,
        "speaker_weight": settings.SPEAKER_WEIGHT,
        "prosody_weight": settings.PROSODY_WEIGHT,
        "context_weight": settings.CONTEXT_WEIGHT,
        "ema_alpha": settings.EMA_ALPHA,
        "low_risk_threshold": settings.LOW_RISK_THRESHOLD,
        "medium_risk_threshold": settings.MEDIUM_RISK_THRESHOLD,
        "high_risk_threshold": settings.HIGH_RISK_THRESHOLD,
        "speaker_similarity_threshold": settings.SPEAKER_SIMILARITY_THRESHOLD
    }

@router.put("/thresholds")
async def update_thresholds(config: ThresholdConfigUpdate):
    # In a real app, we'd save these to DB or Redis so they persist.
    # For now, we update the in-memory settings (won't persist across restarts).
    settings.VAD_THRESHOLD = config.vad_threshold
    settings.DEEPFAKE_WEIGHT = config.deepfake_weight
    settings.SPEAKER_WEIGHT = config.speaker_weight
    settings.PROSODY_WEIGHT = config.prosody_weight
    settings.CONTEXT_WEIGHT = config.context_weight
    settings.EMA_ALPHA = config.ema_alpha
    settings.LOW_RISK_THRESHOLD = config.low_risk_threshold
    settings.MEDIUM_RISK_THRESHOLD = config.medium_risk_threshold
    settings.HIGH_RISK_THRESHOLD = config.high_risk_threshold
    settings.SPEAKER_SIMILARITY_THRESHOLD = config.speaker_similarity_threshold
    
    # Also update risk scorer instance
    from app.ml.model_manager import model_manager
    model_manager.risk_scorer.deepfake_weight = config.deepfake_weight
    model_manager.risk_scorer.speaker_weight = config.speaker_weight
    model_manager.risk_scorer.prosody_weight = config.prosody_weight
    model_manager.risk_scorer.context_weight = config.context_weight
    model_manager.risk_scorer.ema_alpha = config.ema_alpha
    
    return {"message": "Thresholds updated"}

@router.get("/analysis")
async def get_analysis_config():
    return {
        "audio_sample_rate": settings.AUDIO_SAMPLE_RATE,
        "aasist_window_samples": settings.AASIST_WINDOW_SAMPLES,
        "aasist_hop_ms": settings.AASIST_HOP_MS
    }
