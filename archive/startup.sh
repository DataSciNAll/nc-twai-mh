#!/bin/bash

# Startup script for Azure App Service
# This script starts the Streamlit application

# Install dependencies
pip install -r requirements.txt

# Start Streamlit
# - Disable CORS for App Service
# - Set server address to 0.0.0.0 to accept external connections
# - Use port 8000 (default for App Service)
python -m streamlit run app.py \
    --server.port 8000 \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false
