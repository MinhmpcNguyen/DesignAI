from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api.deps import get_auth_service, get_current_user, get_optional_access_token
from db.models import UserAccount
from services.auth_service import AuthService, AuthenticationError, AuthenticatedSession

router = APIRouter(prefix="/auth", tags=["auth"])


class AuthUserResponse(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    tenant_id: str


class AuthSessionResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: AuthUserResponse


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=8)
    display_name: str | None = Field(default=None, max_length=120)


class LoginRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=1)


@router.post("/register", response_model=AuthSessionResponse)
def register(
    request: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    try:
        session = auth_service.register_user(
            email=str(request.email),
            password=request.password,
            display_name=request.display_name,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_session(session)


@router.post("/login", response_model=AuthSessionResponse)
def login(
    request: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthSessionResponse:
    try:
        session = auth_service.login_user(
            email=str(request.email),
            password=request.password,
        )
    except AuthenticationError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc
    return _serialize_session(session)


@router.get("/me", response_model=AuthUserResponse)
def me(user: UserAccount = Depends(get_current_user)) -> AuthUserResponse:
    return _serialize_user(user)


@router.post("/logout")
def logout(
    user: UserAccount = Depends(get_current_user),
    token: str | None = Depends(get_optional_access_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict[str, bool]:
    del user
    if token is None:
        raise HTTPException(status_code=400, detail="Missing access token.")
    auth_service.logout(token)
    return {"ok": True}


def _serialize_session(session: AuthenticatedSession) -> AuthSessionResponse:
    return AuthSessionResponse(
        access_token=session.token,
        user=_serialize_user(session.user),
    )


def _serialize_user(user: UserAccount) -> AuthUserResponse:
    return AuthUserResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        tenant_id=str(user.tenant_id),
    )
