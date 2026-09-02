import numpy as np
import librosa
import io
import soundfile as sf

def preprocess_audio(audio_data: bytes, target_sample_rate: int = 16000) -> np.ndarray:
    """
    Preprocess audio from bytes (WAV, MP3, PCM) into a 1D float32 numpy array
    at the target sample rate.
    """
    try:
        # Load audio from bytes using librosa which uses soundfile/audioread under the hood
        y, sr = sf.read(io.BytesIO(audio_data))
        
        # Convert to float32 if not already
        if y.dtype != np.float32:
            y = y.astype(np.float32)

        # Normalize to [-1.0, 1.0] if it's integer PCM
        if np.max(np.abs(y)) > 1.0:
            y = y / np.max(np.abs(y))

        # Convert to mono if stereo
        if len(y.shape) > 1 and y.shape[1] > 1:
            y = librosa.to_mono(y.T)
        elif len(y.shape) > 1:
            y = y.squeeze()

        # Resample if needed
        if sr != target_sample_rate:
            y = librosa.resample(y, orig_sr=sr, target_sr=target_sample_rate)

        # Clipping protection
        y = np.clip(y, -1.0, 1.0)
        
        return y
    except Exception as e:
        raise ValueError(f"Failed to preprocess audio: {e}")

def preprocess_pcm_chunk(pcm_bytes: bytes, original_sample_rate: int = 16000, target_sample_rate: int = 16000) -> np.ndarray:
    """
    Preprocess raw 16-bit PCM chunk from WebSocket
    """
    # Convert bytes to int16 numpy array
    audio_int16 = np.frombuffer(pcm_bytes, dtype=np.int16)
    
    # Convert to float32 in [-1, 1]
    y = audio_int16.astype(np.float32) / 32768.0
    
    # Resample if needed
    if original_sample_rate != target_sample_rate:
        y = librosa.resample(y, orig_sr=original_sample_rate, target_sr=target_sample_rate)
        
    return np.clip(y, -1.0, 1.0)
