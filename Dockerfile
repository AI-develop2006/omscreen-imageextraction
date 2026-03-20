# Cache Bust: 2026-03-20-10-30
# --- Stage 1: Build the React Frontend ---
FROM node:20-alpine AS build-stage
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps
COPY frontend/ ./
# We can set the API URL to be relative since they are in the same container
ENV VITE_API_URL=""
RUN npm run build

# --- Stage 2: Final Runtime Image (Python) ---
FROM python:3.11-slim
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    postgresql-client \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY backend/ ./

# Copy built frontend from build-stage to 'static' folder inside backend directory
# (FastAPI will serve files from this directory)
COPY --from=build-stage /app/frontend/dist ./static

# Expose the port the app runs on
EXPOSE 8000

# Start command
# We use the PORT environment variable (defaulting to 8000)
# This is better for Render as it assigns a dynamic port
CMD ["sh", "-c", "gunicorn -w 4 -k uvicorn.workers.UvicornWorker main:app --bind 0.0.0.0:${PORT:-8000}"]
