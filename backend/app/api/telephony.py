"""
Telephony & Voice Call Gateway for VoiceGuardAI.

Provides:
1. **IP Geolocation API** — Extracts real caller city, state, country, ISP from IP address
   using free ip-api.com service (no API key required, 45 req/min).
2. **TwiML/SIP Webhook** — Open endpoint for Twilio/Plivo/Asterisk free developer accounts.
3. **WebRTC Call Session** — Initiates a free real-time VoIP/WebRTC call session metadata.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request, HTTPException, Depends
from pydantic import BaseModel
from app.api.deps import verify_api_key
from app.logging_config import get_logger

logger = get_logger("telephony")

router = APIRouter()


# ------------------------------------------------------------------
# 1. Real IP Geolocation (100% Free — ip-api.com, no key required)
# ------------------------------------------------------------------
class CallerMetadata(BaseModel):
    ip: str
    city: str
    region: str
    country: str
    country_code: str
    isp: str
    org: str
    timezone: str
    lat: float
    lon: float
    threat_flag: str  # "DOMESTIC" or "INTERNATIONAL_ANOMALY"


@router.get("/caller-metadata", response_model=CallerMetadata)
async def get_caller_metadata(request: Request, ip: str | None = None):
    """
    Extract real IP geolocation metadata for a caller.
    
    - If `ip` query param is provided, geolocate that IP.
    - Otherwise, use the request's client IP (X-Forwarded-For or direct).
    
    Uses free ip-api.com (no API key, 45 req/min rate limit).
    """
    target_ip = ip or _extract_client_ip(request)

    # For localhost/private IPs, return a sensible default
    if _is_private_ip(target_ip):
        return CallerMetadata(
            ip=target_ip,
            city="Local Network",
            region="Local",
            country="India",
            country_code="IN",
            isp="Local Development",
            org="VoiceGuardAI Dev",
            timezone="Asia/Kolkata",
            lat=19.0760,
            lon=72.8777,
            threat_flag="DOMESTIC",
        )

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                f"http://ip-api.com/json/{target_ip}",
                params={"fields": "status,message,country,countryCode,region,regionName,city,lat,lon,timezone,isp,org,query"},
            )
            data = resp.json()

            if data.get("status") != "success":
                raise HTTPException(status_code=502, detail=f"IP Geolocation failed: {data.get('message', 'Unknown error')}")

            country_code = data.get("countryCode", "")
            threat_flag = "DOMESTIC" if country_code == "IN" else "INTERNATIONAL_ANOMALY"

            return CallerMetadata(
                ip=data.get("query", target_ip),
                city=data.get("city", "Unknown"),
                region=data.get("regionName", "Unknown"),
                country=data.get("country", "Unknown"),
                country_code=country_code,
                isp=data.get("isp", "Unknown"),
                org=data.get("org", "Unknown"),
                timezone=data.get("timezone", "UTC"),
                lat=data.get("lat", 0.0),
                lon=data.get("lon", 0.0),
                threat_flag=threat_flag,
            )
    except httpx.HTTPError as e:
        raise HTTPException(status_code=502, detail=f"IP Geolocation service unreachable: {e}")


# ------------------------------------------------------------------
# 2. TwiML / SIP Webhook Endpoint (Twilio/Plivo/Asterisk/OpenSIPG)
# ------------------------------------------------------------------
@router.post("/voice")
async def telephony_voice_webhook(request: Request):
    """
    Open TwiML/SIP webhook for Twilio, Plivo, or Asterisk free developer accounts.
    
    When a call connects via Twilio, this endpoint returns TwiML XML instructing
    Twilio to stream audio to our WebSocket endpoint for real-time analysis.
    """
    form_data = {}
    try:
        form_data = dict(await request.form())
    except Exception:
        pass

    caller = form_data.get("From", form_data.get("caller_id", "Unknown"))
    called = form_data.get("To", form_data.get("destination", "VoiceGuardAI"))
    call_sid = form_data.get("CallSid", str(uuid.uuid4())[:12])

    logger.info("Incoming voice webhook — From: %s, To: %s, SID: %s", caller, called, call_sid)

    # Return TwiML that streams audio to our WebSocket for real-time analysis
    twiml_response = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Say voice="alice">
        This call is being monitored by VoiceGuard AI for voice authentication and deepfake detection. 
        Please continue your conversation.
    </Say>
    <Connect>
        <Stream url="wss://your-server.com/ws/stream" name="voiceguard_stream">
            <Parameter name="caller_id" value="{caller}" />
            <Parameter name="call_sid" value="{call_sid}" />
        </Stream>
    </Connect>
    <Pause length="3600"/>
</Response>"""

    from fastapi.responses import Response
    return Response(content=twiml_response, media_type="application/xml")


