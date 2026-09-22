"""
Lightweight SIP / VoIP Gateway Server for VoiceGuardAI.

Runs an async UDP SIP server on port 5060:
- Handles SIP REGISTER from softphones (Zoiper / Linphone on mobile or desktop).
- Sends 200 OK responses to register any account (e.g. 1001).
- Supports inbound calls from mobile Zoiper:
  - Answers with 180 Ringing and 200 OK with SDP
  - Starts an RTP receiver on a dynamic UDP port (10000-20000)
  - Decodes G.711 mu-law audio packets from the phone microphone in real-time
  - Upsamples to 16kHz mono PCM and pipes directly into VoiceGuardAI ML engine
  - Live updates the Asterisk / PBX dashboard card so the user sees their mobile call!
- Sends outbound SIP INFO with per-call risk telemetry (application/voiceguard+json)
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import socket
import random
import struct
from urllib.parse import urlencode
from datetime import datetime, timezone
from typing import Tuple, Any

import websockets

from app.logging_config import get_logger
logger = get_logger("sip")


def get_local_ip() -> str:
    """Discover primary LAN IPv4 address (e.g. 192.168.1.10)."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "192.168.1.10"


# Precomputed G.711 mu-law to linear 16-bit PCM lookup table
_ULAW_TABLE = []
for i in range(256):
    byte = ~i & 0xFF
    sign = byte & 0x80
    exponent = (byte >> 4) & 0x07
    mantissa = byte & 0x0F
    sample = ((mantissa << 3) + 0x84) << exponent
    sample -= 0x84
    if not sign:
        sample = -sample
    _ULAW_TABLE.append(sample)


# Precomputed G.711 A-law to linear 16-bit PCM lookup table
def _alaw2linear(a: int) -> int:
    a = a ^ 0x55
    t = (a & 0x0F) << 4
    seg = (a & 0x70) >> 4
    if seg == 0:
        t += 8
    elif seg == 1:
        t += 0x108
    else:
        t = (t + 0x108) << (seg - 1)
    return -t if (a & 0x80) == 0 else t

_ALAW_TABLE = [_alaw2linear(i) for i in range(256)]


