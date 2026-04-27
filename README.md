## AutoDiag base backend

Minimal FastAPI backend for a mobile app with:
- register
- login
- refresh token
- send audio endpoint
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
uvicorn app.main:app --reload
```

> Note: this base backend uses in-memory storage for users and refresh tokens. Data is reset when the server restarts.

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
  - Returns upload confirmation with storage backend and location.

## Project structure

- `app/routes/` - API routers
- `app/services/` - business logic (auth + audio storage)
- `app/models/` - request/response models
- `app/repositories/` - in-memory data store
- `app/core/` - app configuration
