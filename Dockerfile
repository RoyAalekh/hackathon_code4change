# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# MAKE SURE uv is globally visible
ENV PATH="/root/.local/bin:${PATH}"

RUN uv venv /app/.venv

ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/app/.venv/bin:${PATH}"

COPY . .

RUN uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

RUN uv --version \
    && which uv \
    && which python \
    && python --version \
    && which streamlit

EXPOSE 8501

CMD ["/app/.venv/bin/streamlit", "run", "scheduler/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
