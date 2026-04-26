from typing import Annotated

from fastapi import Depends

from app.services.auth_service import auth_service


def get_current_user(
    token: Annotated[str, Depends(auth_service.oauth2_scheme)],
) -> dict[str, str]:
    return auth_service.get_current_user(token)
