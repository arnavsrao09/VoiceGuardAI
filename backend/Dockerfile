FROM python:3.11-slim

# Install system dependencies required for audio processing (libsndfile for soundfile)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libsndfile1 \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install uv
RUN pip install --no-cache-dir uv

WORKDIR /app

# Copy dependency files
COPY pyproject.toml uv.lock requirements.txt ./

# Install dependencies using uv
RUN uv sync --system

# Copy application code
COPY . .

# Expose port
EXPOSE 8000

# Set environment variables
ENV MOCK_ML=false
ENV PYTHONPATH=/app

# Command to run
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
