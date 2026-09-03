from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # App Settings
    app_name: str = "VoiceGuardAI Backend"
    debug: bool = False

    # ML Model Config (ONNX)
    aasist_onnx_path: str = "./app/ml/models/aasist.onnx"
    xlsr_onnx_path: str = "./app/ml/models/xlsr.onnx"
    ecapa_onnx_path: str = "./app/ml/models/ecapa.onnx"

    # Database Settings (PostgreSQL + pgvector)
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/voiceguard"

    # Redis Settings
    redis_url: str = "redis://localhost:6379/0"

    # Thresholds
    vad_threshold: float = 0.5
    deepfake_threshold: float = 0.6
    speaker_verification_threshold: float = 0.72
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
