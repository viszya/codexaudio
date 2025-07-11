# Builder stage
FROM python:3.13-slim AS builder

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --upgrade pip && pip install poetry
COPY pyproject.toml poetry.lock /app/
RUN poetry config virtualenvs.create true && \
    poetry config virtualenvs.in-project true && \
    poetry install --no-root --no-interaction

# Set model cache directories
ENV WHISPER_MODEL_DIR=/app/models/whisper
ENV HF_HOME=/app/models/huggingface
RUN mkdir -p /app/models/whisper /app/models/huggingface /app/audio && \
    chmod -R a+rw /app/models/whisper /app/models/huggingface

# Copy .env and predownload_models.py
COPY .env /app/.env
COPY predownload_models.py /app/predownload_models.py

# Pre-download the Whisper model
RUN echo "Downloading Whisper model..." && \
    /app/.venv/bin/python -c "import whisper; model = whisper.load_model('medium.en', download_root='/app/models/whisper'); print('Model downloaded to:', model.device)" && \
    ls -l /app/models/whisper

# Pre-download Gemma model
# RUN echo "HF_TOKEN: $(grep HF_TOKEN /app/.env | cut -d'=' -f2 | head -c 4)**** (redacted)" && \
#     export $(cat /app/.env | xargs) && /app/.venv/bin/python /app/predownload_models.py && \
#     ls -lR /app/models/huggingface

# Copy application code
COPY server.py /app/server.py
COPY transcribe.py /app/transcribe.py
COPY summarize.py /app/summarize.py

# Final stage
FROM python:3.13-slim

WORKDIR /app

# Install runtime dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    portaudio19-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy everything from builder
COPY --from=builder /app /app

# Set permissions for cache directories
RUN chmod -R a+rw /app/models/whisper /app/models/huggingface

# Set environment variables
ENV WHISPER_MODEL_DIR=/app/models/whisper
ENV HF_HOME=/app/models/huggingface
ENV PYTHONUNBUFFERED=1
ENV PATH="/app/.venv/bin:$PATH"

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]