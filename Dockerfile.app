FROM python:3.9-slim

WORKDIR /app

# Install system dependencies for Pillow, Bluetooth, and utilities
RUN apt-get update && apt-get install -y \
    curl \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libglib2.0-dev \
    bluez \
    bluetooth \
    fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python packages
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY server.py .
COPY label-printer.py .
COPY logger.py .
COPY label_server/ ./label_server/
COPY rw402b_ble/ ./rw402b_ble/
COPY www/ ./www/
COPY config/ ./config/

# Create directories for runtime data
RUN mkdir -p uploads logs batches temp

# Expose port
EXPOSE 5000

# Run the server with gunicorn for production
CMD ["gunicorn", "-w", "2", "-b", "0.0.0.0:5000", "server:app"]
