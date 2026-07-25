FROM python:3.11-slim

WORKDIR /app

# Install system dependencies needed for libraries (e.g. gcc, building helpers if any)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Ensure instance folder exists for application uploads/logs
RUN mkdir -p /app/instance

EXPOSE 4500

CMD ["gunicorn", "-w", "1", "-b", "0.0.0.0:4500", "app:app"]
