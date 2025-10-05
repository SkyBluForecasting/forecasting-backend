# Use official Python image
FROM python:3.10.14-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*

# Copy project files
COPY . /app

# Copy prebuilt wheels from CI
COPY wheels /wheels

# Install dependencies from local wheels
RUN python -m pip install --upgrade pip && \
    pip install --no-index --find-links=/wheels -r requirements.txt

# Expose FastAPI port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
