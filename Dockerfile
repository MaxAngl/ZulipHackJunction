# syntax=docker/dockerfile:1

# 1. Étape de build du frontend React / Vite
FROM node:22-alpine AS frontend-builder
WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build

# 2. Étape finale : Backend FastAPI + UV + Frontend dist
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

WORKDIR /app

# Variables d'environnement
ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    PORT=8000

# Installer les dépendances Python via uv
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copier le code source de l'application
COPY backend/ ./backend/
COPY ml/ ./ml/
COPY contract/ ./contract/
COPY data/ ./data/

# Copier le build statique du frontend
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# Exposer le port par défaut
EXPOSE 8000

# Commande de démarrage (compatible avec le port dynamique de Render, Koyeb, etc.)
CMD ["sh", "-c", "uv run uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
