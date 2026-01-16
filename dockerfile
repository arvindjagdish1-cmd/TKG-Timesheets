FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# System deps:
# - libpq-dev: Postgres driver build deps
# - libreoffice: headless conversion for XLSX -> PDF
# - fonts: better PDF rendering
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    ca-certificates \
    libreoffice \
    libreoffice-writer \
    libreoffice-calc \
    fonts-dejavu \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app

# Create directories for uploads/exports if they don't exist
RUN mkdir -p /app/media /app/exports

EXPOSE 8000
