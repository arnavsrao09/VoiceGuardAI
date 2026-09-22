import asyncio
import json
import uuid
import pytest
from unittest.mock import patch, MagicMock
from app.telephony.sip_server import VoiceGuardSIPServer

pytestmark = pytest.mark.asyncio

class MockTransport:
    def __init__(self):
        self.sent_messages = []

    def sendto(self, data, addr):
        self.sent_messages.append((data.decode("utf-8"), addr))

    def close(self):
        pass

@pytest.fixture
def sip_server():
    server = VoiceGuardSIPServer(local_ip="127.0.0.1")
    server.transport = MockTransport()
    return server

async def test_rtp_port_binding_and_isolation(sip_server):
    # Setup mocks for datagram endpoint to succeed and return a mock transport
    with patch("asyncio.get_running_loop") as mock_loop_func:
        mock_loop = MagicMock()
        mock_loop_func.return_value = mock_loop
        
        async def mock_create_datagram_endpoint(factory, local_addr):
            # Verify the port is in the correct range
            assert 10000 <= local_addr[1] <= 20000
            return (MockTransport(), MagicMock())
            
        mock_loop.create_datagram_endpoint = mock_create_datagram_endpoint
        
        # Test Call A
        invite_a = (
            "INVITE sip:zoiper@127.0.0.1 SIP/2.0\r\n"
            "Via: SIP/2.0/UDP 192.168.1.100:5060\r\n"
            "From: <sip:userA@127.0.0.1>\r\n"
            "To: <sip:zoiper@127.0.0.1>\r\n"
            "Call-ID: call-A-123\r\n"
            "CSeq: 1 INVITE\r\n\r\n"
        )
        # Handle invite is sync and schedules _process_invite
        await sip_server._process_invite(invite_a, ("192.168.1.100", 5060))
        
        assert "call-A-123" in sip_server.active_calls
        assert "call-A-123" in sip_server.rtp_receivers
        assert "call-A-123" in sip_server.rtp_transports
        
        # Check SDP port
        ok_a = next(msg for msg, _ in sip_server.transport.sent_messages if "200 OK" in msg)
        port_a = sip_server.active_calls["call-A-123"]["rtp_port"]
        assert f"m=audio {port_a} RTP/AVP" in ok_a
        assert 10000 <= port_a <= 20000

        # Test Call B
        invite_b = (
            "INVITE sip:zoiper@127.0.0.1 SIP/2.0\r\n"
            "Via: SIP/2.0/UDP 192.168.1.101:5060\r\n"
            "From: <sip:userB@127.0.0.1>\r\n"
            "To: <sip:zoiper@127.0.0.1>\r\n"
            "Call-ID: call-B-456\r\n"
            "CSeq: 1 INVITE\r\n\r\n"
        )
        await sip_server._process_invite(invite_b, ("192.168.1.101", 5060))
        
        assert "call-B-456" in sip_server.active_calls
        port_b = sip_server.active_calls["call-B-456"]["rtp_port"]
        assert 10000 <= port_b <= 20000
        
        # Now simulate BYE for Call A
        bye_a = (
            "BYE sip:zoiper@127.0.0.1 SIP/2.0\r\n"
            "Via: SIP/2.0/UDP 192.168.1.100:5060\r\n"
            "From: <sip:userA@127.0.0.1>\r\n"
            "To: <sip:zoiper@127.0.0.1>\r\n"
            "Call-ID: call-A-123\r\n"
            "CSeq: 2 BYE\r\n\r\n"
        )
        sip_server.handle_bye(bye_a, ("192.168.1.100", 5060))
        
        # Call A is cleaned up
        assert "call-A-123" not in sip_server.active_calls
        assert "call-A-123" not in sip_server.rtp_receivers
        assert "call-A-123" not in sip_server.rtp_transports
        
        # Call B is still untouched
        assert "call-B-456" in sip_server.active_calls
        assert "call-B-456" in sip_server.rtp_receivers
        assert "call-B-456" in sip_server.rtp_transports

async def test_sip_info_wiring(sip_server):
    # Setup call state directly
    sip_server.active_calls["call-C-789"] = {
        "caller_id": "test",
        "addr": ("192.168.1.100", 5060),
        "via": "SIP/2.0/UDP 192.168.1.100:5060",
        "from_hdr": "<sip:test@127.0.0.1>",
        "to_hdr": "<sip:zoiper@127.0.0.1>",
        "cseq": "1",
        "info_cseq_counter": 100
    }
    
    # First INFO sent on new level
    await sip_server.send_risk_info("call-C-789", {"risk_level": "HIGH", "score": 0.8})
    assert len(sip_server.transport.sent_messages) == 1
    info_1, _ = sip_server.transport.sent_messages[-1]
    assert "INFO sip:test@" in info_1
    assert "CSeq: 101 INFO" in info_1
    assert "application/voiceguard+json" in info_1
    
    # Second update with SAME level should not send INFO
    await sip_server.send_risk_info("call-C-789", {"risk_level": "HIGH", "score": 0.85})
    assert len(sip_server.transport.sent_messages) == 1  # Still 1
    
    # Third update with NEW level should send INFO
    await sip_server.send_risk_info("call-C-789", {"risk_level": "CRITICAL", "score": 0.95})
    assert len(sip_server.transport.sent_messages) == 2
    info_2, _ = sip_server.transport.sent_messages[-1]
    assert "CSeq: 102 INFO" in info_2
    
    # Send INFO for non-existent call should not crash
    await sip_server.send_risk_info("missing-call", {"risk_level": "LOW"})
    assert len(sip_server.transport.sent_messages) == 2
