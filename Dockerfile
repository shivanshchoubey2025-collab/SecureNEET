# =====================================================================
# SecureNEET — Production Multi-Stage Container Image
# =====================================================================

FROM python:3.13-slim

# Set environment flags
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py

WORKDIR /app

# Install system dependencies (build-essential, default-libmysqlclient-dev if needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Expose standard production port
EXPOSE 5000

# Healthcheck pinging /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:5000/health || exit 1

# Production WSGI server command
CMD ["sh", "-c", "python seed_data.py; gunicorn --bind 0.0.0.0:5000 --workers 4 --threads 2 app:app"]
