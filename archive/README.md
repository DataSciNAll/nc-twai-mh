# Streamlit Chat Application

A simple chat interface that uses Azure OpenAI with managed identity authentication, designed to run on Azure App Service.

## Features

- 💬 **Streaming Chat Responses**: Real-time streaming of AI responses
- 🔐 **Managed Identity Authentication**: Secure keyless authentication using Azure AD
- 📝 **Conversation History**: Maintains chat context within the session
- ☁️ **Azure App Service Ready**: Configured for Linux App Service deployment
- 🔌 **REST API**: FastAPI backend for programmatic access

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Azure App Service                         │
│  ┌─────────────────────────────────────────────────────┐    │
│  │         Streamlit UI  |  FastAPI REST API           │    │
│  │         (port 8501)   |  (port 8000)                │    │
│  │                                                      │    │
│  │  ┌──────────┐    ┌─────────────────┐               │    │
│  │  │ Chat UI  │───▶│ Azure OpenAI    │               │    │
│  │  │ REST API │    │ Client          │               │    │
│  │  └──────────┘    └────────┬────────┘               │    │
│  │                           │                         │    │
│  │  System Assigned Managed Identity                   │    │
│  └───────────────────────────┼─────────────────────────┘    │
└──────────────────────────────┼──────────────────────────────┘
                               │
                               ▼
                ┌──────────────────────────┐
                │    Azure OpenAI          │
                │    (Cognitive Services)   │
                │                          │
                │  • gpt-4o-mini           │
                │  • Managed Identity Auth  │
                └──────────────────────────┘
```

## Prerequisites

- Azure subscription
- Azure CLI installed
- azd CLI installed
- Python 3.11+

## Local Development

1. **Set environment variables:**
   ```bash
   export AZURE_OPENAI_ENDPOINT="https://your-openai-service.openai.azure.com/"
   export AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4o-mini"
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally:**
   ```bash
   # Run Streamlit UI
   streamlit run app.py
   
   # Or run FastAPI REST API
   uvicorn api:app --reload
   ```

   - Streamlit UI: `http://localhost:8501`
   - FastAPI: `http://localhost:8000`
   - API Docs: `http://localhost:8000/docs`

## REST API Usage

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | API information |
| GET | `/health` | Health check |
| POST | `/chat` | Send message, get complete response |
| POST | `/chat/stream` | Send message, get streaming response |

### Example: Send a chat message

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What is Azure OpenAI?",
    "conversation_history": [],
    "temperature": 0.7
  }'
```

### Example: Chat with conversation history

```bash
curl -X POST "http://localhost:8000/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Can you explain more?",
    "conversation_history": [
      {"role": "user", "content": "What is Azure?"},
      {"role": "assistant", "content": "Azure is Microsoft cloud platform..."}
    ]
  }'
```

### Example: Streaming response

```bash
curl -X POST "http://localhost:8000/chat/stream" \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me a short story"}'
```

## Deployment to Azure

### Option 1: Using the deployment script

1. **Provision infrastructure (if not already done):**
   ```bash
   azd up
   ```

2. **Deploy the web app:**
   ```bash
   cd scripts
   ./05_deploy_webapp.sh
   ```

### Option 2: Manual deployment

1. **Provision infrastructure:**
   ```bash
   azd up
   ```

2. **Deploy using Azure CLI:**
   ```bash
   cd webapp
   zip -r ../webapp.zip .
   az webapp deploy \
       --resource-group <your-rg> \
       --name <your-webapp-name> \
       --src-path ../webapp.zip \
       --type zip
   ```

## Configuration

The app uses the following environment variables (set automatically by Bicep):

| Variable | Description |
|----------|-------------|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI service endpoint URL |
| `AZURE_OPENAI_CHAT_DEPLOYMENT` | Model deployment name (default: gpt-4o-mini) |

## Authentication

The application uses **Azure Managed Identity** for authentication:

- **In Azure App Service**: System-assigned managed identity is automatically used
- **Locally**: Azure CLI credentials are used via `DefaultAzureCredential`

The managed identity is granted the `Cognitive Services OpenAI User` role on the Azure OpenAI resource during infrastructure provisioning.

## Troubleshooting

### View application logs

```bash
az webapp log tail --resource-group <rg-name> --name <webapp-name>
```

### Common issues

1. **401 Unauthorized**: The managed identity may not have proper permissions. Verify the role assignment in Azure portal.

2. **App not starting**: Check the startup logs. Ensure Python 3.11 is configured and all dependencies install correctly.

3. **Timeout errors**: Azure OpenAI may be throttled. Check your TPM (tokens per minute) quota.

## File Structure

```
app/
├── app.py              # Streamlit web UI application
├── api.py              # FastAPI REST API
├── requirements.txt    # Python dependencies
├── startup.sh          # Azure App Service startup (Streamlit)
├── startup_api.sh      # Azure App Service startup (FastAPI)
└── README.md          # This file
```
