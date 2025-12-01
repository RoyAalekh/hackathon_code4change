# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl unzip libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_PROJECT_ENVIRONMENT=/app/.venv

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"
RUN cp /root/.local/bin/uv /usr/local/bin/uv

RUN uv venv /app/.venv
ENV VIRTUAL_ENV=/app/.venv
ENV PATH="/usr/local/bin:/root/.local/bin:/app/.venv/bin:${PATH}"
ENV PYTHONPATH="/app"

COPY . .

RUN uv pip install --upgrade pip setuptools wheel \
    && uv pip install .

RUN uv --version \
    && which uv \
    && python --version \
    && which court-scheduler \
    && which streamlit

EXPOSE 8501

CMD ["bash", "-lc", "cd /app && streamlit run scheduler/dashboard/app.py --server.port=8501 --server.address=0.0.0.0"]
