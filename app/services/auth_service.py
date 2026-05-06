from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

import jwt
from fastapi import HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from werkzeug.security import check_password_hash, generate_password_hash

from app.core.config import get_settings
from app.models.auth import (
    AuthRequest,
    RefreshRequest,
    ResetPasswordRequest,
    TokenPair,
    ValidateTokensRequest,
)
from app.repositories.azure_table import azure_table_repository


class AuthService:
    def __init__(self) -> None:
        self._settings = get_settings()
        self.oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

    def register(self, data: AuthRequest) -> TokenPair:
        created = azure_table_repository.create_user(
            email=data.email,
            password_hash=generate_password_hash(data.password),
        )
        if not created:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Email already exists"
            )
        return self._build_token_pair(data.email)

    def login(self, data: AuthRequest) -> TokenPair:
        user = azure_table_repository.get_user(email=data.email)
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
        if not isinstance(token_id, str) or not isinstance(email, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )
        if not azure_table_repository.validate_refresh_token(
            token_id=token_id, user_email=email
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )
        azure_table_repository.revoke_refresh_token(token_id=token_id, user_email=email)

        if not azure_table_repository.get_user(email=email):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found"
            )
        return self._build_token_pair(email)

    def validate_tokens(self, data: ValidateTokensRequest) -> TokenPair:
        try:
            access_payload = self._decode_token(data.access_token)
            refresh_payload = self._decode_token(data.refresh_token)

            access_email = access_payload.get("sub")
            refresh_email = refresh_payload.get("sub")
            refresh_token_id = refresh_payload.get("jti")

            if access_payload.get("type") != "access":
                raise self._invalid_token_exception()
            if refresh_payload.get("type") != "refresh":
                raise self._invalid_token_exception()
            if not isinstance(access_email, str) or not isinstance(refresh_email, str):
                raise self._invalid_token_exception()
            if access_email != refresh_email:
                raise self._invalid_token_exception()
            if not isinstance(refresh_token_id, str):
                raise self._invalid_token_exception()
            if not azure_table_repository.validate_refresh_token(
                token_id=refresh_token_id,
                user_email=refresh_email,
            ):
                raise self._invalid_token_exception()
            if not azure_table_repository.get_user(email=refresh_email):
                raise self._invalid_token_exception()

            azure_table_repository.revoke_refresh_token(
                token_id=refresh_token_id,
                user_email=refresh_email,
            )
            return self._build_token_pair(refresh_email)
        except HTTPException as exc:
            if exc.status_code == status.HTTP_401_UNAUTHORIZED:
                raise self._invalid_token_exception() from exc
            raise

    def reset_password(self, data: ResetPasswordRequest) -> None:
        user = azure_table_repository.get_user(email=data.email)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        azure_table_repository.update_user_password(
            email=data.email,
            new_password_hash=generate_password_hash(data.new_password),
        )

    def get_current_user(self, token: str) -> dict[str, str]:
        payload = self._decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type"
            )

        email = payload.get("sub")
        user = azure_table_repository.get_user(email=email or "")
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
        issued_at = datetime.now(timezone.utc)
        expires_at = issued_at + timedelta(days=self._settings.refresh_token_expire_days)
        payload = {
            "sub": email,
            "jti": token_id,
            "type": "refresh",
            "exp": expires_at,
        }
        token = jwt.encode(
            payload, self._settings.jwt_secret, algorithm=self._settings.jwt_algorithm
        )
        azure_table_repository.store_refresh_token(
            token_id=token_id,
            user_email=email,
            issued_at=issued_at.isoformat(),
            expires_at=expires_at.isoformat(),
        )
        return token

    def _decode_token(self, token: str) -> dict[str, Any]:
        try:
            return jwt.decode(
                token,
                self._settings.jwt_secret,
                algorithms=[self._settings.jwt_algorithm],
            )
        except jwt.exceptions.InvalidTokenError as exc:
            raise self._invalid_token_exception() from exc

    @staticmethod
    def _invalid_token_exception() -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


auth_service = AuthService()
