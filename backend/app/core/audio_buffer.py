import numpy as np
from collections import deque
import threading

class CircularAudioBuffer:
    def __init__(self, window_size_sec: float = 2.0, hop_size_sec: float = 0.25, sample_rate: int = 16000):
        self.sample_rate = sample_rate
        self.window_size_samples = int(window_size_sec * sample_rate)
        self.hop_size_samples = int(hop_size_sec * sample_rate)
        
        # Buffer to hold samples
        self.buffer = deque(maxlen=self.window_size_samples)
        self.lock = threading.Lock()
        
        # Number of samples since last feature extraction
        self.samples_since_last_hop = 0

    def add_frames(self, frames: np.ndarray):
        with self.lock:
            # Flatten to 1D and add to buffer
            frames_flat = frames.flatten()
            self.buffer.extend(frames_flat)
            self.samples_since_last_hop += len(frames_flat)

    def is_ready_for_inference(self) -> bool:
        with self.lock:
            # Ready if buffer is full and we've advanced by at least hop_size
            return (len(self.buffer) == self.window_size_samples and 
                    self.samples_since_last_hop >= self.hop_size_samples)

    def get_window(self) -> np.ndarray:
        with self.lock:
            if len(self.buffer) < self.window_size_samples:
                return np.zeros(0)
            
            # Reset hop counter
            self.samples_since_last_hop = 0
            
            # Return current window as numpy array
            return np.array(self.buffer, dtype=np.float32)

    def clear(self):
        with self.lock:
            self.buffer.clear()
            self.samples_since_last_hop = 0


class VADSpeechAccumulator:
    """Accumulate VAD-filtered speech for speaker embeddings (1–3 s windows).

    Live WebSocket frames are ~256 ms. ECAPA verification waits until enough
    speech has been collected, then refreshes at a 1 s speech hop so
    ``speaker_verified`` is not decided on every frame.
    """

    def __init__(
        self,
        min_sec: float = 1.5,
        max_sec: float = 3.0,
        hop_sec: float = 1.0,
        sample_rate: int = 16000,
    ):
        self.sample_rate = sample_rate
        self.min_samples = int(min_sec * sample_rate)
        self.max_samples = int(max_sec * sample_rate)
        self.hop_samples = int(hop_sec * sample_rate)
        self.buffer = deque(maxlen=self.max_samples)
        self.samples_since_emit = 0
        self.lock = threading.Lock()

    def add_frames(self, frames: np.ndarray):
        with self.lock:
            flat = frames.flatten()
            self.buffer.extend(flat)
            self.samples_since_emit += len(flat)

    def ready_for_embed(self) -> bool:
        with self.lock:
            if len(self.buffer) < self.min_samples:
                return False
            return self.samples_since_emit >= self.hop_samples

    def get_window(self) -> np.ndarray:
        with self.lock:
            self.samples_since_emit = 0
            if not self.buffer:
                return np.zeros(0, dtype=np.float32)
            return np.array(self.buffer, dtype=np.float32)

    def clear(self):
        with self.lock:
            self.buffer.clear()
            self.samples_since_emit = 0

