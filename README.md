## AutoDiag base backend

Minimal FastAPI backend for a mobile app with:
- register
- login
- refresh token
- send audio endpoint + AI classification
- Azure Cosmos DB persistence for users, refresh tokens, and audio AI results
- modular project structure
- Azure upload with local fallback

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="replace-with-a-strong-secret"
export AZURE_STORAGE_CONNECTION_STRING="<azure-blob-connection-string>"
export AZURE_STORAGE_CONTAINER="audio"
# optional local fallback folder (default: data/audio)
export LOCAL_AUDIO_DIR="data/audio"
export AZURE_COSMOS_ENDPOINT="https://<account>.documents.azure.com:443/"
export AZURE_COSMOS_KEY="<cosmos-key>"
export AZURE_COSMOS_DATABASE="autodiag"
export AZURE_COSMOS_USERS_CONTAINER="users"
export AZURE_COSMOS_REFRESH_TOKENS_CONTAINER="refresh_tokens"
export AZURE_COSMOS_AUDIO_RESULTS_CONTAINER="audio_results"
# AI settings
export AI_MODEL_NAME="laion/clap-htsat-fused"
# optional hosted inference endpoint URL
export AI_INFERENCE_ENDPOINT="https://api-inference.huggingface.co/models/laion/clap-htsat-fused"
# optional bearer token for inference endpoint
export AI_INFERENCE_TOKEN="<inference-token>"
# fallback labels used when endpoint is unavailable
export AI_DEFAULT_LABELS="engine,brake,tire,road_noise,silence"
uvicorn app.main:app --reload
```

> Note: users, refresh token lifecycle records, and audio AI results are persisted in Azure Cosmos DB.

## Endpoints

- `POST /auth/register`
  - JSON body: `{ "email": "user@example.com", "password": "your-password" }`
  - Returns access + refresh tokens.

- `POST /auth/login`
  - JSON body: `{ "email": "user@example.com", "password": "your-password" }`
  - Returns access + refresh tokens.

- `POST /auth/refresh`
  - JSON body: `{ "refresh_token": "..." }`
  - Returns a new access + refresh token pair.

- `POST /audio/send`
  - Auth: `Authorization: Bearer <access_token>`
  - Multipart form-data field: `audio` (file)
  - Accepts `audio/*` content types up to 10 MB.
  - Tries Azure Blob Storage first (if configured), otherwise saves locally.
  - Runs AI classification (`laion/clap-htsat-fused`) via configured inference endpoint.
  - Saves upload metadata + classification result in Azure Cosmos DB.
  - Returns upload confirmation, storage metadata, and classification output.

- `GET /audio/results?limit=10&offset=0`
  - Auth required.
  - Returns paginated AI classification history for current user.

- `GET /audio/results/{result_id}`
  - Auth required.
  - Returns a single AI result only if it belongs to current user.

## Project structure

- `app/routes/` - API routers
- `app/services/` - business logic (auth + audio storage + AI classification/results)
- `app/models/` - request/response models
- `app/repositories/` - Azure Cosmos DB data store
- `app/core/` - app configuration
