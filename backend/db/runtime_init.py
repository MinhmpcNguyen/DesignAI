from __future__ import annotations

import logging
from threading import Lock
from pathlib import Path

from db.postgres import create_connection
from db.schema import (
    get_runtime_schema_statements,
    get_runtime_user_content_schema_statements,
)

logger = logging.getLogger(__name__)
_runtime_schema_lock = Lock()
_user_content_schema_lock = Lock()
_runtime_schema_initialized = False
_user_content_schema_initialized = False
_generated_render_binary_migration_completed = False


def initialize_runtime_schema() -> None:
    _execute_schema_statements(
        get_runtime_schema_statements(),
        label="Runtime schema",
    )


def initialize_user_content_schema() -> None:
    _execute_schema_statements(
        get_runtime_user_content_schema_statements(),
        label="User content schema",
    )


def ensure_runtime_schema() -> None:
    global _runtime_schema_initialized
    if _runtime_schema_initialized:
        return
    with _runtime_schema_lock:
        if _runtime_schema_initialized:
            return
        initialize_runtime_schema()
        _assert_tables_exist(["assets", "asset_files", "design_knowledge"])
        _runtime_schema_initialized = True


def ensure_user_content_schema() -> None:
    global _generated_render_binary_migration_completed
    global _user_content_schema_initialized
    if _user_content_schema_initialized:
        return
    with _user_content_schema_lock:
        if _user_content_schema_initialized:
            return
        initialize_user_content_schema()
        _assert_tables_exist(
            [
                "user_accounts",
                "auth_sessions",
                "saved_layouts",
                "generated_renders",
            ]
        )
        if not _generated_render_binary_migration_completed:
            _migrate_generated_render_storage_to_db()
            _generated_render_binary_migration_completed = True
        _user_content_schema_initialized = True


def _execute_schema_statements(statements: list[str], *, label: str) -> None:
    failures: list[str] = []
    with create_connection() as conn:
        with conn.cursor() as cur:
            for index, statement in enumerate(statements, start=1):
                try:
                    cur.execute(statement)
                    conn.commit()
                except Exception as exc:
                    conn.rollback()
                    failures.append(
                        f"{label} statement {index} failed: {exc} | sql={_statement_preview(statement)}"
                    )
    if failures:
        for failure in failures:
            logger.warning("%s", failure)
        logger.warning(
            "%s initialization completed with %d failed statements.",
            label,
            len(failures),
        )
        return
    logger.info("%s initialization completed with %d statements.", label, len(statements))


def _assert_tables_exist(table_names: list[str]) -> None:
    query = """
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_name = ANY(%(table_names)s)
    """
    with create_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(query, {"table_names": table_names})
            rows = cur.fetchall()
    existing = {str(row["table_name"]) for row in rows}
    missing = [name for name in table_names if name not in existing]
    if missing:
        missing_tables = ", ".join(sorted(missing))
        raise RuntimeError(f"Missing required runtime tables: {missing_tables}")


def _statement_preview(statement: str) -> str:
    condensed = " ".join(statement.split())
    if len(condensed) <= 140:
        return condensed
    return f"{condensed[:137]}..."


def _migrate_generated_render_storage_to_db() -> None:
    select_query = """
        SELECT id, storage_path
        FROM generated_renders
        WHERE image_bytes IS NULL
          AND storage_path IS NOT NULL
          AND btrim(storage_path) <> ''
    """
    update_query = """
        UPDATE generated_renders
        SET image_bytes = %(image_bytes)s
        WHERE id = %(render_id)s
    """
    migrated_count = 0
    skipped_paths: list[str] = []
    with create_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(select_query)
            rows = cur.fetchall()
            for row in rows:
                render_id = str(row.get("id") or "").strip()
                storage_path = str(row.get("storage_path") or "").strip()
                if not render_id or not storage_path:
                    continue
                path = Path(storage_path)
                if not path.exists() or not path.is_file():
                    skipped_paths.append(storage_path)
                    continue
                cur.execute(
                    update_query,
                    {
                        "render_id": render_id,
                        "image_bytes": path.read_bytes(),
                    },
                )
                migrated_count += 1
        conn.commit()
    if migrated_count:
        logger.info(
            "Migrated %d generated render payloads from local storage into Postgres.",
            migrated_count,
        )
    if skipped_paths:
        logger.warning(
            "Skipped %d generated render payload migrations because the local file was missing.",
            len(skipped_paths),
        )
