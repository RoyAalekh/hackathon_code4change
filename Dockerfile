# syntax=docker/dockerfile:1

FROM python:3.11-slim

# Install minimal system dependencies
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

COPY . .

RUN uv venv .venv \
    && uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app"

# Health check commands
RUN uv --version && python --version && which court-scheduler && which streamlit

EXPOSE 8501

CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
