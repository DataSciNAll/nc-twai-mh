| [![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/nchandhi/nc-twai-mh) | [![Open in Dev Containers](https://img.shields.io/static/v1?style=for-the-badge&label=Dev%20Containers&message=Open&color=blue&logo=visualstudiocode)](https://vscode.dev/redirect?url=vscode://ms-vscode-remote.remote-containers/cloneInVolume?url=https://github.com/nchandhi/nc-twai-mh)|
|---|---|


# AI Foundry Agent and Observability Demo

This project demonstrates building a RAG (Retrieval-Augmented Generation) agent using Microsoft Foundry, Azure AI Search, and Azure OpenAI.

## Prerequisites

- Azure subscription
- [Azure Developer CLI (azd)](https://learn.microsoft.com/azure/developer/azure-developer-cli/install-azd)
- Python 3.10+

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/nchandhi/nc-twai-mh.git
cd nc-twai-mh
```

### 2. Deploy Infrastructure

```bash
azd auth login
azd up
```

This deploys:
- Azure AI Services (Microsoft Foundry)
- Storage Account
- Azure AI Search
- Azure Storage Account
- Application Insights

### 3. Set Up Python Environment

```bash
cd scripts
python -m venv .venv
.venv\Scripts\activate  # Windows
# source .venv/bin/activate  # Linux/Mac

# Install dependencies (use uv for faster installation)
pip install uv
uv pip install -r requirements.txt
```

### 4. Upload Documents to Search Index

```bash
python 01_upload_data_to_search.py
```

### 5. Create the Agent

```bash
python 02_create_agent.py
```

### 6. Run Evaluations

```bash
python 03_run_evals.py
```

### 7. Run Safety Evaluations

```bash
python 04_safety_evals.py
```

## Cleanup

To delete all Azure resources:

```bash
azd down
```