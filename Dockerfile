# Use official Python image
FROM python:3.10.14-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential

# Copy project files
COPY . /app

# Accept CodeArtifact token and AWS region as build args
ARG CODEARTIFACT_AUTH_TOKEN
ARG AWS_REGION

# Fail early if build args are missing
RUN if [ -z "$CODEARTIFACT_AUTH_TOKEN" ]; then echo "ERROR: CODEARTIFACT_AUTH_TOKEN not provided"; exit 1; fi && \
    if [ -z "$AWS_REGION" ]; then echo "ERROR: AWS_REGION not provided"; exit 1; fi

# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt \
      --index-url https://aws:${CODEARTIFACT_AUTH_TOKEN}@skyblu-591082451778.d.codeartifact.${AWS_REGION}.amazonaws.com/pypi/forecasting-db/simple/ \
      --extra-index-url https://pypi.org/simple

# Expose FastAPI port
EXPOSE 8000

# Run the FastAPI app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
