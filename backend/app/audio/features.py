# Audio feature extraction utilities
import numpy as np
import librosa


def extract_mfcc(audio: np.ndarray, sample_rate: int = 16000, n_mfcc: int = 13) -> np.ndarray:
    """Extract MFCC features from audio."""
    mfccs = librosa.feature.mfcc(y=audio, sr=sample_rate, n_mfcc=n_mfcc)
    return mfccs


def extract_spectral_features(audio: np.ndarray, sample_rate: int = 16000) -> dict:
    """Extract spectral features for analysis."""
    spectral_centroid = librosa.feature.spectral_centroid(y=audio, sr=sample_rate)
    spectral_flatness = librosa.feature.spectral_flatness(y=audio)
    spectral_rolloff = librosa.feature.spectral_rolloff(y=audio, sr=sample_rate)

    return {
        "spectral_centroid_mean": float(np.mean(spectral_centroid)),
        "spectral_flatness_mean": float(np.mean(spectral_flatness)),
        "spectral_rolloff_mean": float(np.mean(spectral_rolloff)),
    }
