# API Monitoring and Incident Alert System

A Python project for monitoring API availability and detecting incidents.

## Current Features

- FastAPI application
- Environment-based configuration
- Liveness health endpoint
- Interactive API documentation

## Tech Stack

- Python
- FastAPI
- Uvicorn
- Pydantic Settings

## Local Setup

Create and activate a virtual environment, then install dependencies:

```powershell
python -m pip install -r requirements.txt
```

Start the application:

```powershell
python -m uvicorn app.main:app --reload
```

## Endpoints

- `GET /health/live` — checks whether the API process is responding
- `/docs` — interactive API documentation

## Project Status

Phase 1: Initial setup and local health endpoint.