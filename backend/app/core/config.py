from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "VoiceGuardAI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    API_PREFIX: str = "/api/v1"
    
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voiceguardai"
    REDIS_URL: str = "redis://localhost:6379/0"
    
    AUDIO_SAMPLE_RATE: int = 16000
    AUDIO_CHANNELS: int = 1
    
    AASIST_WINDOW_SAMPLES: int = 64600
    AASIST_HOP_MS: int = 250
    
    VAD_THRESHOLD: float = 0.5
    
    DEEPFAKE_WEIGHT: float = 0.45
    SPEAKER_WEIGHT: float = 0.25
    PROSODY_WEIGHT: float = 0.15
    CONTEXT_WEIGHT: float = 0.15
    
    EMA_ALPHA: float = 0.3
    
    LOW_RISK_THRESHOLD: float = 0.30
    MEDIUM_RISK_THRESHOLD: float = 0.60
    HIGH_RISK_THRESHOLD: float = 0.80
    
    SPEAKER_SIMILARITY_THRESHOLD: float = 0.75
    
    RAW_AUDIO_RETENTION: bool = False
    TELEMETRY_RETENTION_DAYS: int = 90
    
    AASIST_MODEL_PATH: str = "models/aasist"
    ECAPA_MODEL_PATH: str = "models/ecapa"
    
    MOCK_ML: bool = False

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

settings = Settings()
