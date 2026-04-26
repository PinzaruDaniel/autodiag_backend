from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.config import get_settings
from app.models.auth import AuthRequest, RefreshRequest, TokenPair
from app.repositories.in_memory import (
    refresh_tokens,
    refresh_tokens_lock,
    users,
    users_lock,
)


class AuthService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

    def register(self, data: AuthRequest) -> TokenPair:
        with users_lock:
            if data.email in users:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
                )

            users[data.email] = {
                "email": data.email,
                "password_hash": generate_password_hash(data.password),
            }
        return self._build_token_pair(data.email)

    def login(self, data: AuthRequest) -> TokenPair:
        user = users.get(data.email)
        if not user or not check_password_hash(user["password_hash"], data.password):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials"
            )
        return self._build_token_pair(data.email)

    def refresh(self, data: RefreshRequest) -> TokenPair:
        payload = self._decode_token(data.refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        token_id = payload.get("jti")
        email = payload.get("sub")
        with refresh_tokens_lock:
            token_owner = refresh_tokens.get(token_id or "")
            if not token_id or token_owner != email:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid refresh token",
                )
            del refresh_tokens[token_id]

        if not email:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        with users_lock:
            if email not in users:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
                )
        return self._build_token_pair(email)

    def get_current_user(self, token: str) -> dict[str, str]:
        payload = self._decode_token(token)
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

    def _build_token_pair(self, email: str) -> TokenPair:
        return TokenPair(
            access_token=self._create_access_token(email),
            refresh_token=self._create_refresh_token(email),
        )

    def _create_access_token(self, email: str) -> str:
        payload = {
            "sub": email,
            "type": "access",
            "exp": datetime.now(timezone.utc)
            + timedelta(minutes=self._settings.access_token_expire_minutes),
        }
        return jwt.encode(
            payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )

    def _create_refresh_token(self, email: str) -> str:
        token_id = str(uuid4())
        payload = {
            "sub": email,
            "jti": token_id,
            "type": "refresh",
            "exp": datetime.now(timezone.utc)
            + timedelta(days=self._settings.refresh_token_expire_days),
        }
        token = jwt.encode(
            payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )
        with refresh_tokens_lock:
            refresh_tokens[token_id] = email
        return token

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.exceptions.InvalidTokenError as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token"
            ) from exc


auth_service = AuthService()
