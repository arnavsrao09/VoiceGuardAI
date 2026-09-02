# VoiceGuardAI Backend

VoiceGuardAI is an AI-powered real-time voice cloning and synthetic speech detection system. 
This backend provides the core ML pipeline, real-time WebSocket analysis, and REST API for VoiceGuardAI.

## Architecture

The system processes incoming audio streams (REST or WebSocket) using the following pipeline:
1. **Preprocessing**: Conversion to 16kHz, mono, float32 PCM.
2. **VAD (Voice Activity Detection)**: Silero VAD prevents processing pure silence.
3. **Ring Buffer**: Buffers audio for ML inference (250ms hops, ~4s windows).
4. **Deepfake Detection**: AASIST model predicts synthetic speech probability.
5. **Speaker Verification**: ECAPA-TDNN compares the voice against enrolled profiles using cosine similarity.
6. **Prosody Analysis**: PyWorld/Parselmouth extract vocal features to detect acoustic anomalies.
7. **Context Analyzer**: Evaluates risk based on transaction metadata.
8. **Risk Fusion & Smoothing**: Calculates a weighted risk score and applies Exponential Moving Average (EMA) for temporal stability.
9. **Alerting**: Triggers alerts if thresholds are breached.

## Prerequisites
- Python 3.11+
- PostgreSQL 16 (with `pgvector` extension)
- Redis
- `uv` package manager

## Setup

1. **Install uv**
   If you don't have `uv` installed:
   ```bash
   curl -LsSf https://astral.sh/uv/install.sh | sh
   ```
   *(Or refer to the official [uv installation guide](https://github.com/astral-sh/uv))*

2. **Sync Dependencies**
   From the `backend` directory, run:
   ```bash
   uv sync
   ```

3. **Environment Variables**
   Copy the example config:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` to match your local PostgreSQL and Redis credentials.

4. **Database Setup**
   Ensure your Postgres database `voiceguardai` exists and has `pgvector` enabled:
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```
   Run Alembic migrations (when DB is ready):
   ```bash
   uv run alembic upgrade head
   ```

5. **Download ML Models**
   Run the download script to fetch necessary models (Silero VAD, ECAPA-TDNN):
   ```bash
   uv run python scripts/download_models.py
   ```
   > **Note on AASIST**: The official AASIST weights must be downloaded manually from the [AASIST repository](https://github.com/clovaai/aasist) and placed in `models/aasist/`. For development without weights, set `MOCK_ML=true` in your `.env`.

6. **Run Backend**
   ```bash
   uv run uvicorn app.main:app --reload
   ```

## APIs & Endpoints

- **Swagger Documentation**: `http://localhost:8000/docs`
- **Health Check**: `GET /api/v1/health`
- **File Analysis**: `POST /api/v1/analyze/file`
- **Speaker Enrollment**: `POST /api/v1/speakers/enroll`
- **WebSocket Streaming**: `WS /api/v1/ws/analyze`
  - First message: JSON `{"type": "start", "speaker_id": "..."}`
  - Subsequent messages: Binary PCM 16-bit 16kHz.

## Testing

Run tests using pytest:
```bash
uv run pytest
```
For testing without heavy ML model loads, ensure `MOCK_ML=true` is used in tests.

## Docker

Build and run the Docker image:
```bash
docker build -t voiceguardai-backend .
docker run -p 8000:8000 --env-file .env voiceguardai-backend
```
*Note: Mount the models volume or set MOCK_ML=true.*

## Privacy Considerations
- **No Raw Audio Persistence**: Raw audio is kept only in memory for inference. Set `RAW_AUDIO_RETENTION=true` strictly for debugging.
- **Anonymization**: PII in logs is sanitized.
