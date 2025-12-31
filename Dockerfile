FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    default-mysql-client \
    libmariadb-dev-compat \
    libmariadb-dev \
    libffi-dev \
    libjpeg-dev \
    libopenjp2-7-dev \
    zlib1g-dev \
    libxml2-dev \
    libxslt1-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --upgrade pip setuptools wheel

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Make scripts executable
RUN chmod +x ./wait-for-it.sh ./entrypoint.sh

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "procured_payment.wsgi:application", "--bind", "0.0.0.0:8000"]
