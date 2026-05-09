from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from db.models import (
    AuthSession,
    SessionId,
    TenantId,
    UserAccount,
    UserAuthRecord,
    UserId,
)
from db.pg_user_content import PostgresUserContentRepository
from db.runtime_init import ensure_user_content_schema

DEFAULT_SHARED_INVENTORY_TENANT = os.getenv(
    "TKNT_SHARED_INVENTORY_TENANT_ID", "demo_tenant"
)
DEFAULT_SESSION_TTL_DAYS = max(
    1,
    int(os.getenv("TKNT_AUTH_SESSION_TTL_DAYS", "30")),
)
_PBKDF2_ITERATIONS = max(
    100_000,
    int(os.getenv("TKNT_AUTH_PBKDF2_ITERATIONS", "240000")),
)


class AuthenticationError(ValueError):
    pass


@dataclass(frozen=True)
class AuthenticatedSession:
    user: UserAccount
    session: AuthSession
    token: str


def get_shared_inventory_tenant_id() -> str:
    return DEFAULT_SHARED_INVENTORY_TENANT


class AuthService:
    def __init__(
        self,
        repository: PostgresUserContentRepository | None = None,
    ) -> None:
        ensure_user_content_schema()
        self._repository = repository or PostgresUserContentRepository()

    def register_user(
        self,
        *,
        email: str,
        password: str,
        display_name: str | None = None,
    ) -> AuthenticatedSession:
        normalized_email = _normalize_email(email)
        normalized_display_name = _normalize_display_name(
            display_name, normalized_email
        )
        _validate_password(password)

        existing = self._repository.get_user_auth_by_email(normalized_email)
        if existing is not None:
            raise AuthenticationError("An account with this email already exists.")

        user = UserAccount(
            id=UserId(_build_user_id()),
            email=normalized_email,
            display_name=normalized_display_name,
            tenant_id=TenantId(_build_tenant_id(normalized_email)),
        )
        salt = _generate_secret_token(24)
        password_hash = _hash_password(password=password, salt=salt)
        self._repository.create_user(
            UserAuthRecord(
                user=user,
                password_salt=salt,
                password_hash=password_hash,
            )
        )
        return self._create_session(user)

    def login_user(self, *, email: str, password: str) -> AuthenticatedSession:
        normalized_email = _normalize_email(email)
        record = self._repository.get_user_auth_by_email(normalized_email)
        if record is None:
            raise AuthenticationError("Invalid email or password.")

        expected_hash = _hash_password(password=password, salt=record.password_salt)
        if not hmac.compare_digest(expected_hash, record.password_hash):
            raise AuthenticationError("Invalid email or password.")

        return self._create_session(record.user)

    def logout(self, token: str) -> None:
        resolved = self.get_authenticated_session(token=token)
        self._repository.revoke_session(resolved.session.id)

    def get_authenticated_session(self, *, token: str) -> AuthenticatedSession:
        normalized_token = token.strip()
        if not normalized_token:
            raise AuthenticationError("Missing authentication token.")

        token_hash = _hash_token(normalized_token)
        session = self._repository.get_session_by_token_hash(token_hash)
        if session is None:
            raise AuthenticationError("Session not found.")
        if session.revoked_at is not None:
            raise AuthenticationError("Session has been revoked.")

        now = datetime.now(timezone.utc)
        expires_at = session.expires_at
        if expires_at is None or expires_at <= now:
            raise AuthenticationError("Session has expired.")

        user = self._repository.get_user_by_id(session.user_id)
        if user is None:
            raise AuthenticationError("User account no longer exists.")

        self._repository.touch_session(session.id)
        refreshed_session = (
            self._repository.get_session_by_token_hash(token_hash) or session
        )
        return AuthenticatedSession(
            user=user,
            session=refreshed_session,
            token=normalized_token,
        )

    def _create_session(self, user: UserAccount) -> AuthenticatedSession:
        token = _generate_secret_token(48)
        now = datetime.now(timezone.utc)
        session = AuthSession(
            id=SessionId(_build_session_id()),
            user_id=user.id,
            token_hash=_hash_token(token),
            created_at=now,
            expires_at=now + timedelta(days=DEFAULT_SESSION_TTL_DAYS),
            last_seen_at=now,
            revoked_at=None,
        )
        self._repository.create_session(session)
        return AuthenticatedSession(user=user, session=session, token=token)


def _normalize_email(value: str) -> str:
    normalized = value.strip().lower()
    if not normalized or "@" not in normalized or "." not in normalized.split("@")[-1]:
        raise AuthenticationError("Please provide a valid email address.")
    return normalized


def _normalize_display_name(display_name: str | None, email: str) -> str:
    raw = (display_name or "").strip()
    if raw:
        return raw[:120]
    return email.split("@", 1)[0][:120]


def _validate_password(password: str) -> None:
    if len(password) < 8:
        raise AuthenticationError("Password must be at least 8 characters long.")


def _build_user_id() -> str:
    return f"user_{secrets.token_hex(8)}"


def _build_session_id() -> str:
    return f"sess_{secrets.token_hex(12)}"


def _build_tenant_id(email: str) -> str:
    local_part = email.split("@", 1)[0]
    slug = re.sub(r"[^a-z0-9]+", "-", local_part.lower()).strip("-")
    slug = slug[:32] or "user"
    return f"user_inventory_{slug}_{secrets.token_hex(4)}"


def _generate_secret_token(length: int) -> str:
    return secrets.token_urlsafe(length)


def _hash_password(*, password: str, salt: str) -> str:
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        _PBKDF2_ITERATIONS,
    )
    return base64.b64encode(derived).decode("ascii")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
