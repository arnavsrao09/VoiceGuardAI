import pytest
from fastapi.testclient import TestClient
from app.main import app
import json

def test_websocket_analyze():
    client = TestClient(app)
    
    with client.websocket_connect("/api/v1/ws/analyze") as websocket:
        # Send start config
        config = {
            "type": "start",
            "transaction_type": "fund_transfer",
            "transaction_amount": 5000
        }
        websocket.send_text(json.dumps(config))
        
        # Expect session_started
        response = websocket.receive_json()
        assert response.get("type") == "session_started"
        assert "session_id" in response
        
        # We won't send binary data in this simple test since VAD / ML logic
        # might require a lot of mock setup, but we verify the connection works.
