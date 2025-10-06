# syntax=docker/dockerfile:1

FROM python:3.10-slim

WORKDIR /app

# Copy source code
COPY . .

# Copy prebuilt wheels from CI
# (these should already exist on the EC2 host when building)
COPY wheels ./wheels

# Upgrade pip and install wheels directly
RUN pip install --upgrade pip && \
    pip install --no-index --find-links=./wheels -r requirements.txt

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
