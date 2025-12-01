# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Runtime system dependency for scikit-learn/scipy wheels
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgomp1 \
    && rm -rf /var/lib/apt/lists/*

# Python env hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

# Copy repo and install package (declared in pyproject.toml)
COPY . .

RUN pip install --upgrade pip setuptools wheel \
    && pip install .
RUN curl -fsSL https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:/root/.cargo/bin:${PATH}"
# Streamlit default port
EXPOSE 8501

CMD ["uv", "run", "scheduler/dashboard/app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
