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


class RTPMediaReceiver(asyncio.DatagramProtocol):
    """Listens on UDP port 10000 for RTP packets from mobile phone, pipes to VoiceGuard."""

    def __init__(self, ws_url: str = "ws://localhost:8000/ws/stream?session_ref=zoiper-mobile-call"):
        self.ws_url = ws_url
        self.ws = None
        self.transport = None
        self.loop = asyncio.get_event_loop()
        self.packet_count = 0
        self.is_connected = False

    async def connect_ws(self):
        try:
            self.ws = await websockets.connect(self.ws_url)
            self.is_connected = True
            logger.info("[RTP] Connected to VoiceGuard WebSocket pipeline.")
            print("[RTP] Connected to VoiceGuard WebSocket pipeline.")
        except Exception as e:
            logger.warning(f"[RTP] Could not connect to internal WS: {e}")

    def connection_made(self, transport: asyncio.DatagramTransport):
        self.transport = transport
        logger.info("[RTP] Media receiver listening on UDP 0.0.0.0:10000")
        print("[RTP] Media receiver listening on UDP 0.0.0.0:10000")
        asyncio.create_task(self.connect_ws())

    def datagram_received(self, data: bytes, addr: Tuple[str, int]):
        if len(data) < 12:
            return  # Invalid RTP packet

        # RTP header: 12 bytes
        # Byte 1: payload type (0 = PCMU)
        payload_type = data[1] & 0x7F
        payload = data[12:]
        if not payload:
            return

        self.packet_count += 1

        # Decode mu-law to 16kHz 16-bit linear PCM
        if payload_type == 0:  # PCMU 8kHz
            pcm8k = [_ULAW_TABLE[b] for b in payload]
            # 2x upsample to 16kHz mono
            pcm16k = []
            for s in pcm8k:
                pcm16k.extend([s, s])
            pcm_bytes = struct.pack(f"<{len(pcm16k)}h", *pcm16k)
        else:
            # Fallback raw payload
            pcm_bytes = payload

        # Forward PCM bytes to VoiceGuard WebSocket
        if self.ws and self.is_connected and not self.ws.closed:
            try:
                self.loop.create_task(self.ws.send(pcm_bytes))
            except Exception:
                pass

    def stop(self):
        if self.transport:
            self.transport.close()
        if self.ws and not self.ws.closed:
            asyncio.create_task(self.ws.close())
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
        asyncio.create_task(self._start_rtp_listener())

        # 3. Send 200 OK with SDP pointing to our LAN IP port 10000
        sdp = (
            f"v=0\r\n"
            f"o=VoiceGuardAI 12345 12345 IN IP4 {self.local_ip}\r\n"
            f"s=VoiceGuard Call\r\n"
            f"c=IN IP4 {self.local_ip}\r\n"
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
            f"Contact: <sip:5000@{self.local_ip}:{self.port}>\r\n"
            f"Content-Type: application/sdp\r\n"
            f"Content-Length: {len(sdp)}\r\n\r\n"
            f"{sdp}"
        )
        if self.transport:
            self.transport.sendto(ok_response.encode("utf-8"), addr)
            print(f"[SIP] >>> Call connected with mobile client {caller_id} ({addr[0]}:{addr[1]})!")
            print(f"[SIP] >>> Audio stream routed to VoiceGuard ML pipeline via UDP 10000")

        self.active_calls[call_id] = {
            "caller_id": caller_id,
            "addr": addr,
            "start_time": datetime.now(timezone.utc),
        }

    async def _start_rtp_listener(self):
        """Bind UDP 10000 for receiving mobile audio."""
        if self.rtp_receiver:
            self.rtp_receiver.stop()
        loop = asyncio.get_running_loop()
        self.rtp_receiver = RTPMediaReceiver()
        try:
            self.rtp_transport, _ = await loop.create_datagram_endpoint(
                lambda: self.rtp_receiver,
                local_addr=("0.0.0.0", 10000),
            )
            print("[RTP] Successfully bound UDP 10000 for mobile audio stream.")
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
