from __future__ import annotations

from collections.abc import Sequence

from psycopg.types.json import Jsonb

from db.models import (
    AuthSession,
    GeneratedRender,
    GeneratedRenderId,
    SavedLayout,
    SavedLayoutId,
    SessionId,
    TenantId,
    UserAccount,
    UserAuthRecord,
    UserId,
)
from db.pg_utils import (
    RowMapping,
    to_json_dict,
    to_optional_bytes,
    to_optional_str,
    to_str,
)
from db.postgres import create_connection


class PostgresUserContentRepository:
    def __init__(self, connection_factory=None) -> None:
        self._connection_factory = connection_factory or create_connection

    def create_user(self, record: UserAuthRecord) -> None:
        query = """
            INSERT INTO user_accounts (
                id,
                email,
                display_name,
                tenant_id,
                password_salt,
                password_hash
            )
            VALUES (
                %(id)s,
                %(email)s,
                %(display_name)s,
                %(tenant_id)s,
                %(password_salt)s,
                %(password_hash)s
            )
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "id": record.user.id,
                        "email": record.user.email,
                        "display_name": record.user.display_name,
                        "tenant_id": record.user.tenant_id,
                        "password_salt": record.password_salt,
                        "password_hash": record.password_hash,
                    },
                )

    def get_user_auth_by_email(self, email: str) -> UserAuthRecord | None:
        query = "SELECT * FROM user_accounts WHERE lower(email) = lower(%(email)s)"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"email": email})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_user_auth(row)

    def get_user_by_id(self, user_id: UserId) -> UserAccount | None:
        query = "SELECT * FROM user_accounts WHERE id = %(user_id)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"user_id": user_id})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_user(row)

    def create_session(self, session: AuthSession) -> None:
        query = """
            INSERT INTO auth_sessions (
                id,
                user_id,
                token_hash,
                created_at,
                expires_at,
                last_seen_at,
                revoked_at
            )
            VALUES (
                %(id)s,
                %(user_id)s,
                %(token_hash)s,
                %(created_at)s,
                %(expires_at)s,
                %(last_seen_at)s,
                %(revoked_at)s
            )
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "id": session.id,
                        "user_id": session.user_id,
                        "token_hash": session.token_hash,
                        "created_at": session.created_at,
                        "expires_at": session.expires_at,
                        "last_seen_at": session.last_seen_at,
                        "revoked_at": session.revoked_at,
                    },
                )

    def get_session_by_token_hash(self, token_hash: str) -> AuthSession | None:
        query = "SELECT * FROM auth_sessions WHERE token_hash = %(token_hash)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"token_hash": token_hash})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_session(row)

    def revoke_session(self, session_id: SessionId) -> None:
        query = "UPDATE auth_sessions SET revoked_at = NOW() WHERE id = %(session_id)s"
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"session_id": session_id})

    def touch_session(self, session_id: SessionId) -> None:
        query = (
            "UPDATE auth_sessions SET last_seen_at = NOW() WHERE id = %(session_id)s"
        )
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"session_id": session_id})

    def create_saved_layout(self, layout: SavedLayout) -> None:
        query = """
            INSERT INTO saved_layouts (
                id,
                user_id,
                name,
                floorplan_json,
                design_json,
                styled_result_json,
                meta
            )
            VALUES (
                %(id)s,
                %(user_id)s,
                %(name)s,
                %(floorplan_json)s,
                %(design_json)s,
                %(styled_result_json)s,
                %(meta)s
            )
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "id": layout.id,
                        "user_id": layout.user_id,
                        "name": layout.name,
                        "floorplan_json": Jsonb(layout.floorplan_json),
                        "design_json": Jsonb(layout.design_json)
                        if layout.design_json is not None
                        else None,
                        "styled_result_json": Jsonb(layout.styled_result_json)
                        if layout.styled_result_json is not None
                        else None,
                        "meta": Jsonb(layout.meta),
                    },
                )

    def list_saved_layouts(self, user_id: UserId) -> Sequence[SavedLayout]:
        query = """
            SELECT *
            FROM saved_layouts
            WHERE user_id = %(user_id)s
            ORDER BY updated_at DESC, created_at DESC
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"user_id": user_id})
                rows = cur.fetchall()
        return [_row_to_saved_layout(row) for row in rows]

    def get_saved_layout(
        self, layout_id: SavedLayoutId, user_id: UserId
    ) -> SavedLayout | None:
        query = """
            SELECT *
            FROM saved_layouts
            WHERE id = %(layout_id)s AND user_id = %(user_id)s
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"layout_id": layout_id, "user_id": user_id})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_saved_layout(row)

    def create_generated_render(self, render: GeneratedRender) -> None:
        query = """
            INSERT INTO generated_renders (
                id,
                user_id,
                source,
                model_name,
                prompt,
                negative_prompt,
                storage_path,
                image_bytes,
                mime_type,
                meta
            )
            VALUES (
                %(id)s,
                %(user_id)s,
                %(source)s,
                %(model_name)s,
                %(prompt)s,
                %(negative_prompt)s,
                %(storage_path)s,
                %(image_bytes)s,
                %(mime_type)s,
                %(meta)s
            )
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "id": render.id,
                        "user_id": render.user_id,
                        "source": render.source,
                        "model_name": render.model_name,
                        "prompt": render.prompt,
                        "negative_prompt": render.negative_prompt,
                        "storage_path": render.storage_path,
                        "image_bytes": render.image_bytes,
                        "mime_type": render.mime_type,
                        "meta": Jsonb(render.meta),
                    },
                )

    def list_generated_renders(self, user_id: UserId) -> Sequence[GeneratedRender]:
        query = """
            SELECT *
            FROM generated_renders
            WHERE user_id = %(user_id)s
            ORDER BY created_at DESC
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"user_id": user_id})
                rows = cur.fetchall()
        return [_row_to_generated_render(row) for row in rows]

    def get_generated_render(
        self, render_id: GeneratedRenderId, user_id: UserId
    ) -> GeneratedRender | None:
        query = """
            SELECT *
            FROM generated_renders
            WHERE id = %(render_id)s AND user_id = %(user_id)s
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(query, {"render_id": render_id, "user_id": user_id})
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_generated_render(row)

    def update_generated_render_meta(
        self,
        render_id: GeneratedRenderId,
        user_id: UserId,
        meta: dict[str, object],
    ) -> GeneratedRender | None:
        query = """
            UPDATE generated_renders
            SET meta = %(meta)s
            WHERE id = %(render_id)s AND user_id = %(user_id)s
            RETURNING *
        """
        with self._connection_factory() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    query,
                    {
                        "render_id": render_id,
                        "user_id": user_id,
                        "meta": Jsonb(meta),
                    },
                )
                row = cur.fetchone()
        if row is None:
            return None
        return _row_to_generated_render(row)


