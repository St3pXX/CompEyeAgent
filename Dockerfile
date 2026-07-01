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
    COMPETEYE_EMBEDDING_MODEL=BAAI/bge-base-zh-v1.5

WORKDIR /app

# Use local apt mirror for faster builds. On Alibaba Cloud ECS the
# *.sources file may already exist; we overwrite with the mirror.
RUN rm -f /etc/apt/sources.list.d/*.sources \
    && echo "deb http://deb.debian.org/debian/ trixie main contrib non-free non-free-firmware" > /etc/apt/sources.list \
    && echo "deb http://deb.debian.org/debian/ trixie-updates main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && echo "deb http://deb.debian.org/debian-security/ trixie-security main contrib non-free non-free-firmware" >> /etc/apt/sources.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# Install core Python dependencies.
# sentence-transformers (~2GB with torch/CUDA) is NOT included — install it
# separately on the host if semantic vector search is needed.  The vector store
# falls back to a 768-dim hash embedding when the model isn't available.
RUN pip install --no-cache-dir \
    fastapi httpx pydantic python-dotenv pyyaml litellm \
    langgraph langgraph-checkpoint-sqlite langfuse \
    uvicorn chromadb mcp

COPY . .
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

RUN mkdir -p /app/data

EXPOSE 8000

CMD ["sh", "-c", "uvicorn api_app:app --host 0.0.0.0 --port ${PORT:-8000}"]
