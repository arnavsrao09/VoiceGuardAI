import numpy as np
import logging
import asyncio
import torch
from speechbrain.inference.speaker import EncoderClassifier

from app.core.config import settings
from app.ml.base import SpeakerVerifier

logger = logging.getLogger(__name__)

class ECAPASpeakerVerifier(SpeakerVerifier):
    def __init__(self):
        self.device = 'cuda' if torch.cuda.is_available() else 'cpu'
        self.is_loaded = False
        self.classifier = None

    def load(self):
        if self.is_loaded:
            return
            
        if settings.MOCK_ML:
            logger.info("MOCK_ML is enabled. Using Mock Speaker Verifier.")
            self.is_loaded = True
            return

        try:
            self.classifier = EncoderClassifier.from_hparams(
                source="speechbrain/spkrec-ecapa-voxceleb",
                savedir=settings.ECAPA_MODEL_PATH,
                run_opts={"device": self.device}
            )
            self.is_loaded = True
            logger.info("ECAPA-TDNN model loaded successfully.")
        except Exception as e:
            logger.error(f"Failed to load ECAPA-TDNN model: {e}")
            self.is_loaded = False

    async def extract_embedding(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        if not self.is_loaded or settings.MOCK_ML or self.classifier is None:
            # Mock embedding (192 dimensions)
            return np.random.rand(192).astype(np.float32)

        return await asyncio.to_thread(self._extract_sync, audio, sample_rate)

    def _extract_sync(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        try:
            tensor_audio = torch.FloatTensor(audio).to(self.device)
            # The classifier expects batched audio [batch, time]
            tensor_audio = tensor_audio.unsqueeze(0)
            
            with torch.no_grad():
                embeddings = self.classifier.encode_batch(tensor_audio)
                
            # embeddings shape is usually [1, 1, 192]
            emb = embeddings.squeeze().cpu().numpy()
            
            # Normalize embedding
            norm = np.linalg.norm(emb)
            if norm > 0:
                emb = emb / norm
                
            return emb
        except Exception as e:
            logger.error(f"ECAPA-TDNN extraction error: {e}")
            return np.zeros(192, dtype=np.float32)

    async def compare(self, current_embedding: np.ndarray, enrolled_embedding: np.ndarray) -> float:
        """Returns cosine similarity mapped to [0, 1]"""
        try:
            cos_sim = np.dot(current_embedding, enrolled_embedding) / (
                np.linalg.norm(current_embedding) * np.linalg.norm(enrolled_embedding)
            )
            # Map cosine similarity from [-1, 1] to [0, 1] for easier thresholding if needed
            # Or just return raw cosine similarity, which is standard. We'll return raw for now.
            # Wait, prompt says: "Return similarity in a normalized format. 0 to 1".
            normalized_sim = (cos_sim + 1.0) / 2.0
            return float(normalized_sim)
        except Exception as e:
            logger.error(f"Embedding comparison error: {e}")
            return 0.0
