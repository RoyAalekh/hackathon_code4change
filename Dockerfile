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
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Move uv from /root/.local/bin to /usr/local/bin
# so Render's non-root user can access it
RUN cp /root/.local/bin/uv /usr/local/bin/uv
ENV PATH="/usr/local/bin:${PATH}"

# Verify
RUN uv --version

# Streamlit default
EXPOSE 8501

CMD ["streamlit", "run", "scheduler/dashboard/app.py", "--server.port=8501", "--server.address=0.0.0.0"]

