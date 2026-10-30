FROM python:3.12-slim AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libglib2.0-0 libgl1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
ARG INSTALL_EXTRAS=""
COPY app ./app
RUN if [ -n "$INSTALL_EXTRAS" ]; then pip install --no-cache-dir ".[$INSTALL_EXTRAS]"; else pip install --no-cache-dir .; fi
COPY alembic.ini ./alembic.ini
COPY alembic ./alembic
RUN useradd --create-home --uid 10001 appuser && mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
