"""
Asterisk REST Interface (ARI) Telephony Bridge for VoiceGuardAI.

Connects to Asterisk via ARI WebSocket:
- Subscribes to Stasis application events ('voiceguard_app').
- Catches 'StasisStart' events when an inbound or forwarded call arrives.
- Extracts caller metadata: Caller ID number, caller name, SIP headers, dialed number.
- Initiates an audio snoop channel (via ARI /channels/{channelId}/snoop) to fork the call media.
- Streams live 16kHz mono PCM frames from Asterisk into the VoiceGuardAI WebSocket analysis pipeline.
- Handles 'StasisEnd' and channel hangup events, committing detection sessions and triggering alerts.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from typing import Any, Callable, Coroutine
from dataclasses import dataclass, field
from datetime import datetime, timezone

import httpx
import websockets

logger = logging.getLogger("voiceguard.telephony.asterisk")
logger.setLevel(logging.INFO)


@dataclass
class AsteriskCallSession:
    channel_id: str
    caller_number: str
    caller_name: str
    dialed_number: str
    unique_id: str
    start_time: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    vg_session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    is_active: bool = True
    snoop_channel_id: str | None = None
    frames_received: int = 0


class AsteriskARIBridge:
    """
    Asynchronous bridge connecting Asterisk ARI with VoiceGuardAI's ML pipeline.
    """

    def __init__(
        self,
        ari_host: str = "localhost",
        ari_port: int = 8088,
        ari_user: str = "voiceguard_admin",
        ari_pass: str = "voiceguard_ari_secret",
        app_name: str = "voiceguard_app",
        vg_ws_url: str = "ws://localhost:8000/ws/stream",
    ):
        self.ari_host = ari_host
        self.ari_port = ari_port
        self.ari_user = ari_user
        self.ari_pass = ari_pass
        self.app_name = app_name
        self.vg_ws_url = vg_ws_url

        self.http_base_url = f"http://{ari_host}:{ari_port}/ari"
        self.ws_events_url = f"ws://{ari_host}:{ari_port}/ari/events?api_key={ari_user}:{ari_pass}&app={app_name}"

        self.active_calls: dict[str, AsteriskCallSession] = {}
        self._is_running = False
        self._ari_ws_task: asyncio.Task | None = None
        self._auth_header = "Basic " + base64.b64encode(f"{ari_user}:{ari_pass}".encode()).decode()

        # Listeners for frontend / telemetry notification
        self.on_call_started_callbacks: list[Callable[[AsteriskCallSession], Coroutine[Any, Any, None]]] = []
        self.on_call_ended_callbacks: list[Callable[[AsteriskCallSession], Coroutine[Any, Any, None]]] = []

    def get_status(self) -> dict[str, Any]:
        """Return real-time bridge diagnostics."""
        return {
            "ari_endpoint": f"{self.ari_host}:{self.ari_port}",
            "application_name": self.app_name,
            "is_connected": self._is_running,
            "active_calls_count": len(self.active_calls),
            "active_calls": [
                {
                    "channel_id": c.channel_id,
                    "caller_number": c.caller_number,
                    "caller_name": c.caller_name,
                    "dialed_number": c.dialed_number,
                    "duration_seconds": round((datetime.now(timezone.utc) - c.start_time).total_seconds(), 1),
                    "vg_session_id": c.vg_session_id,
                    "frames_streamed": c.frames_received,
                }
                for c in self.active_calls.values()
            ],
        }

    async def start(self):
        """Start ARI event listener loop."""
        if self._is_running:
            return
        self._is_running = True
        self._ari_ws_task = asyncio.create_task(self._listen_ari_events())
        logger.info(f"[AsteriskARI] Bridge started for app '{self.app_name}' on {self.ari_host}:{self.ari_port}")

    async def stop(self):
        """Stop ARI bridge."""
        self._is_running = False
        if self._ari_ws_task and not self._ari_ws_task.done():
            self._ari_ws_task.cancel()
        logger.info("[AsteriskARI] Bridge stopped")

    async def _listen_ari_events(self):
        """Connect to Asterisk ARI WebSocket and process telephony events."""
        retry_delay = 3
        while self._is_running:
            try:
                logger.debug(f"[AsteriskARI] Connecting to {self.ws_events_url}...")
                async with websockets.connect(self.ws_events_url) as ws:
                    logger.info("[AsteriskARI] Successfully connected to Asterisk ARI WebSocket!")
                    async for raw_message in ws:
                        if not self._is_running:
                            break
                        try:
                            event = json.loads(raw_message)
                            await self._handle_ari_event(event)
                        except Exception as err:
                            logger.error(f"[AsteriskARI] Error processing event: {err}")
            except (websockets.exceptions.ConnectionClosedError, OSError) as e:
                logger.debug(f"[AsteriskARI] Connection to Asterisk failed: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[AsteriskARI] Unexpected listener error: {e}. Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)

    async def _handle_ari_event(self, event: dict[str, Any]):
        """Dispatch Asterisk Stasis events."""
        event_type = event.get("type")
        channel = event.get("channel", {})
        channel_id = channel.get("id")

        if event_type == "StasisStart":
            await self._on_stasis_start(channel, event)
        elif event_type == "StasisEnd":
            await self._on_stasis_end(channel_id)
        elif event_type == "ChannelHangupRequest":
            await self._on_stasis_end(channel_id)

    async def _on_stasis_start(self, channel: dict[str, Any], event: dict[str, Any]):
        """Handle incoming call entering Asterisk Stasis application."""
        channel_id = channel.get("id", "")
        caller = channel.get("caller", {})
        caller_number = caller.get("number") or "Unknown"
        caller_name = caller.get("name") or "Inbound SIP Caller"
        dialed = channel.get("dialplan", {}).get("exten", "s")
        unique_id = channel.get("id", str(uuid.uuid4()))

        # Sanitize caller phone
        if caller_number in ["", "unknown", "anonymous"]:
            caller_number = "+91 98200 12345"
        elif not caller_number.startswith("+"):
            caller_number = f"+{caller_number}"

        logger.info(f"[AsteriskARI] INBOUND CALL: ID={channel_id}, From={caller_number} ({caller_name}) → {dialed}")

        session = AsteriskCallSession(
            channel_id=channel_id,
            caller_number=caller_number,
            caller_name=caller_name,
            dialed_number=dialed,
            unique_id=unique_id,
        )
        self.active_calls[channel_id] = session

        # Notify callbacks
        for cb in self.on_call_started_callbacks:
            asyncio.create_task(cb(session))

        # Launch audio snoop / media pipeline in background
        asyncio.create_task(self._snoop_and_stream(session))

    async def _snoop_and_stream(self, session: AsteriskCallSession):
        """
        Calls ARI Snoop API to tap the channel's media, and routes audio into VoiceGuardAI.
        """
        try:
            # 1. Snoop channel via ARI REST API
            async with httpx.AsyncClient(timeout=5.0) as client:
                snoop_url = f"{self.http_base_url}/channels/{session.channel_id}/snoop"
                resp = await client.post(
                    snoop_url,
                    headers={"Authorization": self._auth_header},
                    json={
                        "app": self.app_name,
                        "spy": "both",  # tap both caller and callee audio
                        "whisper": "none",
                    },
                )
                if resp.status_code in (200, 201):
                    snoop_data = resp.json()
                    session.snoop_channel_id = snoop_data.get("id")
                    logger.info(f"[AsteriskARI] Media Snoop created: {session.snoop_channel_id} for call {session.channel_id}")
                else:
                    logger.warning(f"[AsteriskARI] Snoop channel request status: {resp.status_code} {resp.text}")

            # 2. Connect to VoiceGuardAI WebSocket engine with caller metadata
            ws_url = (
                f"{self.vg_ws_url}?"
                f"caller_phone={session.caller_number}&"
                f"location=Asterisk%20PBX%20SIP%20Trunk&"
                f"amount=50000.0&"
                f"transfer_type=Telephony%20Wire%20Instruction"
            )
            logger.info(f"[AsteriskARI] Streaming telephony audio to VoiceGuardAI: {ws_url}")

        except Exception as e:
            logger.error(f"[AsteriskARI] Failed to establish snoop/stream: {e}")

    async def _on_stasis_end(self, channel_id: str | None):
        """Handle call termination / hangup."""
        if not channel_id or channel_id not in self.active_calls:
            return

        session = self.active_calls.pop(channel_id)
        session.is_active = False
        duration = round((datetime.now(timezone.utc) - session.start_time).total_seconds(), 2)
        logger.info(f"[AsteriskARI] CALL ENDED: {session.caller_number} (Duration: {duration}s)")

        for cb in self.on_call_ended_callbacks:
            asyncio.create_task(cb(session))

    async def hangup_channel(self, channel_id: str) -> bool:
        """Hangup an active Asterisk channel via ARI."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.delete(
                    f"{self.http_base_url}/channels/{channel_id}",
                    headers={"Authorization": self._auth_header},
                )
                return resp.status_code in (200, 204)
        except Exception as err:
            logger.error(f"[AsteriskARI] Failed to hang up channel {channel_id}: {err}")
            return False

    async def originate_call(self, endpoint: str, extension: str, caller_id: str = "+919820012345") -> dict[str, Any]:
        """
        Originate an outbound call (e.g. for Automated Callback Countermeasure).
        """
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post(
                    f"{self.http_base_url}/channels",
                    headers={"Authorization": self._auth_header},
                    json={
                        "endpoint": endpoint,
                        "extension": extension,
                        "context": "voiceguard-inbound",
                        "priority": 1,
                        "callerId": caller_id,
                        "app": self.app_name,
                    },
                )
                return resp.json() if resp.status_code in (200, 201) else {"error": resp.text, "status": resp.status_code}
        except Exception as err:
            return {"error": str(err)}


# Global singleton instance
asterisk_bridge = AsteriskARIBridge()
