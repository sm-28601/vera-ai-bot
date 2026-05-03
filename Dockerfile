FROM python:3.10-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Run the FastAPI app. Cloud Run automatically sets the $PORT environment variable.
CMD uvicorn bot:app --host 0.0.0.0 --port ${PORT:-8080}
