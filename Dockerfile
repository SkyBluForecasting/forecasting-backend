# syntax=docker/dockerfile:1

FROM python:3.10-slim

WORKDIR /app

# Copy everything
COPY . .

# Copy prebuilt wheels built by GitHub Actions
COPY wheels ./wheels

# Install dependencies from local wheels (no CodeArtifact access needed)
RUN pip install --upgrade pip && \
    pip install --find-links=./wheels -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Make cleanup script executable
RUN chmod +x /app/tasks/cleanup.sh
