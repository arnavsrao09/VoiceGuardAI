"""
Telephony & Asterisk PBX Call Simulator for VoiceGuardAI.

Allows complete end-to-end testing of:
1. Inbound Asterisk SIP calls with realistic caller phone numbers (+91, +1, etc.)
2. Automatic caller ID propagation into the live detection session
3. Streaming 16kHz mono PCM frames into the WebSocket inference engine
4. Intent extraction, acoustic radar, and automated countermeasure workflows
without requiring an active commercial SIP carrier account.
"""

from __future__ import annotations

import asyncio
import io
import math
import os
import struct
import uuid
import wave
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import websockets

from app.telephony.asterisk_bridge import asterisk_bridge, AsteriskCallSession


@dataclass
class ActiveSimulatedCall:
    call_id: str
    caller_phone: str
    caller_name: str
    destination: str
    amount: float
    transfer_type: str
    location: str
    start_time: datetime
    is_active: bool = True
    task: asyncio.Task | None = None
    frames_sent: int = 0
    risk_level: str = "LOW"
    risk_score: float = 0.0


class TelephonyCallSimulator:
    """
    Simulates inbound Asterisk calls and streams synthetic or real 16kHz PCM audio
    into VoiceGuardAI's WebSocket engine.
    """

    def __init__(self):
        self.active_simulations: dict[str, ActiveSimulatedCall] = {}

    def get_active_calls(self) -> list[dict[str, Any]]:
        """Return list of active simulated SIP calls."""
        now = datetime.now(timezone.utc)
        return [
            {
                "call_id": c.call_id,
                "caller_phone": c.caller_phone,
                "caller_name": c.caller_name,
                "destination": c.destination,
                "amount": c.amount,
                "transfer_type": c.transfer_type,
                "location": c.location,
                "duration_seconds": round((now - c.start_time).total_seconds(), 1),
                "frames_sent": c.frames_sent,
                "risk_level": c.risk_level,
                "risk_score": c.risk_score,
                "is_active": c.is_active,
            }
            for c in self.active_simulations.values()
            if c.is_active
        ]

    async def start_simulated_call(
        self,
        caller_phone: str = "+91 98200 12345",
        caller_name: str = "Rajesh Sharma (HDFC Wire)",
        destination: str = "5000",
        amount: float = 50000.0,
        transfer_type: str = "High-Value Wire Transfer",
        location: str = "Mumbai, MH (IN) - Asterisk SIP",
        audio_scenario: str = "deepfake_pressure",  # 'deepfake_pressure', 'genuine_user', or custom wav path
        duration_seconds: int = 15,
        vg_ws_url: str = "ws://localhost:8000/ws/stream",
    ) -> dict[str, Any]:
        """
        Simulate an incoming phone call routed through Asterisk PBX.
        Forks the media stream directly to the VoiceGuardAI WebSocket engine.
        """
        call_id = f"sip-call-{uuid.uuid4().hex[:8]}"

        sim_call = ActiveSimulatedCall(
            call_id=call_id,
            caller_phone=caller_phone,
            caller_name=caller_name,
            destination=destination,
            amount=amount,
            transfer_type=transfer_type,
            location=location,
            start_time=datetime.now(timezone.utc),
            is_active=True,
        )
        self.active_simulations[call_id] = sim_call

        # Also register into Asterisk ARI bridge session store so bridge reports it
        ast_session = AsteriskCallSession(
            channel_id=call_id,
            caller_number=caller_phone,
            caller_name=caller_name,
            dialed_number=destination,
            unique_id=call_id,
        )
        asterisk_bridge.active_calls[call_id] = ast_session

        # Notify Asterisk bridge listeners
        for cb in asterisk_bridge.on_call_started_callbacks:
            asyncio.create_task(cb(ast_session))

        # Launch background audio streaming task
        stream_task = asyncio.create_task(
            self._stream_simulated_audio(
                sim_call=sim_call,
                audio_scenario=audio_scenario,
                duration_seconds=duration_seconds,
                vg_ws_url=vg_ws_url,
            )
        )
        sim_call.task = stream_task

        return {
            "status": "call_connected",
            "call_id": call_id,
            "caller_phone": caller_phone,
            "caller_name": caller_name,
            "destination": destination,
            "amount": amount,
            "transfer_type": transfer_type,
            "location": location,
            "telephony_engine": "Asterisk PBX (ARI Stasis)",
            "message": f"Inbound SIP call connected from {caller_phone}. Media stream piped to VoiceGuardAI.",
        }

    async def hangup_call(self, call_id: str) -> bool:
        """Hang up a simulated call."""
        if call_id in self.active_simulations:
            call = self.active_simulations[call_id]
            call.is_active = False
            if call.task and not call.task.done():
                call.task.cancel()

            # Clean up from Asterisk bridge
            if call_id in asterisk_bridge.active_calls:
                session = asterisk_bridge.active_calls.pop(call_id)
                for cb in asterisk_bridge.on_call_ended_callbacks:
                    asyncio.create_task(cb(session))

            return True
        return False

    async def _stream_simulated_audio(
        self,
        sim_call: ActiveSimulatedCall,
        audio_scenario: str,
        duration_seconds: int,
        vg_ws_url: str,
    ):
        """
        Connects via WebSocket to /ws/stream with caller metadata and streams
        16kHz mono PCM frames (e.g. 500 samples per 31.25ms chunk).
        """
        query = (
            f"?caller_phone={sim_call.caller_phone}"
            f"&location={sim_call.location}"
            f"&amount={sim_call.amount}"
            f"&transfer_type={sim_call.transfer_type}"
        )
        full_ws_url = f"{vg_ws_url}{query}"

        try:
            # 1. Prepare PCM audio source
            audio_bytes = self._generate_scenario_audio(audio_scenario, duration_seconds)

            async with websockets.connect(full_ws_url) as ws:
                # Background listener for risk scores
                async def listen_risk():
                    try:
                        async for raw in ws:
                            import json
                            data = json.loads(raw)
                            if "score" in data:
                                sim_call.risk_score = data["score"]
                                sim_call.risk_level = data.get("level", "LOW")
                    except Exception:
                        pass

                listener_task = asyncio.create_task(listen_risk())

                # Chunk size: 500 samples (1000 bytes) = ~31.25 ms of 16kHz 16-bit mono PCM
                CHUNK_BYTES = 1000
                total_len = len(audio_bytes)
                offset = 0

                while offset < total_len and sim_call.is_active:
                    chunk = audio_bytes[offset : offset + CHUNK_BYTES]
                    if not chunk:
                        break
                    await ws.send(chunk)
                    sim_call.frames_sent += 1
                    offset += CHUNK_BYTES
                    await asyncio.sleep(0.03125)  # Real-time pacing

                listener_task.cancel()

        except asyncio.CancelledError:
            pass
        except Exception as err:
            print(f"[TelephonySim] Stream error on call {sim_call.call_id}: {err}")
        finally:
            sim_call.is_active = False
            if sim_call.call_id in asterisk_bridge.active_calls:
                session = asterisk_bridge.active_calls.pop(sim_call.call_id)
                for cb in asterisk_bridge.on_call_ended_callbacks:
                    asyncio.create_task(cb(session))

    def _generate_scenario_audio(self, scenario: str, duration_seconds: int) -> bytes:
        """
        Returns raw 16kHz 16-bit mono PCM bytes for the chosen scenario.
        If a WAV benchmark file exists, load it; otherwise generate synthetic speech-like harmonics.
        """
        # Check if benchmark wav files exist
        benchmark_paths = [
            f"frontend/public/samples/hindi_{scenario}.wav",
            f"frontend/public/samples/{scenario}.wav",
            "frontend/public/samples/hindi_deepfake_threat.wav",
        ]
        for path in benchmark_paths:
            if os.path.exists(path):
                try:
                    with wave.open(path, "rb") as wf:
                        if wf.getnchannels() == 1 and wf.getsampwidth() == 2 and wf.getframerate() == 16000:
                            return wf.readframes(wf.getnframes())
                except Exception:
                    pass

        # Generate synthetic 16kHz PCM audio
        sample_rate = 16000
        total_samples = sample_rate * duration_seconds
        buffer = io.BytesIO()

        # Generate speech-like harmonic carrier (pitch ~ 130Hz) with slight jitter
        base_f0 = 135.0 if scenario == "deepfake_pressure" else 150.0
        for i in range(total_samples):
            t = i / sample_rate
            # Pitch modulation
            f0 = base_f0 + 5.0 * math.sin(2 * math.pi * 3.0 * t)
            # Add vocoder artifacts if deepfake
            harmonic1 = math.sin(2 * math.pi * f0 * t)
            harmonic2 = 0.5 * math.sin(2 * math.pi * 2 * f0 * t)
            harmonic3 = 0.25 * math.sin(2 * math.pi * 3 * f0 * t)

            sample_val = (harmonic1 + harmonic2 + harmonic3) / 1.75
            # Add synthetic breathiness / envelope
            envelope = 0.5 * (1.0 + math.sin(2 * math.pi * 0.8 * t))
            sample_val *= envelope * 0.6

            int16_val = max(-32767, min(32767, int(sample_val * 32767)))
            buffer.write(struct.pack("<h", int16_val))

        return buffer.getvalue()


# Global singleton instance
call_simulator = TelephonyCallSimulator()
