import torch
import numpy as np
import logging
import asyncio

from app.core.config import settings

logger = logging.getLogger(__name__)

class VADService:
    def __init__(self):
        self.model = None
        self.get_speech_timestamps = None
        self.threshold = settings.VAD_THRESHOLD
        self.sample_rate = settings.AUDIO_SAMPLE_RATE
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.is_loaded = False
        
    def load(self):
        """Lazy load Silero VAD model"""
        if self.is_loaded:
            return
            
        try:
            # torch.hub.load might fail without internet if not cached
            self.model, utils = torch.hub.load(
                repo_or_dir='snakers4/silero-vad',
                model='silero_vad',
                force_reload=False,
                trust_repo=True
            )
            self.model = self.model.to(self.device)
            (self.get_speech_timestamps, _, read_audio, *_) = utils
            self.is_loaded = True
            logger.info("Silero VAD model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load Silero VAD model: {e}")
            self.is_loaded = False
            
    async def is_speech(self, audio_chunk: np.ndarray) -> bool:
        """Determine if a chunk contains speech"""
        if not self.is_loaded:
            # Fallback if model could not load: just assume speech so pipeline doesn't break
            return True
            
        return await asyncio.to_thread(self._is_speech_sync, audio_chunk)
            
    def _is_speech_sync(self, audio_chunk: np.ndarray) -> bool:
        try:
            # Convert to torch tensor
            tensor_audio = torch.FloatTensor(audio_chunk).to(self.device)
            
            # get_speech_timestamps requires batched or 1d tensor, silero expects 16k
            speech_timestamps = self.get_speech_timestamps(
                tensor_audio, 
                self.model, 
                sampling_rate=self.sample_rate,
                threshold=self.threshold
            )
            
            return len(speech_timestamps) > 0
        except Exception as e:
            logger.error(f"VAD inference error: {e}")
            return True # Fallback

vad_service = VADService()
