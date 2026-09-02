from abc import ABC, abstractmethod
import logging

logger = logging.getLogger(__name__)

class AlertNotifier(ABC):
    @abstractmethod
    async def send_alert(self, alert_data: dict):
        pass

class ConsoleNotifier(AlertNotifier):
    async def send_alert(self, alert_data: dict):
        logger.warning(f"🚨 CRITICAL ALERT TRIGGERED: {alert_data.get('trigger_reason')} (Score: {alert_data.get('risk_score')})")

class EmailNotifier(AlertNotifier):
    async def send_alert(self, alert_data: dict):
        # Placeholder for SendGrid / SMTP integration
        logger.info("Email notification would be sent here.")

class SMSNotifier(AlertNotifier):
    async def send_alert(self, alert_data: dict):
        # Placeholder for Twilio integration
        logger.info("SMS notification would be sent here.")
