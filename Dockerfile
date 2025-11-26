FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 \
    libgdk-pixbuf-2.0-0 libgobject-2.0-0 libffi-dev libjpeg-dev \
    libopenjp2-7-dev shared-mime-info build-essential default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Copy scripts
COPY wait-for-it.sh .
COPY entrypoint.sh .
RUN chmod +x ./wait-for-it.sh ./entrypoint.sh

# Copy the .env file into the image
COPY .env .env

# Load env variables inside the image
RUN export $(cat .env | xargs)

EXPOSE 8000

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["gunicorn", "procured_payment.wsgi:application", "--bind", "0.0.0.0:8000"]
