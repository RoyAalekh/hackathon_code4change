# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Make uv visible to shell
ENV PATH="/root/.local/bin:${PATH}"

# Create uv virtual environment
RUN uv venv /app/.venv

# Activate venv for rest of image
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Make project importable
ENV PYTHONPATH="/app"

COPY . .

RUN uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

RUN uv --version \
    && which uv \
    && which python \
    && python --version \
    && which streamlit

EXPOSE 8501

CMD ["streamlit", "run", "scheduler/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
