# ==============================================================================
# Stage 1: Build Dependencies
# ==============================================================================
FROM python:3.10-slim AS builder

WORKDIR /build

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ==============================================================================
# Stage 2: Minimal Production Runtime
# ==============================================================================
FROM python:3.10-slim AS runner

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH=/home/verislip/.local/bin:$PATH

# Install minimal C runtime libraries for OpenCV headless, PyPDFium2, Tesseract OCR (Sinhala & Tamil), and Node for ZK proof verification
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    tesseract-ocr \
    tesseract-ocr-sin \
    tesseract-ocr-tam \
    nodejs \
    && rm -rf /var/lib/apt/lists/*

# Create unprivileged system user for hardened security isolation
RUN groupadd -r verislip && useradd -r -g verislip -d /home/verislip -m -s /bin/bash verislip

# Copy Python packages from builder
COPY --from=builder --chown=verislip:verislip /root/.local /home/verislip/.local

# Copy application source tree
COPY --chown=verislip:verislip . /app

# Switch to non-root user
USER verislip

# Container Healthcheck
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
