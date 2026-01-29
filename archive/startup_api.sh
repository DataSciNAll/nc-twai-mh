#!/bin/bash

# Startup script for Azure App Service - FastAPI only
# Use this for API-only deployments

# Install dependencies
pip install -r requirements.txt

# Start FastAPI with uvicorn
python -m uvicorn api:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 1
