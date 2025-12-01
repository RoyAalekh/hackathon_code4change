# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Create uv venv
RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Copy project
COPY . .

# IMPORTANT: ensure scheduler/ is importable ALWAYS
ENV PYTHONPATH="/app"

# Install dependencies inside venv
RUN uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

# Sanity check
RUN uv --version \
    && python --version \
    && pip list

EXPOSE 8501

CMD ["/app/.venv/bin/streamlit", "run", "scheduler/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

