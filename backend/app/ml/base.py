from abc import ABC, abstractmethod
import numpy as np
from typing import Dict, Any

class DeepfakeDetector(ABC):
    @abstractmethod
    async def predict(self, audio: np.ndarray, sample_rate: int) -> float:
        """Return deepfake probability [0.0, 1.0]"""
        pass
    
    @abstractmethod
    def load(self):
        """Load model weights"""
        pass

class SpeakerVerifier(ABC):
    @abstractmethod
    async def extract_embedding(self, audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Extract speaker embedding"""
        pass

    @abstractmethod
    async def compare(self, current_embedding: np.ndarray, enrolled_embedding: np.ndarray) -> float:
        """Return similarity score [0.0, 1.0]"""
        pass

    @abstractmethod
    def load(self):
        pass

class ProsodyAnalyzer(ABC):
    @abstractmethod
    async def analyze(self, audio: np.ndarray, sample_rate: int) -> Dict[str, float]:
        """Return prosody features and anomaly score"""
        pass
