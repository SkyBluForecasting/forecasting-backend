# Forecasting Backend

A FastAPI backend service that serves solar/load forecasts from S3 to authorized clients via secure endpoints.

## Features

- Secure API endpoints with Auth0 authentication
- S3 integration for retrieving forecast data
- FastAPI-based REST API with OpenAPI documentation
- Environment-based configuration
- Docker support for easy deployment
- ngrok integration for exposing endpoints

## Prerequisites

- Python 3.8 or higher
- AWS credentials configured (for S3 access)
- Auth0 account and API configuration
- pip (Python package manager)
- Docker (optional, for containerized deployment)
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
S3_BUCKET=forecasting-forecasts

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

### Option 3: Use ngrok to expose your local server to the internet (handy for testing Auth0 callbacks or external integrations):

To expose your local API endpoints to the internet for testing:

1. Install ngrok:
```bash
# macOS (using Homebrew)
brew install ngrok

# Or download from https://ngrok.com/download
```

2. Run the development server
```bash
uvicorn app.main:app --reload
```

3. In a new terminal, start ngrok:
```bash
ngrok http 8000
```

4. ngrok will provide a public URL (e.g., `https://abc123.ngrok.io`) that forwards to your local server

5. Update your Auth0 configuration:
   - Add the ngrok URL to your Auth0 application's allowed callback URLs
   - Update the `AUTH0_CALLBACK_URL` in your `.env` file to use the ngrok URL

Note: The ngrok URL changes each time you restart ngrok  without a paid account.

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

Run the test suite:
```bash
pytest
```

To run tests and also check coverage:
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
