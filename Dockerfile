FROM node:22-slim AS web
WORKDIR /web
COPY web/package.json ./
RUN npm install --no-audit --no-fund
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg fonts-dejavu-core libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY api/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY api/app ./app
COPY --from=web /web/dist ./web
ENV NUMBA_CACHE_DIR=/tmp/numba
CMD ["sh", "-c", "uvicorn app.main:app --host ${HOST:-127.0.0.1} --port ${PORT:-8090}"]
