# KJScreener local Docker build (based on Screeni-py style)
FROM python:3.13-slim-bookworm

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential wget curl git \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

ENV LANG=C.UTF-8 \
    PYTHONUNBUFFERED=TRUE \
    PYTHONDONTWRITEBYTECODE=TRUE \
    KJScreener_GUI=TRUE \
    KJScreener_DOCKER=TRUE \
    TZ=Asia/Kolkata \
    PATH=/opt/program:$PATH

WORKDIR /opt/program

# Install uv for fast deps
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

COPY requirements.txt pyproject.toml ./

RUN uv venv /venv
ENV PATH=/venv/bin:$PATH
ENV UV_PROJECT_ENVIRONMENT=/venv

# Core deps from requirements (ta-lib 0.6.5+ has manylinux wheels — no system lib needed)
RUN uv pip install --python /venv/bin/python -r requirements.txt || \
    uv pip install --python /venv/bin/python \
      numpy==2.1.0 pandas==2.2.3 scipy yfinance tabulate alive-progress \
      openpyxl requests streamlit streamlit-local-storage Pillow joblib \
      pyyaml plotly httpx apscheduler openai-agents openai anthropic litellm \
      mplfinance num2words ta chromadb nsetools progress retrying appdirs \
      cachecontrol contextlib2

# Optional TA packages (no-deps to avoid numpy conflicts)
RUN uv pip install --python /venv/bin/python --no-deps advanced-ta pandas-ta-remake 2>/dev/null || true

COPY . .

RUN chmod +x ./* 2>/dev/null || true

EXPOSE 8501
EXPOSE 8000

HEALTHCHECK CMD curl --fail http://localhost:8501/_stcore/health || exit 1

WORKDIR /opt/program/src

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]
