#!/bin/bash
# Deploy Streamlit Web App to Azure App Service
#
# This script deploys the Streamlit chat application to Azure App Service.
# Prerequisites:
#   - Azure CLI installed and logged in
#   - azd environment provisioned (run 'azd up' first)
#
# Usage:
#   ./05_deploy_webapp.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
WEBAPP_DIR="$ROOT_DIR/webapp"

# Load environment variables from azd
AZURE_DIR="$ROOT_DIR/.azure"
if [ -f "$AZURE_DIR/config.json" ]; then
    ENV_NAME=$(python3 -c "import json; print(json.load(open('$AZURE_DIR/config.json'))['defaultEnvironment'])")
    ENV_FILE="$AZURE_DIR/$ENV_NAME/.env"
    
    if [ -f "$ENV_FILE" ]; then
        echo "Loading environment from: $ENV_FILE"
        set -a
        source "$ENV_FILE"
        set +a
    fi
fi

# Validate required environment variables
if [ -z "$AZURE_WEB_APP_NAME" ]; then
    echo "Error: AZURE_WEB_APP_NAME not set. Run 'azd up' first to provision infrastructure."
    exit 1
fi

if [ -z "$AZURE_RESOURCE_GROUP" ]; then
    echo "Error: AZURE_RESOURCE_GROUP not set."
    exit 1
fi

echo "============================================"
echo "Deploying Streamlit Web App"
echo "============================================"
echo "Resource Group: $AZURE_RESOURCE_GROUP"
echo "Web App Name:   $AZURE_WEB_APP_NAME"
echo "Source Dir:     $WEBAPP_DIR"
echo "============================================"

# Navigate to webapp directory
cd "$WEBAPP_DIR"

# Create a zip file for deployment
echo ""
echo "Creating deployment package..."
ZIP_FILE="$ROOT_DIR/webapp-deploy.zip"
rm -f "$ZIP_FILE"
zip -r "$ZIP_FILE" . -x "*.pyc" -x "__pycache__/*" -x ".git/*" -x "*.zip"

# Deploy to Azure App Service using zip deployment
echo ""
echo "Deploying to Azure App Service..."
az webapp deploy \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_WEB_APP_NAME" \
    --src-path "$ZIP_FILE" \
    --type zip \
    --async false

# Clean up zip file
rm -f "$ZIP_FILE"

# Get the web app URL
WEBAPP_URL=$(az webapp show \
    --resource-group "$AZURE_RESOURCE_GROUP" \
    --name "$AZURE_WEB_APP_NAME" \
    --query "defaultHostName" \
    --output tsv)

echo ""
echo "============================================"
echo "Deployment Complete!"
echo "============================================"
echo "Web App URL: https://$WEBAPP_URL"
echo ""
echo "Note: It may take a few minutes for the app to start."
echo "Check logs with: az webapp log tail -g $AZURE_RESOURCE_GROUP -n $AZURE_WEB_APP_NAME"
echo "============================================"
