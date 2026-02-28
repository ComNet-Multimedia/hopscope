FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends mtr \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

# data/ is created at runtime via volume
ENV PYTHONUNBUFFERED=1

# Default: run server (override in compose for collector)
ENV PORT=5000
EXPOSE 5000
CMD ["python", "backend/server.py"]
