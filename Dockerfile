# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl git git-lfs libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv
RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

COPY . .

RUN git lfs install && git lfs pull

RUN uv venv .venv \
    && uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

ENV PATH="/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app"

EXPOSE 8501

CMD ["streamlit", "run", "scheduler/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]
