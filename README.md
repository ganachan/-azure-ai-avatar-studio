# Azure AI Avatar Studio

A production-ready **multi-avatar AI customer support platform** built on Azure AI Services. The application delivers real-time, text-to-speech avatar conversations powered by Azure OpenAI (GPT-4o), Azure Speech Service, and Azure Cosmos DB — with built-in analytics, batch video generation, and containerized deployment to Azure Container Instances (ACI).

---

## Features

- **Multi-Avatar Real-Time Chat** — Choose from multiple AI avatars (Binaka, Sri, Mike) powered by Azure Speech Avatar API
- **GPT-4o Intelligence** — Azure OpenAI drives natural, context-aware customer support conversations
- **Global Analytics Dashboard** — Track engagement, session duration, message counts, and avatar usage via Cosmos DB + Plotly
- **Batch Video Generation** — Generate offline avatar video responses for async customer communication
- **Azure AI Search RAG** — Retrieval-Augmented Generation over your knowledge base for accurate answers
- **Email Notifications** — Send case summaries via Azure Communication Services
- **Password-Protected Access** — Built-in security gate before the UI loads
- **Containerized** — Docker + ACI deployment ready

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   Streamlit Frontend                    │
│         (avatar_prod.py / enhanced_streamlit_app.py)    │
└────────────────────────┬────────────────────────────────┘
                         │
        ┌────────────────┼──────────────────┐
        ▼                ▼                  ▼
┌──────────────┐  ┌─────────────┐  ┌──────────────────┐
│ Azure OpenAI │  │ Azure Speech│  │  Azure Cosmos DB  │
│   GPT-4o     │  │  Avatar API │  │  (MongoDB vCore)  │
└──────────────┘  └─────────────┘  └──────────────────┘
        │                                   │
        ▼                                   ▼
┌──────────────┐                  ┌──────────────────┐
│ Azure AI     │                  │  Azure Blob      │
│ Search (RAG) │                  │  Storage         │
└──────────────┘                  └──────────────────┘
                                           │
                                           ▼
                                  ┌──────────────────┐
                                  │  Azure Comm Svc  │
                                  │  (Email)         │
                                  └──────────────────┘
```

---

## Project Structure

```
multi_agents/
├── streamlit/
│   ├── avatar_prod.py              # Main production Streamlit app
│   ├── avataranalytics.py          # FastAPI analytics backend
│   ├── Dockerfile                  # Container image definition
│   ├── requirements.txt            # Python dependencies
│   ├── aci-deployment.yaml         # Azure Container Instances config
│   ├── .env.example                # Environment variable template
│   └── batch/
│       ├── enhanced_streamlit_app.py  # Batch video generation UI
│       ├── analytics_api.py           # Analytics REST API
│       ├── global_avatar_analytics/   # Analytics module
│       ├── deployment_guide.md        # Deployment instructions
│       └── .env.example               # Env template for batch app
```

---

## Prerequisites

| Service | Purpose |
|---|---|
| Azure OpenAI (GPT-4o deployment) | AI conversation intelligence |
| Azure Speech Service | Avatar synthesis & TTS |
| Azure Cosmos DB for MongoDB | Case storage & analytics |
| Azure Blob Storage | Avatar video & image storage |
| Azure AI Search | RAG knowledge base |
| Azure Communication Services | Email notifications |

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/ganachan/-azure-ai-avatar-studio.git
cd -azure-ai-avatar-studio/streamlit
```

### 2. Set up environment variables

```bash
cp .env.example .env
# Edit .env and fill in your Azure resource credentials
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run locally

```bash
streamlit run avatar_prod.py
```

The app will be available at `http://localhost:8501`. Use the configured security password to log in.

---

## Docker Deployment

### Build and run locally

```bash
docker build -t azure-ai-avatar-studio .
docker run -p 8501:8501 --env-file .env azure-ai-avatar-studio
```

### Deploy to Azure Container Instances

```bash
# Build and push to Azure Container Registry
az acr build --registry <your-acr> --image avatar-studio:latest .

# Deploy to ACI
az container create \
  --resource-group <rg> \
  --name avatar-studio \
  --image <your-acr>.azurecr.io/avatar-studio:latest \
  --ports 8501 \
  --environment-variables $(cat .env | xargs)
```

See [streamlit/batch/deployment_guide.md](streamlit/batch/deployment_guide.md) for detailed ACI deployment steps.

---

## Batch Video Generation

The `batch/` folder contains a separate Streamlit app for generating avatar videos asynchronously:

```bash
cd streamlit/batch
cp .env.example .env
# Fill in .env values
streamlit run enhanced_streamlit_app.py
```

---

## Environment Variables

Copy `.env.example` to `.env` and configure the following:

| Variable | Description |
|---|---|
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI resource endpoint |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI API key |
| `AZURE_OPENAI_DEPLOYMENT_NAME` | Model deployment name (e.g. `gpt-4o`) |
| `SPEECH_ENDPOINT` | Azure Speech Service endpoint |
| `SPEECH_SUBSCRIPTION_KEY` | Azure Speech subscription key |
| `AZCOSMOS_CONNSTR` | Cosmos DB MongoDB connection string |
| `AZCOSMOS_DATABASE_NAME` | Cosmos DB database name |
| `AZCOSMOS_CONTAINER_NAME` | Cosmos DB container/collection name |
| `BLOB_CONNECTION_STRING` | Azure Blob Storage connection string |
| `BLOB_CONTAINER_NAME` | Blob container for avatar videos |
| `AZURE_SEARCH_ENDPOINT` | Azure AI Search endpoint |
| `AZURE_SEARCH_KEY` | Azure AI Search API key |
| `AZURE_SEARCH_INDEX` | Search index name |
| `BACKGROUND_IMAGE_*_URL` | Avatar background image URLs (per avatar) |
| `AZURE_COMMUNICATION_EMAIL_CONNECTION_STRING` | ACS email connection string |
| `EMAIL_SENDER_ADDRESS` | Verified sender email address |
| `GITHUB_TOKEN` | GitHub PAT for case management integration |

> **Never commit your `.env` file.** It is excluded by `.gitignore`.

---

## Tech Stack

- **Python 3.11**
- **Streamlit** — Web UI framework
- **Azure OpenAI** (GPT-4o) — Language model
- **Azure Speech SDK** — Avatar synthesis & TTS
- **Azure Cosmos DB** (MongoDB vCore) — Data persistence
- **Azure Blob Storage** — Media storage
- **Azure AI Search** — Vector/keyword search (RAG)
- **Azure Communication Services** — Email
- **FastAPI** — Analytics REST API backend
- **Plotly** — Analytics dashboards
- **Docker** — Containerization

---

## Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

---

## License

[MIT](LICENSE)