# ------------------------------------------------------------------
# 3. WebRTC Call Session Metadata Initializer
# ------------------------------------------------------------------
class CallSessionRequest(BaseModel):
    caller_name: str = "Live WebRTC Caller"
    device_type: str = "browser"
    user_agent: str = ""
    screen_width: int = 0
    screen_height: int = 0


class CallSessionResponse(BaseModel):
    session_id: str
    ws_url: str
    caller_metadata: dict
    device_fingerprint: dict
    created_at: str


@router.post("/call-session", response_model=CallSessionResponse)
async def create_call_session(request: Request, body: CallSessionRequest):
    """
    Initialize a free WebRTC call session.
    
    Creates session metadata with real IP geolocation and device fingerprint,
    then returns the WebSocket URL for the frontend to stream live audio.
    """
    client_ip = _extract_client_ip(request)
    session_id = str(uuid.uuid4())

    # Get real geolocation
    geo_data = {"ip": client_ip, "city": "Local", "country": "India", "isp": "Local"}
    if not _is_private_ip(client_ip):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"http://ip-api.com/json/{client_ip}")
                data = resp.json()
                if data.get("status") == "success":
                    geo_data = {
                        "ip": data.get("query", client_ip),
                        "city": data.get("city", "Unknown"),
                        "region": data.get("regionName", "Unknown"),
                        "country": data.get("country", "Unknown"),
                        "country_code": data.get("countryCode", ""),
                        "isp": data.get("isp", "Unknown"),
                    }
        except Exception:
            pass

    device_fingerprint = {
        "device_type": body.device_type,
        "user_agent": body.user_agent,
        "screen_resolution": f"{body.screen_width}x{body.screen_height}",
        "ip_address": client_ip,
    }

    return CallSessionResponse(
        session_id=session_id,
        ws_url=f"ws://localhost:8000/ws/stream?session_ref={session_id}",
        caller_metadata=geo_data,
        device_fingerprint=device_fingerprint,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


# ------------------------------------------------------------------
# 4. Real-Time Conversation & Transaction Intent Extraction
# ------------------------------------------------------------------
from app.telephony.intent_extractor import analyze_conversation_transcript

class ConversationAnalysisRequest(BaseModel):
    text: str
    session_id: str | None = None

@router.post("/analyze-conversation")
async def analyze_conversation(body: ConversationAnalysisRequest):
    """
    Real-time speech transcript intent extractor.
    Extracts transaction amounts, banking channels, urgency markers,
    and coercion cues directly from live spoken conversation.
    """
    return analyze_conversation_transcript(body.text)



# ------------------------------------------------------------------
# 5. Asterisk PBX & ARI (Asterisk REST Interface) Telephony Gateway
# ------------------------------------------------------------------
from app.telephony.asterisk_bridge import asterisk_bridge
from app.telephony.simulator import call_simulator

class AsteriskOriginateRequest(BaseModel):
    endpoint: str = "PJSIP/1001"
    extension: str = "5000"
    caller_id: str = "+91 98200 12345"

class AsteriskSimulateCallRequest(BaseModel):
    caller_phone: str = "+91 98200 12345"
    caller_name: str = "Rajesh Sharma (HDFC Wire)"
    destination: str = "5000"
    amount: float = 50000.0
    transfer_type: str = "High-Value Wire Transfer"
    location: str = "Mumbai, MH (IN) - Asterisk SIP"
    scenario: str = "deepfake_pressure"
    duration_seconds: int = 15


class SIPProfileSelectionRequest(BaseModel):
    """The enrolled speaker to verify for SIP calls that start next."""

    profile_id: uuid.UUID | None = None
    expected_caller_id: str | None = None


@router.put("/sip/target-profile")
async def set_sip_target_profile(
    body: SIPProfileSelectionRequest
):
    """Set or clear the speaker profile used by the next inbound SIP call.

    A SIP call owns an internal WebSocket connection. Without this bridge, a
    profile selected in the dashboard never reached that connection and every
    call silently ran in unenrolled/general-monitoring mode.
    """
    from app.telephony.sip_server import sip_server_instance

    if sip_server_instance is None:
        raise HTTPException(status_code=503, detail="SIP gateway is not running")

    profile_id = str(body.profile_id) if body.profile_id else None
    if body.profile_id:
        from app.db.database import AsyncSessionLocal
        from app.db import crud

        async with AsyncSessionLocal() as db:
            profile = await crud.get_voice_profile(db, body.profile_id)
        if profile is None or not profile.embedding:
            raise HTTPException(status_code=404, detail="Selected speaker profile is unavailable")

    caller_id = body.expected_caller_id or "_next_call"
    sip_server_instance.set_target_profile(profile_id, caller_id)
    return {
        "profile_id": profile_id,
        "applies_to": caller_id if caller_id != "_next_call" else "next inbound SIP call",
    }

@router.get("/asterisk/status")
async def get_asterisk_status():
    """Return live Asterisk ARI bridge connection state and active calls."""
    status = asterisk_bridge.get_status()
    sim_calls = call_simulator.get_active_calls()

    from app.telephony.sip_server import sip_server_instance, get_local_ip
    registered_clients = list(sip_server_instance.registered_clients.keys()) if sip_server_instance else []
    sip_active_call_list = []
    if sip_server_instance:
        for cid, cinfo in sip_server_instance.active_calls.items():
            rcv = cinfo.get("rtp_receiver")
            sip_active_call_list.append({
                "call_id": cid,
                "caller_id": cinfo.get("caller_id"),
                "profile_id": cinfo.get("profile_id"),
                "start_time": cinfo["start_time"].isoformat() if "start_time" in cinfo else None,
                "packet_count": rcv.packet_count if rcv else 0,
                "invalid_rtp_packets": rcv.invalid_rtp_packets if rcv else 0,
                "unsupported_payload_packets": rcv.unsupported_payload_packets if rcv else 0,
                "payload_type": rcv.last_payload_type if rcv else None,
                "audio_rms": round(rcv.last_rms, 5) if rcv else 0.0,
                "audio_peak": round(rcv.last_peak, 5) if rcv else 0.0,
                "last_packet_at": rcv.last_packet_at.isoformat() if rcv and rcv.last_packet_at else None,
                "last_score": rcv.last_score if rcv else 0.0,
                "speech_prob": rcv.last_speech_prob if rcv else 0.0,
                "latest_result": rcv.latest_result if rcv else None,
            })
    sip_active_calls = len(sip_active_call_list)

    return {
        **status,
        "simulated_calls": sim_calls,
        "sip_calls": sip_active_call_list,
        "total_active_calls": status["active_calls_count"] + len(sim_calls) + sip_active_calls,
        "sip_server": {
            "is_running": sip_server_instance is not None,
            "local_ip": get_local_ip(),
            "port": 5060,
            "registered_clients": registered_clients,
            "target_profile_id": None,
            "active_calls_count": sip_active_calls,
            "active_calls": sip_active_call_list,
        },
    }

@router.post("/asterisk/simulate-call")
async def simulate_asterisk_call(body: AsteriskSimulateCallRequest):
    """
    Simulate an inbound phone call arriving through Asterisk PBX with ARI snoop media.
    Pipes 16kHz PCM audio frames and real caller metadata directly into VoiceGuardAI.
    """
    result = await call_simulator.start_simulated_call(
        caller_phone=body.caller_phone,
        caller_name=body.caller_name,
        destination=body.destination,
        amount=body.amount,
        transfer_type=body.transfer_type,
        location=body.location,
        audio_scenario=body.scenario,
        duration_seconds=body.duration_seconds,
    )
    return result

@router.post("/asterisk/hangup/{call_id}")
async def hangup_asterisk_call(call_id: str):
    """Hang up an active call on Asterisk or simulated channel."""
    # Try simulated call first
    sim_hung = await call_simulator.hangup_call(call_id)
    # Also attempt Asterisk ARI hangup if real
    ari_hung = await asterisk_bridge.hangup_channel(call_id)
    return {
        "call_id": call_id,
        "status": "terminated" if (sim_hung or ari_hung) else "not_found",
        "simulated_channel": sim_hung,
        "ari_channel": ari_hung,
    }

@router.post("/asterisk/originate")
async def originate_asterisk_call(body: AsteriskOriginateRequest):
    """Trigger an outbound call or callback verification via Asterisk ARI."""
    result = await asterisk_bridge.originate_call(
        endpoint=body.endpoint,
        extension=body.extension,
        caller_id=body.caller_id,
    )
    return result


# ------------------------------------------------------------------
# Utility Helpers
# ------------------------------------------------------------------
def _extract_client_ip(request: Request) -> str:
    """Extract the real client IP from proxy headers or direct connection."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    return request.client.host if request.client else "127.0.0.1"


def _is_private_ip(ip: str) -> bool:
    """Check if an IP address is private/localhost."""
    return (
        ip.startswith("127.")
        or ip.startswith("10.")
        or ip.startswith("192.168.")
        or ip.startswith("172.16.")
        or ip.startswith("172.17.")
        or ip.startswith("172.18.")
        or ip.startswith("172.19.")
        or ip.startswith("172.2")
        or ip.startswith("172.3")
        or ip == "::1"
        or ip == "localhost"
        or ip == "0.0.0.0"
    )
