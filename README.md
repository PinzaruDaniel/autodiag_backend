## AutoDiag base backend

Minimal FastAPI backend for a mobile app with:
- register
- login
- refresh token
- send audio endpoint

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export JWT_SECRET="replace-with-a-strong-secret"
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
  - Returns upload confirmation.
