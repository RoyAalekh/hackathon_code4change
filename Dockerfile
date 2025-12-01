# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Install system deps (including curl for uv installer)
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 curl \
    && rm -rf /var/lib/apt/lists/*

# Python env hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy repo
COPY . .

# Install Python package
RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# Install uv
RUN curl -fsSL https://astral.sh/uv/install.sh | sh

# Add uv to PATH so CMD can find it
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"

EXPOSE 8501

CMD ["uv", "run", "scheduler/dashboard/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
