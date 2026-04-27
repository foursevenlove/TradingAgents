# TradingAgents Docker Deployment
# Multi-stage build: frontend + backend

# Stage 1: Build frontend
FROM node:20-alpine AS frontend-builder

WORKDIR /app/frontend

# Copy frontend package files
COPY web/frontend/package.json web/frontend/package-lock.json* ./

# Install dependencies
RUN npm ci || npm install

# Copy frontend source
COPY web/frontend/ ./

# Build frontend
RUN npm run build

# Stage 2: Python backend with frontend static files
FROM python:3.11-slim AS backend

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt pyproject.toml ./

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY tradingagents/ ./tradingagents/
COPY cli/ ./cli/
COPY web/backend/ ./web/backend/
COPY main.py analyze.py ./

# Copy frontend build from stage 1
COPY --from=frontend-builder /app/frontend/dist ./web/frontend/dist

# Create necessary directories
RUN mkdir -p /app/logs /app/reports /app/results

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV TRADINGAGENTS_WEB_HOST=0.0.0.0
ENV TRADINGAGENTS_WEB_PORT=8000

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/docs || exit 1

# Run the application
CMD ["uvicorn", "web.backend.app:app", "--host", "0.0.0.0", "--port", "8000"]