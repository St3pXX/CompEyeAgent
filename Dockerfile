FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    RUN_STORE_PATH=/app/data/run_store.sqlite3 \
    COORDINATOR_STORE_PATH=/app/data/coordinator_store.sqlite3 \
    SOURCE_STORE_PATH=/app/data/source_store.sqlite3 \
    COMPETEYE_VECTOR_STORE_PATH=/app/data/vector_store \
    COMPETEYE_CHECKPOINT_PATH=/app/data/graph_checkpoints.sqlite3 \
    COMPETEYE_EMBEDDING_MODEL=BAAI/bge-small-zh-v1.5 \
    HF_ENDPOINT=https://hf-mirror.com

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Core Python deps (this layer rarely changes — keep it cacheable)
RUN pip install --no-cache-dir \
    fastapi httpx pydantic python-dotenv pyyaml litellm \
    langgraph langgraph-checkpoint-sqlite langfuse \
    uvicorn chromadb mcp

# FastEmbed: ONNX-based embeddings (~50MB runtime + ~33MB model).
# Separate layer so core deps stay cached when only fastembed changes.
RUN pip install --no-cache-dir fastembed

COPY . .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
