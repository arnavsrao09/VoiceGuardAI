import logging
from typing import Dict, Any

from app.ml.aasist_detector import AASISTDetector
from app.ml.speaker_verifier import ECAPASpeakerVerifier
from app.ml.prosody_analyzer import PyWorldProsodyAnalyzer
from app.ml.context_analyzer import ContextAnalyzer
from app.ml.risk_scorer import RiskScorer
from app.audio.vad import vad_service
from app.core.config import settings

logger = logging.getLogger(__name__)

class ModelManager:
    def __init__(self):
        self.aasist = AASISTDetector()
        self.ecapa = ECAPASpeakerVerifier()
        self.prosody = PyWorldProsodyAnalyzer()
        self.context = ContextAnalyzer()
        self.risk_scorer = RiskScorer()
        
    def initialize(self):
        """Load all models at startup"""
        logger.info("Initializing ML models...")
        self.aasist.load()
        self.ecapa.load()
        vad_service.load()
        logger.info("Model initialization complete.")

    def get_status(self) -> Dict[str, str]:
        return {
            "aasist": "loaded" if self.aasist.is_loaded else "mock/unavailable",
            "ecapa": "loaded" if self.ecapa.is_loaded else "mock/unavailable",
            "vad": "loaded" if vad_service.is_loaded else "mock/unavailable"
        }
        
    def get_device(self) -> str:
        # Since vad, aasist, ecapa use the same logic for device selection:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"

model_manager = ModelManager()
