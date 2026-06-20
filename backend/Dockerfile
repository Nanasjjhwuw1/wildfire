# Backend image: Python 3.11 (rasterio/GDAL wheels are reliable on Linux here).
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DATA_MODE=real

WORKDIR /app

# Install deps first for better layer caching.
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# App code (the `backend` package is imported as backend.*).
COPY backend /app/backend

EXPOSE 8000

# Simple container healthcheck against the liveness endpoint.
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health').status==200 else 1)"

CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
