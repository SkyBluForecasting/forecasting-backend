# Use official Python image
FROM python:3.10.14-slim

# Set workdir
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential

# Copy project files
COPY . /app

# Copy pre-built wheels
COPY wheels /wheels

# Install dependencies from wheels (no AWS needed)
RUN pip install --no-index --find-links=/wheels -r requirements.txt

# Expose FastAPI port
EXPOSE 8000

# Run the app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
