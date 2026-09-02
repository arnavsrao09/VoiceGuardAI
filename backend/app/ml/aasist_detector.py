import numpy as np
import logging
import asyncio
import torch
import os

from app.core.config import settings
from app.ml.base import DeepfakeDetector

logger = logging.getLogger(__name__)

class AASISTDetector(DeepfakeDetector):
    def __init__(self):
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.is_loaded = False
        self.model = None
        self.window_samples = settings.AASIST_WINDOW_SAMPLES

    def load(self):
        if self.is_loaded:
            return
            
        if settings.MOCK_ML:
            logger.info("MOCK_ML is enabled. Using Mock AASIST Detector.")
            self.is_loaded = True
            return

        model_path = os.path.join(settings.AASIST_MODEL_PATH, "aasist.pth")
        
        try:
            # Here we would normally import the AASIST model definition from a local file
            # For this academic/hackathon prototype, we assume a TorchScript model or
            # onnxruntime wrapper. We'll attempt to load via torch.jit if available,
            # otherwise we fallback gracefully so the app still runs.
            if os.path.exists(model_path):
                try:
                    self.model = torch.jit.load(model_path, map_location=self.device)
                    self.model.eval()
                    self.is_loaded = True
                    logger.info("AASIST model loaded successfully.")
                except Exception as jit_err:
                    logger.error(f"Failed to load AASIST as TorchScript: {jit_err}. Fallback to mock.")
                    self.is_loaded = False
            else:
                logger.warning(f"AASIST model not found at {model_path}. Using mock mode.")
                self.is_loaded = False
                
        except Exception as e:
            logger.error(f"Error loading AASIST model: {e}")
            self.is_loaded = False

    async def predict(self, audio: np.ndarray, sample_rate: int) -> float:
        if not self.is_loaded or settings.MOCK_ML or self.model is None:
            # Mock implementation: 
            # Simple heuristic: if audio has very low energy, it's a test case, return low risk
            # Or just return a random score based on audio sum to be deterministic
            score = float(np.abs(audio).mean() * 10)
            return min(max(score, 0.0), 1.0)
            
        return await asyncio.to_thread(self._predict_sync, audio)

    def _predict_sync(self, audio: np.ndarray) -> float:
        try:
            # Ensure proper length
            if len(audio) < self.window_samples:
                pad_width = self.window_samples - len(audio)
                audio = np.pad(audio, (0, pad_width), mode='constant')
            elif len(audio) > self.window_samples:
                # Deterministic windowing strategy (e.g. center)
                start = (len(audio) - self.window_samples) // 2
                audio = audio[start:start + self.window_samples]

            tensor_audio = torch.FloatTensor(audio).unsqueeze(0).to(self.device) # Batch size 1
            
            with torch.no_grad():
                # The official AASIST outputs logits. 
                # Output shape typically: [batch, 2] (bona-fide, spoof)
                logits = self.model(tensor_audio)
                # Ensure output is softmaxed and we return spoof probability
                probs = torch.softmax(logits, dim=1)
                spoof_prob = probs[0, 1].item()
                
            return float(spoof_prob)
        except Exception as e:
            logger.error(f"AASIST inference error: {e}")
            return 0.5 # Return uncertain score on failure
