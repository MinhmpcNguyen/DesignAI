from __future__ import annotations

from fastapi import Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from db.models import UserAccount
from services.auth_service import AuthService, AuthenticationError

bearer_scheme = HTTPBearer(auto_error=False)


def get_auth_service() -> AuthService:
    return AuthService()


def get_optional_access_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    access_token: str | None = Query(default=None),
) -> str | None:
    if access_token is not None and access_token.strip():
        return access_token.strip()
    if credentials is not None and credentials.scheme.lower() == "bearer":
        token = credentials.credentials.strip()
        if token:
            return token
    return None


def get_optional_current_user(
    token: str | None = Depends(get_optional_access_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> UserAccount | None:
    if token is None or not token.strip():
        return None
    try:
        return auth_service.get_authenticated_session(token=token).user
    except AuthenticationError:
        return None


def get_current_user(
    user: UserAccount | None = Depends(get_optional_current_user),
) -> UserAccount:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
        )
    return user
