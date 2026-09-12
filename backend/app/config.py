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
    
    # Multi-Channel Alerting Settings (Email & SMS)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    alert_email_from: str = "alerts@voiceguard.ai"
    alert_email_to: str = ""

    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_phone_number: str = ""
    alert_sms_to: str = ""

    # Privacy & Retention Defaults
    default_session_ttl_days: int = 30
    default_telemetry_ttl_days: int = 30
    default_embedding_ttl_days: int = 90
    default_alert_ttl_days: int = 90
    default_inference_mode: str = "EDGE"
    privacy_purge_interval_hours: int = 6

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
