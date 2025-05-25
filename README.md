# Forecasting Backend

A FastAPI backend service that serves solar/load forecasts from S3 to authorized clients via secure endpoints.

## Features

- Secure API endpoints with Auth0 authentication
- S3 integration for forecast data storage
- FastAPI-based REST API with OpenAPI documentation
- Environment-based configuration

## Prerequisites

- Python 3.8 or higher
- AWS credentials configured (for S3 access)
- Auth0 account and API configuration
- pip (Python package manager)

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
pip install -r requirements.txt
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
AUTH0_AUDIENCE=https://forecasting-api.forecasting
AUTH0_ALGORITHMS=RS256
```

5. Run the development server:
```bash
uvicorn app.main:app --reload
```

## Authentication Setup & Testing

To test API endpoints locally, you need a valid JWT token from Auth0:

1. Use the Client Credentials flow to get an access token:

```bash
curl --request POST \
  --url https://dev-zk4j1lb7dnrwc0xg.us.auth0.com/oauth/token \
  --header 'content-type: application/json' \
  --data '{
    "client_id": "Pt3i90aTorkKYw3pN7IV6zSZaDzZoT5E",
    "client_secret": "bGIqPpVyGJ5lcqY9hrqGdvP0zRrGL7GAK-kqrpmMlEOdk8n2i6_fPuAUp_8LhfEQ",
    "audience": "https://forecasting-api.forecasting",
    "grant_type": "client_credentials"
  }'
```

2. Copy the returned `access_token`

## API Documentation

Once the server is running, you can access:
- Interactive API documentation: `http://localhost:8000/docs`
- Alternative API documentation: `http://localhost:8000/redoc`

To use the API:
1. Click the "Authorize" button
2. Enter your token with the "Bearer" prefix: `Bearer your_access_token`
3. Click "Authorize"

The API provides the following endpoints:

### Get Forecast
- `GET /forecast`
- Parameters:
  - `utility_id` (required): The utility identifier (e.g., "ieso")
  - `asset_id` (required): The asset identifier (e.g., "L9M")
  - `date` (required): The forecast date in YYYY-MM-DD format
- Example: `/forecast?utility_id=ieso&asset_id=L9M&date=2024-03-24`

### Get Latest Forecast
- `GET /forecast/latest`
- Parameters:
  - `utility_id` (required): The utility identifier (e.g., "ieso")
  - `asset_id` (required): The asset identifier (e.g., "L9M")
- Example: `/forecast/latest?utility_id=ieso&asset_id=L9M`

## Testing

Run the test suite:
```bash
pytest
```

The test suite includes:
- Authentication tests
- API endpoint tests
- Parameter validation tests
- Error handling tests

## Project Structure

```
forecasting-backend/
├── app/
│   ├── __init__.py
│   ├── main.py      # FastAPI application and routes
│   ├── auth.py      # Authentication and token validation
│   ├── s3.py        # S3 client and forecast retrieval
│   └── config.py    # Configuration and environment variables
├── tests/
│   ├── __init__.py
│   ├── test_auth.py # Authentication tests
│   └── test_main.py # API endpoint tests
├── requirements.txt # Project dependencies
└── .env            # Environment variables (create this)
```

## Error Handling

The API returns appropriate HTTP status codes:
- 200: Successful request
- 401: Unauthorized (invalid or missing token)
- 404: Forecast not found
- 422: Invalid parameters
- 500: Server error

## License

[Add your license information here]
