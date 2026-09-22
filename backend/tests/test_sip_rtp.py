from app.telephony.sip_server import RTPMediaReceiver


def test_rtp_payload_skips_csrc_extension_and_padding():
    # V=2, P=1, X=1, one CSRC; PT 0 (PCMU).
    header = bytes([0xB1, 0x00]) + b"\x00\x01\x00\x00\x00\x01\x12\x34\x56\x78"
    csrc = b"\x11\x22\x33\x44"
    extension = b"\xBE\xDE\x00\x01" + b"\xAA\xBB\xCC\xDD"
    payload = b"\xFF\x7F\x00"
    packet = header + csrc + extension + payload + b"\x00\x02"

    assert RTPMediaReceiver._parse_rtp_payload(packet) == (0, payload)


def test_rtp_payload_rejects_malformed_extension():
    # Extension declares four bytes but the packet does not contain them.
    packet = bytes([0x90, 0x00]) + b"\x00" * 10 + b"\xBE\xDE\x00\x01"

    assert RTPMediaReceiver._parse_rtp_payload(packet) is None
