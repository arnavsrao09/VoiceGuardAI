import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

class PrivacyAnonymizer:
    @staticmethod
    def should_retain_audio() -> bool:
        """
        Check if system is configured to retain raw audio.
        By default, this is False for privacy reasons.
        """
        return settings.RAW_AUDIO_RETENTION
        
    @staticmethod
    def sanitize_log_data(data: dict) -> dict:
        """
        Remove any raw PII or raw audio bytes from log dictionaries.
        """
        sanitized = data.copy()
        if "audio_bytes" in sanitized:
            sanitized["audio_bytes"] = "<REDACTED>"
        if "phone_number" in sanitized:
            # Mask phone number, keep last 4 digits
            phone = str(sanitized["phone_number"])
            if len(phone) >= 4:
                sanitized["phone_number"] = f"***-***-{phone[-4:]}"
        return sanitized
