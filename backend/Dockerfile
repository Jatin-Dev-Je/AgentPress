FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Optional build metadata
ARG AGENTPRESS_BUILD_SHA=""
ARG AGENTPRESS_BUILD_TIME=""
ENV AGENTPRESS_BUILD_SHA=$AGENTPRESS_BUILD_SHA \
    AGENTPRESS_BUILD_TIME=$AGENTPRESS_BUILD_TIME

# System deps (kept minimal for OSS v1)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml /app/pyproject.toml

RUN pip install --no-cache-dir -U pip \
 && pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "pydantic>=2.7" \
    "pydantic-settings>=2.3" \
    "sqlalchemy[asyncio]>=2.0.30" \
    "asyncpg>=0.29.0" \
    "aiosqlite>=0.20.0" \
    "httpx>=0.27.0"

COPY app /app/app

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=5 \
    CMD python -c "import json,sys,urllib.request;\
u='http://127.0.0.1:8000/health';\
data=json.load(urllib.request.urlopen(u, timeout=2));\
sys.exit(0 if data.get('status')=='ok' else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
