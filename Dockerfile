# Single-container deploy: build the frontend, then have FastAPI serve it + the API.
# Render/Fly/Railway build this image in their cloud (no local Docker needed).

# --- stage 1: build the React frontend ---
FROM node:20-alpine AS fe
WORKDIR /fe
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- stage 2: Python backend that also serves the built frontend ---
FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    DATA_MODE=real
WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ backend/
# Make the cache writable at runtime (HF Spaces / non-root) so terrain/weather
# fetched on first request can be cached next to the shipped model files.
RUN mkdir -p backend/cache && chmod -R 777 backend/cache
COPY --from=fe /fe/dist frontend/dist

EXPOSE 8000
# Hosts inject $PORT; default to 8000 locally.
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
