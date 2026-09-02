import pytest
from httpx import AsyncClient, ASGITransport
import numpy as np
import io
import soundfile as sf
from app.main import app

@pytest.mark.asyncio
async def test_analyze_file_endpoint():
    # Create dummy wav
    audio = np.random.uniform(-1, 1, 16000).astype(np.float32)
    buf = io.BytesIO()
    sf.write(buf, audio, 16000, format='WAV', subtype='PCM_16')
    buf.seek(0)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        response = await ac.post(
            "/api/v1/analyze/file",
            files={"file": ("test.wav", buf, "audio/wav")},
            data={"transaction_type": "fund_transfer"}
        )
        
    assert response.status_code == 200
    data = response.json()
    assert "score" in data
    assert "level" in data
