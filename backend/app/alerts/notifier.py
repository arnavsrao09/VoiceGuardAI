"""
Multi-Channel Alert Dispatcher Engine for VoiceGuardAI.

Dispatches real-time security alerts across:
1. **Real Email Notifications** (via SMTP with HTML formatting)
2. **Real SMS Alerts** (via Twilio REST API)
3. **Webhook Notifications** (HTTP POST payloads to registered enterprise endpoints)
4. **Database Audit Logging** (PostgreSQL `alerts` table)
"""

from __future__ import annotations

import asyncio
import email.mime.multipart
import email.mime.text
import smtplib
import uuid
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.db import crud
from app.db.database import AsyncSessionLocal


class AlertNotifier:
    """Async multi-channel alert dispatcher."""

    _registered_webhooks: list[str] = [
        # Default internal enterprise webhook listener (simulated/configurable)
        "http://localhost:8000/api/v1/webhooks/listener"
    ]

    @classmethod
    def register_webhook(cls, url: str):
        """Add a custom enterprise webhook endpoint."""
        if url not in cls._registered_webhooks:
            cls._registered_webhooks.append(url)

    @classmethod
    def get_registered_webhooks(cls) -> list[str]:
        return list(cls._registered_webhooks)

    @classmethod
    async def dispatch_alert(
        cls,
        session_id: str | uuid.UUID,
        severity: str,
        trigger_reason: str,
        risk_score: float,
        organization_id: uuid.UUID | None = None,
        caller_id: str | None = None,
        context_data: dict | None = None,
    ) -> dict:
        """Dispatch multi-channel security alert asynchronously."""
        if isinstance(session_id, str):
            try:
                session_id = uuid.UUID(session_id)
            except ValueError:
                session_id = uuid.uuid4()

        # 1. Log alert into Database
        db_alert = None
        try:
            async with AsyncSessionLocal() as db:
                db_alert = await crud.create_alert(
                    db=db,
                    session_id=session_id,
                    severity=severity,
                    trigger_reason=trigger_reason,
                    risk_score=risk_score,
                    organization_id=organization_id,
                )
        except Exception as e:
            print(f"[NOTIFIER] DB alert log failed: {e}")

        payload = {
            "alert_id": str(db_alert.id) if db_alert else str(uuid.uuid4()),
            "session_id": str(session_id),
            "severity": severity,
            "trigger_reason": trigger_reason,
            "risk_score": round(risk_score, 4),
            "caller_id": caller_id or "Live Stream",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "context": context_data or {},
        }

        # 2. Fire Async Tasks for Email, SMS, and Webhooks
        results = await asyncio.gather(
            cls._send_email_alert(payload),
            cls._send_sms_alert(payload),
            cls._send_webhook_alerts(payload),
            return_exceptions=True,
        )

        email_status = results[0] if not isinstance(results[0], Exception) else False
        sms_status = results[1] if not isinstance(results[1], Exception) else False
        webhook_status = results[2] if not isinstance(results[2], Exception) else False

        return {
            "status": "dispatched",
            "payload": payload,
            "channels": {
                "email": email_status,
                "sms": sms_status,
                "webhook": webhook_status,
            },
        }

    # ------------------------------------------------------------------
    # 1. Real Email Alert via SMTP
    # ------------------------------------------------------------------
    @classmethod
    async def _send_email_alert(cls, payload: dict) -> bool:
        """Send HTML alert email via SMTP."""
        recipient = settings.alert_email_to or settings.smtp_user
        if not settings.smtp_host or not recipient or not settings.smtp_user:
            print("[NOTIFIER Email] SMTP not fully configured (SMTP_USER/ALERT_EMAIL_TO missing). Skipping email dispatch.")
            return False

        def _sync_send():
            try:
                msg = email.mime.multipart.MIMEMultipart("alternative")
                msg["Subject"] = f"🚨 VoiceGuardAI [{payload['severity']}] Voice Clone Threat Alert"
                msg["From"] = settings.alert_email_from
                msg["To"] = recipient

                text_body = (
                    f"VoiceGuardAI Threat Alert\n"
                    f"Severity: {payload['severity']}\n"
                    f"Risk Score: {payload['risk_score'] * 100:.1f}%\n"
                    f"Session ID: {payload['session_id']}\n"
                    f"Reason: {payload['trigger_reason']}\n"
                )

                html_body = f"""
                <html>
                <body style="font-family: 'Segoe UI', Arial, sans-serif; background-color: #0c0d14; color: #e2e4eb; padding: 24px;">
                    <div style="max-width: 580px; margin: 0 auto; background: #141622; border: 1px solid #2a2d3d; border-radius: 12px; padding: 32px;">
                        <h2 style="color: #ef4444; margin-top: 0; display: flex; align-items: center;">
                            🚨 VOICE CLONE IMPERSONATION ALERT
                        </h2>
                        <div style="background: rgba(239,68,68,0.1); border-left: 4px solid #ef4444; padding: 12px 16px; margin-bottom: 20px;">
                            <strong>Severity Level:</strong> <span style="color: #ef4444;">{payload['severity']}</span><br>
                            <strong>Impersonation Risk Score:</strong> <span style="font-size: 18px; font-weight: bold; color: #ef4444;">{payload['risk_score'] * 100:.1f}%</span>
                        </div>
                        <p><strong>Caller ID:</strong> {payload['caller_id']}</p>
                        <p><strong>Session UUID:</strong> <code style="background: #1e2130; padding: 2px 6px; border-radius: 4px;">{payload['session_id']}</code></p>
                        <p><strong>Forensic Detection Reason:</strong></p>
                        <p style="background: #1a1c2a; padding: 12px; border-radius: 6px; color: #f87171;">{payload['trigger_reason']}</p>
                        
                        <hr style="border: 0; border-top: 1px solid #2a2d3d; margin: 24px 0;">
                        <p style="font-size: 12px; color: #8a8fa4;">
                            Sent automatically by <strong>VoiceGuardAI Real-Time Threat Engine</strong>.<br>
                            Recommended Action: Freeze high-value transactions & trigger MFA challenge.
                        </p>
                    </div>
                </body>
                </html>
                """

                msg.attach(email.mime.text.MIMEText(text_body, "plain"))
                msg.attach(email.mime.text.MIMEText(html_body, "html"))

                with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as server:
                    server.starttls()
                    if settings.smtp_user and settings.smtp_password:
                        server.login(settings.smtp_user, settings.smtp_password)
                    server.sendmail(settings.alert_email_from, [recipient], msg.as_string())

                print(f"[NOTIFIER Email] Successfully dispatched email alert to {recipient}")
                return True
            except Exception as e:
                print(f"[NOTIFIER Email Error] Failed to send email alert: {e}")
                return False

        return await asyncio.to_thread(_sync_send)

    # ------------------------------------------------------------------
    # 2. Real SMS Alert via Twilio REST API
    # ------------------------------------------------------------------
    @classmethod
    async def _send_sms_alert(cls, payload: dict) -> bool:
        """Send SMS alert via Twilio REST API."""
        if not settings.twilio_account_sid or not settings.twilio_auth_token or not settings.alert_sms_to:
            print("[NOTIFIER SMS] Twilio credentials or ALERT_SMS_TO not configured. Skipping SMS dispatch.")
            return False

        url = f"https://api.twilio.com/2010-04-01/Accounts/{settings.twilio_account_sid}/Messages.json"
        sms_text = (
            f"🚨 VOICEGUARD ALERT [{payload['severity']}]\n"
            f"AI Voice Clone Risk: {payload['risk_score'] * 100:.1f}%\n"
            f"Caller: {payload['caller_id']}\n"
            f"Session: {payload['session_id'][:8]}...\n"
            f"Action: Hold Transaction Immediately!"
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    url,
                    data={
                        "From": settings.twilio_phone_number,
                        "To": settings.alert_sms_to,
                        "Body": sms_text,
                    },
                    auth=(settings.twilio_account_sid, settings.twilio_auth_token),
                )
                if resp.status_code in (200, 201):
                    print(f"[NOTIFIER SMS] Successfully dispatched Twilio SMS to {settings.alert_sms_to}")
                    return True
                else:
                    print(f"[NOTIFIER SMS Error] Twilio responded with status {resp.status_code}: {resp.text}")
                    return False
        except Exception as e:
            print(f"[NOTIFIER SMS Error] Failed to dispatch Twilio SMS: {e}")
            return False

    # ------------------------------------------------------------------
    # 3. Webhook Delivery
    # ------------------------------------------------------------------
    @classmethod
    async def _send_webhook_alerts(cls, payload: dict) -> bool:
        """Send JSON webhook payloads to registered enterprise endpoints."""
        if not cls._registered_webhooks:
            return False

        success_count = 0
        async with httpx.AsyncClient(timeout=5.0) as client:
            for url in cls._registered_webhooks:
                try:
                    resp = await client.post(url, json=payload)
                    if resp.status_code < 400:
                        success_count += 1
                        print(f"[NOTIFIER Webhook] Delivered alert payload to {url}")
                except Exception as e:
                    print(f"[NOTIFIER Webhook Error] Delivery failed for {url}: {e}")

        return success_count > 0
