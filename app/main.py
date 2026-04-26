from datetime import datetime, timedelta, timezone
import os
from typing import Annotated
from uuid import uuid4

import jwt
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from werkzeug.security import check_password_hash, generate_password_hash

app = FastAPI(title="AutoDiag Backend")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

JWT_SECRET = os.getenv("JWT_SECRET")
if not JWT_SECRET:
    raise RuntimeError("JWT_SECRET environment variable must be set")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
MAX_AUDIO_SIZE_BYTES = 10 * 1024 * 1024

# In-memory stores for demo/minimal setup only.
users: dict[str, dict[str, str]] = {}
refresh_tokens: dict[str, str] = {}


class AuthRequest(BaseModel):
    email: EmailStr
    password: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


def _create_access_token(email: str) -> str:
    payload = {
        "sub": email,
        "type": "access",
        "exp": datetime.now(timezone.utc)
        + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _create_refresh_token(email: str) -> str:
    token_id = str(uuid4())
    payload = {
        "sub": email,
        "jti": token_id,
        "type": "refresh",
        "exp": datetime.now(timezone.utc) + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    refresh_tokens[token_id] = email
    return token


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.exceptions.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
        ) from exc


def _build_token_pair(email: str) -> TokenPair:
    return TokenPair(
        access_token=_create_access_token(email),
        refresh_token=_create_refresh_token(email),
    )


def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, str]:
    payload = _decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )

    email = payload.get("sub")
    user = users.get(email or "")
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )
    return user


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/auth/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(data: AuthRequest) -> TokenPair:
    if data.email in users:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
        )

    users[data.email] = {
        "email": data.email,
        "password_hash": generate_password_hash(data.password),
    }
    return _build_token_pair(data.email)


@app.post("/auth/login", response_model=TokenPair)
def login(data: AuthRequest) -> TokenPair:
    user = users.get(data.email)
    if not user or not check_password_hash(user["password_hash"], data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
        )
    return _build_token_pair(data.email)


@app.post("/auth/refresh", response_model=TokenPair)
def refresh_token(data: RefreshRequest) -> TokenPair:
    payload = _decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
        )

    token_id = payload.get("jti")
    email = payload.get("sub")
    if not token_id or refresh_tokens.get(token_id) != email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    if not email or email not in users:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
        )

    del refresh_tokens[token_id]
    return _build_token_pair(email)


@app.post("/audio/send")
async def send_audio(
    audio: UploadFile = File(...),
    user: dict[str, str] = Depends(get_current_user),
) -> dict[str, str]:
    if not audio.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="No filename provided"
        )
    if not audio.content_type or not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="File must be audio"
        )

    total_size = 0
    while True:
        chunk = await audio.read(1024 * 1024)
        if not chunk:
            break
        total_size += len(chunk)
        if total_size > MAX_AUDIO_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Audio file too large",
            )

    if total_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Empty audio file"
        )

    return {
        "message": "Audio received",
        "filename": audio.filename,
        "size_bytes": str(total_size),
        "uploaded_by": user["email"],
    }
