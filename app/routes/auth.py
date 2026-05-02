from fastapi import APIRouter, status

from app.models.auth import AuthRequest, RefreshRequest, ResetPasswordRequest, TokenPair
from app.services.auth_service import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
def register(data: AuthRequest) -> TokenPair:
    return auth_service.register(data)


@router.post("/login", response_model=TokenPair)
def login(data: AuthRequest) -> TokenPair:
    return auth_service.login(data)


@router.post("/refresh", response_model=TokenPair)
def refresh_token(data: RefreshRequest) -> TokenPair:
    return auth_service.refresh(data)


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(data: ResetPasswordRequest) -> None:
    auth_service.reset_password(data)
