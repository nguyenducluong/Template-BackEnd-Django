FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements/prod.txt requirements/base.txt ./
RUN pip install --no-cache-dir -r prod.txt

# Copy project files
COPY . .

# Create media and static directories
RUN mkdir -p media staticfiles logs

# Start Gunicorn + Uvicorn
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4", "--timeout", "60"]