# syntax=docker/dockerfile:1

# ---- Stage 1: install the packages into a virtual environment ----
FROM python:3.14-slim AS build

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ---- Stage 2: the image that actually runs ----
FROM python:3.14-slim

LABEL org.opencontainers.image.source="https://github.com/iM-MQ/fastapi-asset-register"
LABEL org.opencontainers.image.description="Asset Register API: FastAPI and PostgreSQL"

# No .pyc files, and logs appear straight away
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"

# A user with no password and no home directory, so the app never runs as root
RUN useradd --system --no-create-home --uid 10001 appuser

WORKDIR /app

# Only the finished virtual environment and the app's code are copied across
COPY --from=build /opt/venv /opt/venv
COPY database.py models.py main.py ./

USER appuser

EXPOSE 8000

# Docker marks the container unhealthy if /health stops answering
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request, sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"]

CMD ["fastapi", "run", "main.py", "--port", "8000"]