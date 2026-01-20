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

# Install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Install gunicorn for production
RUN pip install --no-cache-dir gunicorn

# Copy application
COPY . /app

# Create directories for uploads/exports if they don't exist
RUN mkdir -p /app/media /app/exports /app/staticfiles

# Collect static files
RUN python manage.py collectstatic --noinput --clear 2>/dev/null || true

EXPOSE 8000

# Default command (overridden in compose)
CMD ["gunicorn", "tkg_te.wsgi:application", "--bind", "0.0.0.0:8000"]
