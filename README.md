# Forecasting Backend

A FastAPI backend service that serves forecast data from the DB to authorized clients via secure endpoints.

## Features

- Secure API endpoints with Auth0 authentication
- DB integration for retrieving forecast and measurement data
- FastAPI-based REST API with OpenAPI documentation
- Environment-based configuration
- Docker support for easy deployment
- ngrok integration for exposing endpoints

## Prerequisites

- Python 3.8 or higher
- AWS credentials configured
- Auth0 account and API configuration
- pip (Python package manager)
- Docker (required for integration tests, optional for containerized deployment)
- ngrok (optional, for exposing endpoints)


## Local Development Setup

1. Clone the repository:
```bash
git clone https://github.com/yourusername/forecasting-backend.git
cd forecasting-backend
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows, use: venv\Scripts\activate
```

3. Install dependencies:
```bash
./install_requirements.sh
```

4. Create a `.env` file in the root directory with your configuration:
```bash
# AWS Configuration
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_DEFAULT_REGION=us-east-2

# Auth0 Configuration
AUTH0_DOMAIN=your-auth0-domain.auth0.com
API_AUDIENCE=https://forecasting-api.forecasting
AUTH0_ALGORITHMS=RS256
AUTH0_CLIENT_ID=your_client_id
AUTH0_CLIENT_SECRET=your_client_secret
AUTH0_CALLBACK_URL=http://localhost:8000/oauth2-redirect

# Database Configuration (PostgreSQL/TimescaleDB)
DATABASE_URL = ""postgresql+asyncpg://postgres:skyblu55!@localhost:15432/appdb""
```

## Running forecasting-backend locally for testing

The API will be available at `http://localhost:8000`. Make sure your `.env` file contains all required environment variables.
Once the server is running, you can access interactive API documentation: `http://localhost:8000/docs`

### Option 1 (easiest): Run the development server directly for quick local testing:

```bash
uvicorn app.main:app --reload
```

### Option 2: Build and run a Docker container for an isolated environment

1. Build the Docker image:
```bash
docker build -t forecasting-api .
```

2. Run the container:
```bash
docker run -p 8000:8000 --env-file .env forecasting-api
```

## Authentication Setup & Testing

To test API endpoints locally, you need a valid JWT token from Auth0:

1. Use the Client Credentials flow to get an access token with the required scope:

```bash
curl --request POST \
  --url https://dev-zk4j1lb7dnrwc0xg.us.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id": "Pt3i90aTorkKYw3pN7IV6zSZaDzZoT5E",
    "client_secret": "bGIqPpVyGJ5lcqY9hrqGdvP0zRrGL7GAK-kqrpmMlEOdk8n2i6_fPuAUp_8LhfEQ",
    "audience": "https://forecasting-api.forecasting",
    "grant_type": "client_credentials",
    "scope": "read:forecast"
  }'
```

Note: The `scope` parameter is required to get a token with the necessary permissions. The API checks for the `read:forecast` permission in both the `permissions` and `scope` claims of the JWT token.

2. Copy the returned `access_token`


## Testing

The test suite includes both unit tests and integration tests. Unit tests use mocks and don't require external services. Integration tests use a real PostgreSQL database running in a Docker container.

### Running Tests

**Run all tests (unit + integration):**
```bash
pytest
```

**Run only unit tests:**
```bash
pytest tests/unit/
```

**Run only integration tests:**
```bash
pytest tests/integration/
```

**Note:** Integration tests require Docker to be running. If Docker is not available, integration tests will be automatically skipped with a helpful message. To run integration tests:
1. Start Docker Desktop (or ensure Docker daemon is running)
2. Start a docker container with
```
docker run --name forecasting-test-db \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=password \
  -e POSTGRES_DB=test_forecasting_db \
  -p 5432:5432 \
  -d postgres:15
```
3. Run: `pytest tests/integration/`

### Test Coverage

**Run tests with coverage report:**
```bash
coverage run --source=app -m pytest tests && coverage report -m
```

## Pre-Commit

Pre-commit hooks are set-up for this repo. To run them locally:
```bash
pip install pre-commit
pre-commit install
pre-commit run --all-files
```

## Error Handling

The API returns appropriate HTTP status codes:
- 200 OK: Successful request
- 403 Forbidden: Unauthorized (missing token)
- 401 Unauthorized: Invalid or expired token
- 404 Not Found: Forecast not found
- 422 Unprocessable Entity: Invalid parameters
- 500 Internal Server Error: Server error
