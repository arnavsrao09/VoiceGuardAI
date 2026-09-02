import numpy as np
import threading
from typing import Optional, Tuple

class AudioRingBuffer:
    def __init__(self, sample_rate: int = 16000, window_samples: int = 64600, hop_samples: int = 4000):
        """
        Ring buffer for storing audio chunks and extracting analysis windows.
        window_samples: 64600 (~4.04s at 16kHz)
        hop_samples: 4000 (250ms at 16kHz)
        """
        self.sample_rate = sample_rate
        self.window_samples = window_samples
        self.hop_samples = hop_samples
        
        # Internal buffer can be larger to hold more history, but we'll use a dynamic array for simplicity
        # or a fixed size large enough for our needs.
        # Let's use a dynamic array since the session might end quickly or run long, but we only KEEP the latest window.
        self.buffer = np.array([], dtype=np.float32)
        self.lock = threading.Lock()
        
        # Track how many samples we've processed to know when to emit the next window
        self.processed_samples = 0
        
    def add_audio(self, audio_chunk: np.ndarray):
        """Add new audio chunk to the buffer"""
        with self.lock:
            self.buffer = np.concatenate([self.buffer, audio_chunk])
            # To avoid memory leak, only keep what's necessary
            # We need at most (window_samples + some margin)
            max_size = self.window_samples * 2
            if len(self.buffer) > max_size:
                self.buffer = self.buffer[-max_size:]
                
    def get_analysis_window(self) -> Optional[np.ndarray]:
        """
        Returns the latest window_samples if enough audio is present and hop condition met.
        If available audio < window_samples, we might pad it if explicitly requested (in ML wrapper), 
        but buffer returns None until it has enough or session ends.
        """
        with self.lock:
            if len(self.buffer) < self.window_samples:
                return None
                
            # If we have enough for a window
            latest_window = self.buffer[-self.window_samples:]
            
            # Here we could implement strict hop logic, but for real-time:
            # "Analyze every 250ms once enough buffered audio exists."
            # The caller will manage the 250ms hop trigger or we can track it.
            # We'll just return the latest window whenever called.
            
            return np.copy(latest_window)
            
    def get_all_padded(self) -> np.ndarray:
        """Get all audio, padded or truncated to window_samples. Used for short file uploads."""
        with self.lock:
            if len(self.buffer) == 0:
                return np.zeros(self.window_samples, dtype=np.float32)
                
            if len(self.buffer) >= self.window_samples:
                return np.copy(self.buffer[-self.window_samples:])
                
            # Pad with zeros if shorter
            pad_width = self.window_samples - len(self.buffer)
            return np.pad(self.buffer, (0, pad_width), mode='constant')

    def clear(self):
        with self.lock:
            self.buffer = np.array([], dtype=np.float32)
            self.processed_samples = 0