def _row_to_user(row: RowMapping) -> UserAccount:
    return UserAccount(
        id=UserId(to_str(row.get("id"))),
        email=to_str(row.get("email")),
        display_name=to_optional_str(row.get("display_name")),
        tenant_id=TenantId(to_str(row.get("tenant_id"))),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_user_auth(row: RowMapping) -> UserAuthRecord:
    user = _row_to_user(row)
    return UserAuthRecord(
        user=user,
        password_salt=to_str(row.get("password_salt")),
        password_hash=to_str(row.get("password_hash")),
    )


def _row_to_session(row: RowMapping) -> AuthSession:
    return AuthSession(
        id=SessionId(to_str(row.get("id"))),
        user_id=UserId(to_str(row.get("user_id"))),
        token_hash=to_str(row.get("token_hash")),
        created_at=row.get("created_at"),
        expires_at=row.get("expires_at"),
        last_seen_at=row.get("last_seen_at"),
        revoked_at=row.get("revoked_at"),
    )


def _row_to_saved_layout(row: RowMapping) -> SavedLayout:
    return SavedLayout(
        id=SavedLayoutId(to_str(row.get("id"))),
        user_id=UserId(to_str(row.get("user_id"))),
        name=to_str(row.get("name")),
        floorplan_json=to_json_dict(row.get("floorplan_json")),
        design_json=to_json_dict(row.get("design_json"))
        if row.get("design_json") is not None
        else None,
        styled_result_json=to_json_dict(row.get("styled_result_json"))
        if row.get("styled_result_json") is not None
        else None,
        meta=to_json_dict(row.get("meta")),
        created_at=row.get("created_at"),
        updated_at=row.get("updated_at"),
    )


def _row_to_generated_render(row: RowMapping) -> GeneratedRender:
    source = to_str(row.get("source"))
    if source not in {
        "snapshot_render",
        "object_prompt_reference",
        "object_image_upload",
    }:
        raise ValueError(f"Unsupported render source: {source}")
    return GeneratedRender(
        id=GeneratedRenderId(to_str(row.get("id"))),
        user_id=UserId(to_str(row.get("user_id"))),
        source=source,
        model_name=to_str(row.get("model_name")),
        prompt=to_str(row.get("prompt")),
        negative_prompt=to_optional_str(row.get("negative_prompt")),
        storage_path=to_optional_str(row.get("storage_path")),
        image_bytes=to_optional_bytes(row.get("image_bytes")),
        mime_type=to_str(row.get("mime_type")),
        meta=to_json_dict(row.get("meta")),
        created_at=row.get("created_at"),
    )
