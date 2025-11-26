FROM python:3.11-slim

WORKDIR /app

# Install WeasyPrint system dependencies (Debian ≥ 11)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 \
    libpangoft2-1.0-0 \
    libharfbuzz0b \
    libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 \
    libgobject-2.0-0 \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    shared-mime-info \
    build-essential \
    default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Copy wait-for-it and entrypoint scripts
COPY wait-for-it.sh .
COPY entrypoint.sh .

# Make scripts executable
RUN chmod +x ./wait-for-it.sh ./entrypoint.sh

EXPOSE 8000

# Set entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Default command (will be executed by entrypoint)
CMD ["gunicorn", "IST.wsgi:application", "--bind", "0.0.0.0:8000"]
