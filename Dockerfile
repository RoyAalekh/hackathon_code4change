# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Tell uv to ALWAYS use /app/.venv instead of creating temp envs
ENV UV_PROJECT_ENVIRONMENT=/app/.venv

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

# Create virtual env
RUN uv venv /app/.venv

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

# Ensure scheduler is always importable
ENV PYTHONPATH="/app"

# Copy project
COPY . .

# Install deps
RUN uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

# Diagnostics
RUN uv --version \
    && python --version \
    && which court-scheduler \
    && which python \
    && which streamlit \
    && pip list

EXPOSE 8501

CMD ["/app/.venv/bin/streamlit", "run", "scheduler/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
