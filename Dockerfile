FROM python:3.10.14-slim

WORKDIR /app
COPY . /app

# Install system dependencies
RUN apt-get update && apt-get install -y build-essential curl unzip

# Accept AWS region as build arg
ARG AWS_REGION

# Fetch CodeArtifact token inside container and install requirements
RUN TOKEN=$(aws codeartifact get-authorization-token \
      --domain skyblu \
      --domain-owner 591082451778 \
      --region $AWS_REGION \
      --query authorizationToken \
      --output text) && \
    python -m pip install --upgrade pip && \
    pip install -r requirements.txt \
      --index-url https://aws:$TOKEN@skyblu-591082451778.d.codeartifact.$AWS_REGION.amazonaws.com/pypi/forecasting-db/simple/ \
      --extra-index-url https://pypi.org/simple

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
