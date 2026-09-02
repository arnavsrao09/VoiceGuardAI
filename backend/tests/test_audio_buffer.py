import pytest
import numpy as np
from app.audio.buffer import AudioRingBuffer

def test_audio_buffer_add_and_get():
    buffer = AudioRingBuffer(window_samples=1000)
    
    # Add 500 samples
    chunk1 = np.ones(500, dtype=np.float32)
    buffer.add_audio(chunk1)
    
    # Not enough samples yet
    assert buffer.get_analysis_window() is None
    
    # Add 600 more samples (total 1100)
    chunk2 = np.ones(600, dtype=np.float32)
    buffer.add_audio(chunk2)
    
    window = buffer.get_analysis_window()
    assert window is not None
    assert len(window) == 1000
    
def test_audio_buffer_padded():
    buffer = AudioRingBuffer(window_samples=1000)
    chunk = np.ones(500, dtype=np.float32)
    buffer.add_audio(chunk)
    
    padded = buffer.get_all_padded()
    assert len(padded) == 1000
    assert np.all(padded[500:] == 0.0)
