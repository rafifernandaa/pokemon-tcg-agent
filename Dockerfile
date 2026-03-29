FROM python:3.11-slim

ENV PYTHONUNBUFFERED=True
ENV APP_HOME=/app
WORKDIR /app

# Copy all files
COPY . ./

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Cloud Run injects $PORT (default 8080)
# Use uvicorn to serve the FastAPI app in main.py
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --workers 1
