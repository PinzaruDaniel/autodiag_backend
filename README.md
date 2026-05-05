## AutoDiag base backend

Minimal FastAPI backend for a mobile app with:
- register
- login
- refresh token
- send audio endpoint + local AI classification
- Azure Table Storage persistence for users, refresh tokens, and audio AI results
- modular project structure
- Azure Blob upload with local fallback

## AI Classification

Audio classification runs **locally** using the [`laion/clap-htsat-unfused`](https://huggingface.co/laion/clap-htsat-unfused)
model loaded directly via Hugging Face `transformers`.  No external inference endpoint is required.

How it works:
1. The model and processor are downloaded from the Hugging Face Hub on first use and cached automatically.
2. Uploaded audio bytes are decoded with `soundfile` and converted to a 32-bit mono numpy array.
3. `ClapProcessor` encodes both the audio and the candidate label strings.
4. `ClapModel` produces audio↔text similarity logits that are normalised with softmax into per-label probabilities.
5. Predictions are returned sorted by score (highest first).

The candidate labels are controlled by `AI_DEFAULT_LABELS` (comma-separated). Any set of
descriptive text labels can be used – the model performs zero-shot classification.

## Azure Infrastructure

All required Azure resources (Storage Account, Blob container) can be provisioned with the
included Bicep templates and deployment script:

```bash
chmod +x deploy.sh
./deploy.sh [resource-group] [location]
# defaults: resource-group=autodiag-rg  location=eastus
```

The script will:
1. Create a Resource Group
2. Deploy `infra/main.bicep` (Storage Account + Blob container)
3. Print the connection string to set as `AZURE_STORAGE_CONNECTION_STRING`
4. Optionally build a Docker image and deploy to Azure Container Apps

> Azure Table Storage tables (`users`, `refreshtokens`, `audioresults`) are created
> automatically by the app on first startup.

## Local Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# copy the example env file and fill in values
cp .env.example .env

# required
export JWT_SECRET="replace-with-a-strong-secret"
export AZURE_STORAGE_CONNECTION_STRING="<connection-string-from-deploy-script>"

# optional – defaults shown
export AZURE_STORAGE_CONTAINER="audio"
export AZURE_TABLE_USERS="users"
export AZURE_TABLE_REFRESH_TOKENS="refreshtokens"
export AZURE_TABLE_AUDIO_RESULTS="audioresults"
export LOCAL_AUDIO_DIR="data/audio"

# AI model (downloaded automatically on first request)
export AI_MODEL_NAME="laion/clap-htsat-unfused"
export AI_DEFAULT_LABELS="engine_knock,engine_misfire,engine_idle,engine_normal,engine_overheating,engine_startup,engine_acceleration,engine_stall"

uvicorn app.main:app --reload
```

> **Note:** On first startup the CLAP model weights (~600 MB) are downloaded from the
> Hugging Face Hub and cached in `~/.cache/huggingface/`.  Subsequent starts load the
> cached weights instantly.  Set `HF_HOME` to a custom path to change the cache location.

## Docker

```bash
docker build -t autodiag-backend .
docker run -p 8000:8000 \
  -e JWT_SECRET="..." \
  -e AZURE_STORAGE_CONNECTION_STRING="..." \
  autodiag-backend
```

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

- `POST /auth/reset-password`
  - JSON body: `{ "email": "user@example.com", "new_password": "new-password" }`
  - Resets the password for an existing account (no auth required).
  - Returns `204 No Content` on success.

- `POST /audio/send`
  - Auth: `Authorization: Bearer <access_token>`
  - Multipart form-data field: `audio` (file)
  - Accepts `audio/*` content types up to 10 MB.
  - Tries Azure Blob Storage first (if configured), otherwise saves locally.
  - Runs zero-shot classification with `laion/clap-htsat-unfused` locally via `transformers`.
  - Saves upload metadata + classification result in Azure Table Storage.
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
  - `classification_service.py` – loads CLAP model locally and runs zero-shot inference
- `app/models/` - request/response models
- `app/repositories/` - Azure Table Storage data store
- `app/core/` - app configuration
- `infra/` - Bicep templates for Azure resource provisioning
  - `main.bicep` – Storage Account + Blob container
  - `containerapp.bicep` – Azure Container Apps hosting (optional)
- `Dockerfile` - container image
- `deploy.sh` - end-to-end provisioning script
- `.env.example` - environment variable reference

