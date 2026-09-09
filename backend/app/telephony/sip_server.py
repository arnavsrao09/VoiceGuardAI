"""
Lightweight SIP / VoIP Gateway Server for VoiceGuardAI.

Runs an async UDP SIP server on port 5060:
- Handles SIP REGISTER from softphones (Zoiper / Linphone on mobile or desktop).
- Sends 200 OK responses to register any account (e.g. 1001).
- Supports inbound calls from mobile Zoiper:
  - Answers with 180 Ringing and 200 OK with SDP
  - Starts an RTP receiver on UDP port 10000
  - Decodes G.711 mu-law audio packets from the phone microphone in real-time
  - Upsamples to 16kHz mono PCM and pipes directly into VoiceGuardAI ML engine
  - Live updates the Asterisk / PBX dashboard card so the user sees their mobile call!
"""

from __future__ import annotations

import asyncio
import logging
import re
import socket
import struct
from datetime import datetime, timezone
from typing import Tuple, Any

import websockets

logger = logging.getLogger("voiceguard.telephony.sip")
logger.setLevel(logging.INFO)


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

    def __init__(self, ws_url: str = "ws://127.0.0.1:8000/ws/stream?session_ref=zoiper-mobile-call"):
        self.ws_url = ws_url
        self.ws = None
        self.transport = None
        self.packet_count = 0
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
            print("[RTP] Connected to VoiceGuard WebSocket pipeline.")
            self.drain_task = asyncio.create_task(self._drain_ws_results())
            self.sender_task = asyncio.create_task(self._sender_loop())
        except Exception as e:
            logger.warning(f"[RTP] Could not connect to internal WS: {e}")
            print(f"[RTP] Could not connect to internal WS: {e}")

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
            import json
            while self.is_connected and self.is_ws_open:
                raw_msg = await self.ws.recv()
                if raw_msg:
                    try:
                        data = json.loads(raw_msg)
                        self.latest_result = data
                        self.last_score = float(data.get("score", 0.0))
                        self.last_speech_prob = float(data.get("speech_probability", 0.0))
                        if self.last_speech_prob > 0.3:
                            print(f"[RTP VOICE] Phone speech detected! Prob: {self.last_speech_prob:.2f}, Score: {self.last_score:.2f}")
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        logger.info("[RTP] Media receiver listening on UDP 0.0.0.0:10000")
        print("[RTP] Media receiver listening on UDP 0.0.0.0:10000")
        asyncio.create_task(self.connect_ws())

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        if len(data) < 12:
            return  # Invalid RTP packet

        # RTP header: 12 bytes
        # Byte 1: payload type (0 = PCMU, 8 = PCMA)
        payload_type = data[1] & 0x7F
        payload = data[12:]
        if not payload:
            return

        self.packet_count += 1

        # Decode mu-law or A-law to 16-bit linear PCM
        if payload_type == 0:  # PCMU 8kHz
            pcm8k = [_ULAW_TABLE[b] for b in payload]
        elif payload_type == 8:  # PCMA 8kHz (A-law)
            pcm8k = [_ALAW_TABLE[b] for b in payload]
        else:
            return  # Ignore non-voice packets (e.g. DTMF)

        # 2x linear interpolation upsampling from 8kHz to 16kHz
        pcm16k = []
        n = len(pcm8k)
        for i in range(n):
            s0 = pcm8k[i]
            s1 = pcm8k[i + 1] if i + 1 < n else s0
            pcm16k.extend([s0, (s0 + s1) // 2])
        pcm_bytes = struct.pack(f"<{len(pcm16k)}h", *pcm16k)

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
        print(f"[RTP] Media receiver stopped. Total packets processed: {self.packet_count}")


class VoiceGuardSIPServer(asyncio.DatagramProtocol):
    def __init__(self, host: str = "0.0.0.0", port: int = 5060, local_ip: str | None = None):
        self.host = host
        self.port = port
        self.local_ip = local_ip or get_local_ip()
        self.transport: asyncio.DatagramTransport | None = None
        self.registered_clients: dict[str, Tuple[str, int]] = {}
        self.active_calls: dict[str, dict[str, Any]] = {}
        self.rtp_receiver: RTPMediaReceiver | None = None
        self.rtp_transport = None

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        logger.info(f"[SIP] VoiceGuard SIP Server listening on UDP {self.host}:{self.port} (LAN IP: {self.local_ip})")
        print(f"[SIP] VoiceGuard SIP Server listening on UDP {self.host}:{self.port} (LAN IP: {self.local_ip})")

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
            f"Allow: INVITE, ACK, CANCEL, OPTIONS, BYE, REGISTER\r\n"
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
        logger.info(f"[SIP] Registered client '{account}' from {addr[0]}:{addr[1]}")
        print(f"[SIP] REGISTER accepted for '{account}' from {addr[0]}:{addr[1]}")

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

        # Determine media IP: if client connected from loopback, use 127.0.0.1, else local IP
        media_ip = "127.0.0.1" if addr[0] in ("127.0.0.1", "localhost") else self.local_ip

        # 1. Send 180 Ringing
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

        # 2. Start RTP Media Receiver on port 10000
        asyncio.create_task(self._start_rtp_listener(caller_id=caller_id))

        # 3. Send 200 OK with SDP pointing to media IP on port 10000
        sdp = (
            f"v=0\r\n"
            f"o=VoiceGuardAI 12345 12345 IN IP4 {media_ip}\r\n"
            f"s=VoiceGuard Call\r\n"
            f"c=IN IP4 {media_ip}\r\n"
            f"t=0 0\r\n"
            f"m=audio 10000 RTP/AVP 0 8 101\r\n"
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
            print(f"[SIP] >>> Call connected with client {caller_id} ({addr[0]}:{addr[1]})!")
            print(f"[SIP] >>> Audio stream routed to VoiceGuard ML pipeline via UDP 10000 (media IP: {media_ip})")

        self.active_calls[call_id] = {
            "caller_id": caller_id,
            "addr": addr,
            "start_time": datetime.now(timezone.utc),
            "rtp_receiver": self.rtp_receiver,
        }

    async def _start_rtp_listener(self, caller_id: str = "Live Mobile Caller"):
        """Bind UDP 10000 for receiving mobile audio."""
        if self.rtp_receiver:
            self.rtp_receiver.stop()
        loop = asyncio.get_running_loop()
        ws_url = (
            f"ws://localhost:8000/ws/stream?session_ref=sip-{caller_id}"
            f"&caller_phone={caller_id}"
            f"&amount=0.0"
            f"&transfer_type=Inbound%20SIP%20Call"
            f"&location=VoIP%20PBX%20Trunk"
        )
        self.rtp_receiver = RTPMediaReceiver(ws_url=ws_url)
        try:
            self.rtp_transport, _ = await loop.create_datagram_endpoint(
                lambda: self.rtp_receiver,
                local_addr=("0.0.0.0", 10000),
            )
            print(f"[RTP] Successfully bound UDP 10000 for mobile audio stream ({caller_id}).")
        except Exception as e:
            print(f"[RTP] Could not bind UDP 10000 (might be already active): {e}")

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
            print(f"[SIP] <<< Call terminated from {addr[0]}:{addr[1]}")

        if call_id in self.active_calls:
            del self.active_calls[call_id]

        if self.rtp_receiver:
            self.rtp_receiver.stop()
            self.rtp_receiver = None

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
        print(f"[SIP] Successfully started VoiceGuard SIP gateway on port 5060 (LAN IP: {resolved_ip})")
    except Exception as e:
        logger.warning(f"[SIP] Could not bind port 5060: {e}")
