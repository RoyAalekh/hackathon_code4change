# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system deps
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl unzip \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

COPY . .

# Install Python package
RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# ----------------------------------------------------------
# Install uv system-wide
# ----------------------------------------------------------
RUN curl -LsSf https://astral.sh/uv/install.sh -o uv-installer.sh && \
    sh uv-installer.sh --install-dir /usr/local/bin && \
    rm uv-installer.sh

# Check uv installation
RUN uv --version

EXPOSE 8501

CMD ["uv", "run", "scheduler/dashboard/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
