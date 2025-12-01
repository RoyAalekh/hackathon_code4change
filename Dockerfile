# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

COPY . .

RUN pip install --upgrade pip setuptools wheel \
    && pip install .

# Install uv
RUN curl -L "https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-unknown-linux-gnu.tar.gz" \
    -o uv.tar.gz \
    && tar -xzf uv.tar.gz \
    && mv uv /usr/local/bin/uv \
    && rm uv.tar.gz

# Test uv works
RUN uv --version

EXPOSE 8501

CMD ["uv", "run", "scheduler/dashboard/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