class RTPMediaReceiver(asyncio.DatagramProtocol):
    """Listens on UDP port 10000 for RTP packets from mobile phone, batches and pipes to VoiceGuard."""

    def __init__(self, ws_url: str = "ws://127.0.0.1:8000/ws/stream?session_ref=zoiper-mobile-call", on_risk_update=None):
        self.ws_url = ws_url
        self.on_risk_update = on_risk_update
        self.ws = None
        self.transport = None
        self.packet_count = 0
        self.invalid_rtp_packets = 0
        self.unsupported_payload_packets = 0
        self.last_payload_type: int | None = None
        self.last_rms: float = 0.0
        self.last_peak: float = 0.0
        self.last_packet_at: datetime | None = None
        self.is_connected = False
        self.latest_result: dict[str, Any] | None = None
        self.last_score: float = 0.0
        self.last_speech_prob: float = 0.0
        self.drain_task: asyncio.Task | None = None
        self.sender_task: asyncio.Task | None = None
        self.audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self.pcm_buffer: bytearray = bytearray()

    @property
    def is_ws_open(self) -> bool:
        try:
            return self.ws is not None and getattr(self.ws, "state", None) is not None and self.ws.state.name == "OPEN"
        except Exception:
            return False

    async def connect_ws(self):
        try:
            self.ws = await websockets.connect(self.ws_url)
            self.is_connected = True
            logger.info("[RTP] Connected to VoiceGuard WebSocket pipeline.")
            logger.debug("RTP receiver connected to WebSocket pipeline.")
            self.drain_task = asyncio.create_task(self._drain_ws_results())
            self.sender_task = asyncio.create_task(self._sender_loop())
        except Exception as e:
            logger.warning(f"[RTP] Could not connect to internal WS: {e}")
            logger.warning("RTP receiver could not connect to WS: %s", e)

    async def _sender_loop(self):
        """Continuously drain batched PCM frames from queue and transmit over WebSocket."""
        while self.is_connected:
            try:
                chunk = await self.audio_queue.get()
                if self.is_ws_open:
                    await self.ws.send(chunk)
                self.audio_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.debug(f"[RTP] Send error: {e}")
                await asyncio.sleep(0.01)

    async def _drain_ws_results(self):
        """Continuously drain results from server so WebSocket TCP buffer never blocks."""
        try:
            while self.is_connected and self.is_ws_open:
                raw_msg = await self.ws.recv()
                if raw_msg:
                    try:
                        data = json.loads(raw_msg)
                        self.latest_result = data
                        self.last_score = float(data.get("score", 0.0))
                        self.last_speech_prob = float(data.get("speech_probability", 0.0))
                        if self.last_speech_prob > 0.3:
                            logger.debug("Speech detected — prob=%.2f score=%.2f", self.last_speech_prob, self.last_score)
                        
                        # Notify SIP server of risk update for outbound SIP INFO
                        if self.on_risk_update and "risk_level" in data:
                            self.on_risk_update(data)
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        logger.debug("RTP media receiver listening.")
        asyncio.create_task(self.connect_ws())

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        parsed = self._parse_rtp_payload(data)
        if parsed is None:
            self.invalid_rtp_packets += 1
            return
        payload_type, payload = parsed
        self.last_payload_type = payload_type
        self.last_packet_at = datetime.now(timezone.utc)

        # Decode mu-law or A-law to 16-bit linear PCM
        if payload_type == 0:  # PCMU 8kHz
            pcm8k = [_ULAW_TABLE[b] for b in payload]
        elif payload_type == 8:  # PCMA 8kHz (A-law)
            pcm8k = [_ALAW_TABLE[b] for b in payload]
        else:
            self.unsupported_payload_packets += 1
            return  # Ignore non-voice packets (e.g. DTMF)

        self.packet_count += 1

        # 2x linear interpolation upsampling from 8kHz to 16kHz
        pcm16k = []
        n = len(pcm8k)
        for i in range(n):
            s0 = pcm8k[i]
            s1 = pcm8k[i + 1] if i + 1 < n else s0
            pcm16k.extend([s0, (s0 + s1) // 2])
        pcm_bytes = struct.pack(f"<{len(pcm16k)}h", *pcm16k)
        if pcm16k:
            # Input-level telemetry proves that the RTP stream carries actual
            # microphone signal independently of the spoof classifier.
            self.last_peak = max(abs(sample) for sample in pcm16k) / 32768.0
            self.last_rms = (
                sum(sample * sample for sample in pcm16k) / len(pcm16k)
            ) ** 0.5 / 32768.0

        # Accumulate PCM frames into buffer and queue when >= 1600 samples (100ms = 3200 bytes)
        self.pcm_buffer.extend(pcm_bytes)
        CHUNK_SIZE = 3200  # 100ms @ 16kHz mono 16-bit PCM
        while len(self.pcm_buffer) >= CHUNK_SIZE:
            chunk = bytes(self.pcm_buffer[:CHUNK_SIZE])
            self.pcm_buffer = self.pcm_buffer[CHUNK_SIZE:]
            try:
                self.audio_queue.put_nowait(chunk)
            except asyncio.QueueFull:
                try:
                    self.audio_queue.get_nowait()
                except Exception:
                    pass
                try:
                    self.audio_queue.put_nowait(chunk)
                except Exception:
                    pass

    @staticmethod
    def _parse_rtp_payload(data: bytes) -> tuple[int, bytes] | None:
        """Return RTP payload while honoring CSRC, extension, and padding fields.

        The old fixed ``data[12:]`` offset treated optional RTP header bytes as
        G.711 samples. Zoiper and many mobile stacks use header extensions, so
        that produced plausible-looking but corrupted audio.
        """
        if len(data) < 12 or (data[0] >> 6) != 2:
            return None
        has_padding = bool(data[0] & 0x20)
        has_extension = bool(data[0] & 0x10)
        csrc_count = data[0] & 0x0F
        offset = 12 + csrc_count * 4
        if offset > len(data):
            return None
        if has_extension:
            if offset + 4 > len(data):
                return None
            extension_words = int.from_bytes(data[offset + 2 : offset + 4], "big")
            offset += 4 + extension_words * 4
            if offset > len(data):
                return None
        end = len(data)
        if has_padding:
            padding_size = data[-1]
            if padding_size == 0 or padding_size > end - offset:
                return None
            end -= padding_size
        if offset >= end:
            return None
        return data[1] & 0x7F, data[offset:end]

    def stop(self):
        self.is_connected = False
        if self.drain_task and not self.drain_task.done():
            self.drain_task.cancel()
        if self.sender_task and not self.sender_task.done():
            self.sender_task.cancel()
        if self.transport:
            try:
                self.transport.close()
            except Exception:
                pass
        if self.is_ws_open:
            try:
                asyncio.create_task(self.ws.close())
            except Exception:
                pass
        logger.debug("RTP receiver stopped. Packets processed: %d", self.packet_count)


class VoiceGuardSIPServer(asyncio.DatagramProtocol):
    def __init__(self, host: str = "0.0.0.0", port: int = 5060, local_ip: str | None = None):
        self.host = host
        self.port = port
        self.local_ip = local_ip or get_local_ip()
        self.transport: asyncio.DatagramTransport | None = None
        self.registered_clients: dict[str, Tuple[str, int]] = {}
        self.active_calls: dict[str, dict[str, Any]] = {}
        # Per-call RTP state (no global receiver/transport)
        self.rtp_receivers: dict[str, RTPMediaReceiver] = {}
        self.rtp_transports: dict[str, asyncio.DatagramTransport] = {}
        # Set by the dashboard before a call begins. Capture it per call so a
        # later UI selection cannot change an in-progress verification.
        self.expected_profiles: dict[str, str] = {}
        # Track last reported risk level per call for change-based SIP INFO
        self._last_risk_levels: dict[str, str] = {}

    def set_target_profile(self, profile_id: str | None, expected_caller_id: str = "_next_call") -> None:
        """Select the enrolled speaker profile for the next SIP call."""
        if profile_id:
            self.expected_profiles[expected_caller_id] = profile_id
        else:
            self.expected_profiles.pop(expected_caller_id, None)

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        logger.info("SIP server listening on %s:%d (LAN %s)", self.host, self.port, self.local_ip)

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        message = data.decode("utf-8", errors="ignore")
        first_line = message.split("\r\n")[0] if message else ""

        if first_line.startswith("REGISTER"):
            self.handle_register(message, addr)
        elif first_line.startswith("INVITE"):
            self.handle_invite(message, addr)
        elif first_line.startswith("OPTIONS"):
            self.handle_options(message, addr)
        elif first_line.startswith("ACK"):
            pass
        elif first_line.startswith("BYE"):
            self.handle_bye(message, addr)
        elif first_line.startswith("INFO"):
            asyncio.create_task(self.handle_info(message, addr))

    def handle_options(self, message: str, addr: Tuple[str, int]):
        """Respond to keep-alive pings from softphones."""
        call_id = self._extract_header(message, "Call-ID")
        cseq = self._extract_header(message, "CSeq")
        from_hdr = self._extract_header(message, "From")
        to_hdr = self._extract_header(message, "To")
        via = self._extract_header(message, "Via")

        response = (
            f"SIP/2.0 200 OK\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr};tag=vg_opt\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {cseq}\r\n"
            f"Allow: INVITE, ACK, CANCEL, OPTIONS, BYE, REGISTER, INFO\r\n"
            f"Server: VoiceGuardAI-SIP-PBX/1.0\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        if self.transport:
            self.transport.sendto(response.encode("utf-8"), addr)

    def handle_register(self, message: str, addr: Tuple[str, int]):
        """Respond with 200 OK to register Zoiper client immediately."""
        call_id = self._extract_header(message, "Call-ID")
        cseq = self._extract_header(message, "CSeq")
        from_hdr = self._extract_header(message, "From")
        to_hdr = self._extract_header(message, "To")
        via = self._extract_header(message, "Via")

        # Extract account/caller ID from To or From header (e.g. sip:1001@...)
        match = re.search(r"sip:([a-zA-Z0-9_\-+]+)@", to_hdr)
        account = match.group(1) if match else "1001"

        self.registered_clients[account] = addr
        logger.debug("REGISTER accepted for '%s' from %s:%d", account, addr[0], addr[1])

        response = (
            f"SIP/2.0 200 OK\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr};tag=vg_{cseq.split()[0] if cseq else '1'}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {cseq}\r\n"
            f"Contact: <sip:{account}@{addr[0]}:{addr[1]}>\r\n"
            f"Expires: 3600\r\n"
            f"Server: VoiceGuardAI-SIP-PBX/1.0\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        if self.transport:
            self.transport.sendto(response.encode("utf-8"), addr)

    def handle_invite(self, message: str, addr: Tuple[str, int]):
        """Answer call from Zoiper mobile and negotiate media stream."""
        call_id = self._extract_header(message, "Call-ID")
        cseq = self._extract_header(message, "CSeq")
        from_hdr = self._extract_header(message, "From")
        to_hdr = self._extract_header(message, "To")
        via = self._extract_header(message, "Via")

        caller_match = re.search(r"sip:([a-zA-Z0-9_\-+]+)@", from_hdr)
        caller_id = caller_match.group(1) if caller_match else "Zoiper-Mobile"
        profile_id = self.target_profile_id

        # Determine media IP: if client connected from loopback, use 127.0.0.1, else local IP
        media_ip = "127.0.0.1" if addr[0] in ("127.0.0.1", "localhost") else self.local_ip

    def handle_invite(self, message: str, addr: Tuple[str, int]):
        # Schedule the invite processing so we can await actual port binding
        asyncio.create_task(self._process_invite(message, addr))

    async def _process_invite(self, message: str, addr: Tuple[str, int]):
        """Answer call from Zoiper mobile and negotiate media stream."""
        call_id = self._extract_header(message, "Call-ID")
        cseq = self._extract_header(message, "CSeq")
        from_hdr = self._extract_header(message, "From")
        to_hdr = self._extract_header(message, "To")
        via = self._extract_header(message, "Via")

        caller_match = re.search(r"sip:([a-zA-Z0-9_\-+]+)@", from_hdr)
        caller_id = caller_match.group(1) if caller_match else "Zoiper-Mobile"
        
        # Use a FIFO target profile mapping or generic
        profile_id = None
        if hasattr(self, "expected_profiles"):
            profile_id = self.expected_profiles.pop(caller_id, None)
            if not profile_id:
                profile_id = self.expected_profiles.pop("_next_call", None)
        else:
            profile_id = getattr(self, "target_profile_id", None)

        media_ip = "127.0.0.1" if addr[0] in ("127.0.0.1", "localhost") else self.local_ip
        logger.info("INVITE from %s (%s:%d), profile=%s", caller_id, addr[0], addr[1], profile_id)

        # 1. Send 180 Ringing (immediate indication)
        ringing = (
            f"SIP/2.0 180 Ringing\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr};tag=vg_call_{call_id[:8]}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {cseq}\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        if self.transport:
            self.transport.sendto(ringing.encode("utf-8"), addr)

        # Register the call before starting the listener. The listener updates
        # this same record once its socket is live, avoiding a stale None
        # receiver in the dashboard status endpoint.
        self.active_calls[call_id] = {
            "caller_id": caller_id,
            "addr": addr,
            "start_time": datetime.now(timezone.utc),
            "rtp_receiver": None,
            "rtp_port": None,
            "profile_id": profile_id,
            # SIP dialog state for outbound INFO
            "via": via,
            "from_hdr": from_hdr,
            "to_hdr": to_hdr,
            "cseq": cseq,
            "info_cseq_counter": 100,  # Start INFO CSeq at a high number to avoid collisions
        }

        # 2. Allocate a dynamic RTP port and start RTP Media Receiver using actual bind
        try:
            rtp_port = await self._start_rtp_listener(
                caller_id=caller_id,
                call_id=call_id,
                profile_id=profile_id,
            )
        except RuntimeError as e:
            logger.error("Could not bind RTP port for %s: %s", call_id, e)
            self.active_calls.pop(call_id, None)
            return

        # 3. Send 200 OK with SDP pointing to media IP on actual bound RTP port
        sdp = (
            f"v=0\r\n"
            f"o=VoiceGuardAI 12345 12345 IN IP4 {media_ip}\r\n"
            f"s=VoiceGuard Call\r\n"
            f"c=IN IP4 {media_ip}\r\n"
            f"t=0 0\r\n"
            f"m=audio {rtp_port} RTP/AVP 0 8 101\r\n"
            f"a=rtpmap:0 PCMU/8000\r\n"
            f"a=rtpmap:8 PCMA/8000\r\n"
            f"a=rtpmap:101 telephone-event/8000\r\n"
            f"a=sendrecv\r\n"
        )
        ok_response = (
            f"SIP/2.0 200 OK\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr};tag=vg_call_{call_id[:8]}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {cseq}\r\n"
            f"Contact: <sip:5000@{media_ip}:{self.port}>\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp)}\r\n\r\n"
            f"{sdp}"
        )
        if self.transport:
            self.transport.sendto(ok_response.encode("utf-8"), addr)
            logger.info("Call connected: %s (%s:%d) on RTP port %d", caller_id, addr[0], addr[1], rtp_port)

    async def _start_rtp_listener(
        self,
        caller_id: str = "Live Mobile Caller",
        call_id: str | None = None,
        profile_id: str | None = None,
    ) -> int:
        """Bind UDP for receiving mobile audio on a dynamic port and start RTP receiver.
        Returns the actually bound port.
        """
        loop = asyncio.get_running_loop()
        query = {
            "session_ref": f"sip-{caller_id}",
            "caller_phone": caller_id,
            "amount": "0.0",
            "transfer_type": "Inbound SIP Call",
            "location": "VoIP PBX Trunk",
        }
        if profile_id:
            query["profile_id"] = profile_id
        ws_url = f"ws://localhost:8000/ws/stream?{urlencode(query)}"
        
        rtp_receiver = RTPMediaReceiver(
            ws_url=ws_url,
            on_risk_update=lambda risk_data: asyncio.create_task(
                self.send_risk_info(call_id, risk_data)
            ) if hasattr(self, "send_risk_info") else None
        )
        self.rtp_receivers[call_id] = rtp_receiver
        
        # Try finding a free port between 10000 and 20000 and ACTUAL BIND
        for _ in range(100):
            rtp_port = random.randint(10000, 20000)
            try:
                transport, _ = await loop.create_datagram_endpoint(
                    lambda: rtp_receiver,
                    local_addr=("0.0.0.0", rtp_port),
                )
                self.rtp_transports[call_id] = transport
                if call_id in self.active_calls:
                    self.active_calls[call_id]["rtp_receiver"] = rtp_receiver
                    self.active_calls[call_id]["rtp_port"] = rtp_port
                logger.debug("Bound UDP %d for %s", rtp_port, caller_id)
                return rtp_port
            except OSError:
                continue

        # Clean up any partial registration if completely failed
        self.active_calls.pop(call_id, None)
        self.rtp_receivers.pop(call_id, None)
        raise RuntimeError("[RTP] Could not bind UDP port in 10000-20000 after 100 attempts")

    def handle_bye(self, message: str, addr: Tuple[str, int]):
        call_id = self._extract_header(message, "Call-ID")
        cseq = self._extract_header(message, "CSeq")
        from_hdr = self._extract_header(message, "From")
        to_hdr = self._extract_header(message, "To")
        via = self._extract_header(message, "Via")

        resp = (
            f"SIP/2.0 200 OK\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {cseq}\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        if self.transport:
            self.transport.sendto(resp.encode("utf-8"), addr)
            logger.info("Call terminated from %s:%d", addr[0], addr[1])

        if call_id in self.active_calls:
            call_info = self.active_calls.pop(call_id)
            rtp = call_info.get("rtp_receiver")
            if rtp:
                rtp.stop()

        # Remove per-call RTP receiver and transport
        self.rtp_receivers.pop(call_id, None)
        rtp_transport = self.rtp_transports.pop(call_id, None)
        if rtp_transport:
            try:
                rtp_transport.close()
            except Exception:
                pass
        # Clean up risk level tracking
        self._last_risk_levels.pop(call_id, None)

    # ── SIP INFO handling ───────────────────────────────────────────────

    async def handle_info(self, message: str, addr: Tuple[str, int]):
        """Process inbound SIP INFO messages and optionally forward JSON payloads.
        Expected Content-Type: application/voiceguard+json.
        This handler uses per-call state and avoids undefined globals.
        """
        # Extract SIP headers needed for response
        call_id = self._extract_header(message, "Call-ID")
        cseq = self._extract_header(message, "CSeq")
        from_hdr = self._extract_header(message, "From")
        to_hdr = self._extract_header(message, "To")
        via = self._extract_header(message, "Via")

        content_type = self._extract_header(message, "Content-Type")
        if content_type and "application/voiceguard+json" in content_type.lower():
            parts = message.split("\r\n\r\n", 1)
            if len(parts) == 2:
                try:
                    payload = json.loads(parts[1])
                    # Forward payload to corresponding RTP receiver's websocket if present
                    rtp = self.active_calls.get(call_id, {}).get("rtp_receiver")
                    if rtp and rtp.is_ws_open:
                        await rtp.ws.send(json.dumps(payload))
                    logger.debug("Forwarded INFO payload for call %s", call_id)
                except Exception as e:
                    logger.warning("Failed to parse SIP INFO payload: %s", e)
        else:
            logger.debug("SIP INFO: unsupported Content-Type or missing payload")

        # Send 200 OK response
        resp = (
            f"SIP/2.0 200 OK\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {cseq}\r\n"
            f"Content-Length: 0\r\n\r\n"
        )
        if self.transport:
            self.transport.sendto(resp.encode("utf-8"), addr)
            logger.debug("Sent 200 OK for INFO Call-ID %s", call_id)

        # INFO does not terminate a call - no state cleanup here

    async def send_risk_info(self, call_id: str, risk_data: dict):
        """Send outbound SIP INFO with JSON risk payload to the client for a specific call.

        Only sends when the authoritative risk level changes from the last
        reported level, or when explicitly called for periodic updates.

        Args:
            call_id: The SIP Call-ID for the active dialog.
            risk_data: Dict with keys like session_id, risk_score, risk_level,
                       deepfake_probability, speaker_match, confidence.
        """
        call_info = self.active_calls.get(call_id)
        if not call_info:
            logger.warning(f"[SIP INFO] No active call found for Call-ID {call_id}")
            return

        # Check if risk level changed (suppress duplicate INFOs)
        new_level = risk_data.get("risk_level", "")
        last_level = self._last_risk_levels.get(call_id)
        if new_level and new_level == last_level:
            return  # No change, skip sending
        if new_level:
            self._last_risk_levels[call_id] = new_level

        # Build outbound SIP INFO
        via = call_info.get("via", "")
        from_hdr = call_info.get("from_hdr", "")
        to_hdr = call_info.get("to_hdr", "")
        caller_id = call_info.get("caller_id", "unknown")

        # Increment INFO-specific CSeq counter
        info_cseq = call_info.get("info_cseq_counter", 100) + 1
        call_info["info_cseq_counter"] = info_cseq

        payload_json = json.dumps(risk_data)
        content_length = len(payload_json)

        info_msg = (
            f"INFO sip:{caller_id}@{self.local_ip} SIP/2.0\r\n"
            f"Via: {via}\r\n"
            f"From: {from_hdr}\r\n"
            f"To: {to_hdr}\r\n"
            f"Call-ID: {call_id}\r\n"
            f"CSeq: {info_cseq} INFO\r\n"
            f"Content-Type: application/voiceguard+json\r\n"
            f"Content-Length: {content_length}\r\n\r\n"
            f"{payload_json}"
        )
        if self.transport:
            self.transport.sendto(info_msg.encode("utf-8"), call_info.get("addr"))
            logger.info(f"[SIP INFO] Sent risk INFO for Call-ID {call_id}: level={new_level}")

    # ── Utilities ───────────────────────────────────────────────────────

    def _extract_header(self, message: str, header_name: str) -> str:
        for line in message.split("\r\n"):
            if line.lower().startswith(f"{header_name.lower()}:"):
                return line[len(header_name) + 1 :].strip()
        return ""


sip_server_instance: VoiceGuardSIPServer | None = None


async def start_sip_server(local_ip: str | None = None):
    global sip_server_instance
    loop = asyncio.get_running_loop()
    resolved_ip = local_ip or get_local_ip()
    sip_server_instance = VoiceGuardSIPServer(local_ip=resolved_ip)
    try:
        await loop.create_datagram_endpoint(
            lambda: sip_server_instance,
            local_addr=("0.0.0.0", 5060),
        )
        logger.info(f"[SIP] Successfully started VoiceGuard SIP gateway on port 5060 (LAN IP: {resolved_ip})")
        logger.info("SIP gateway started on port 5060 (LAN: %s)", resolved_ip)
    except Exception as e:
        logger.warning(f"[SIP] Could not bind port 5060: {e}")
