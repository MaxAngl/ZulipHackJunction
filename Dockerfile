# syntax=docker/dockerfile:1
# Image de mise en ligne (issue #59) : le front buildé, servi par l'API FastAPI, sur une seule
# adresse. Reprend l'idée de la PR #41 (Rami). Pour Render : voir render.yaml.

# 1. Le front. Debian plutôt qu'Alpine : TypeScript 7, oxlint et Vite livrent des binaires glibc.
FROM node:22-bookworm-slim AS front
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# 2. L'API, avec uv ; PyTorch en version CPU (index déclaré dans pyproject.toml).
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PORT=8000
COPY pyproject.toml uv.lock .python-version ./
RUN uv sync --frozen --no-dev
COPY backend/ backend/
COPY ml/ ml/
COPY --from=front /app/frontend/dist frontend/dist
EXPOSE 8000
# La base SQLite est créée au premier démarrage dans data/ (vide).
CMD ["sh", "-c", "uv run --no-sync uvicorn backend.main:app --host 0.0.0.0 --port ${PORT}"]
