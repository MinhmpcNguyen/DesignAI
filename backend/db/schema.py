from __future__ import annotations

import os

from config.settings import settings

VECTOR_DIMENSIONS = settings.VECTOR_DIMS
DEFAULT_SHARED_INVENTORY_TENANT = os.getenv(
    "TKNT_SHARED_INVENTORY_TENANT_ID", "demo_tenant"
)


def get_schema_statements() -> list[str]:
    return [
        "CREATE EXTENSION IF NOT EXISTS vector;",
        """
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            style_tags TEXT[] NOT NULL DEFAULT '{}',
            material TEXT,
            brand TEXT,
            length_mm DOUBLE PRECISION,
            width_mm DOUBLE PRECISION,
            height_mm DOUBLE PRECISION,
            price_amount DOUBLE PRECISION,
            price_currency TEXT,
            attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS length_mm DOUBLE PRECISION;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS width_mm DOUBLE PRECISION;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS height_mm DOUBLE PRECISION;",
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'assets' AND column_name = 'length_cm'
            ) THEN
                UPDATE assets
                SET length_mm = length_cm * 10
                WHERE length_mm IS NULL AND length_cm IS NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'assets' AND column_name = 'width_cm'
            ) THEN
                UPDATE assets
                SET width_mm = width_cm * 10
                WHERE width_mm IS NULL AND width_cm IS NOT NULL;
            END IF;
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'assets' AND column_name = 'height_cm'
            ) THEN
                UPDATE assets
                SET height_mm = height_cm * 10
                WHERE height_mm IS NULL AND height_cm IS NOT NULL;
            END IF;
        END $$;
        """,
        "ALTER TABLE assets DROP COLUMN IF EXISTS length_cm;",
        "ALTER TABLE assets DROP COLUMN IF EXISTS width_cm;",
        "ALTER TABLE assets DROP COLUMN IF EXISTS height_cm;",
        """
        CREATE TABLE IF NOT EXISTS asset_files (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            file_kind TEXT NOT NULL,
            provider TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            mime TEXT,
            width_px INTEGER,
            height_px INTEGER,
            bytes_size BIGINT,
            role TEXT,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS asset_embeddings (
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            model TEXT NOT NULL,
            meta JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            vector VECTOR({VECTOR_DIMENSIONS}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (asset_id, model)
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS design_knowledge (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT[] NOT NULL DEFAULT '{}',
            source TEXT,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        f"""
        CREATE TABLE IF NOT EXISTS design_knowledge_embeddings (
            knowledge_id TEXT NOT NULL REFERENCES design_knowledge(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            model TEXT NOT NULL,
            meta JSONB NOT NULL DEFAULT '{{}}'::jsonb,
            vector VECTOR({VECTOR_DIMENSIONS}) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (knowledge_id, model)
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_assets_tenant ON assets (tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_assets_style_tags ON assets USING GIN (style_tags);",
        "CREATE INDEX IF NOT EXISTS idx_assets_attributes ON assets USING GIN (attributes);",
        "CREATE INDEX IF NOT EXISTS idx_asset_files_asset_id ON asset_files (asset_id);",
        "CREATE INDEX IF NOT EXISTS idx_embeddings_vector ON asset_embeddings USING HNSW (vector vector_l2_ops);",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON design_knowledge (tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_tags ON design_knowledge USING GIN (tags);",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_category ON design_knowledge (category);",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_embeddings_vector ON design_knowledge_embeddings USING HNSW (vector vector_l2_ops);",
    ]


def get_runtime_asset_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS assets (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL,
            type TEXT NOT NULL,
            name TEXT NOT NULL,
            style_tags TEXT[] NOT NULL DEFAULT '{}',
            material TEXT,
            brand TEXT,
            length_mm DOUBLE PRECISION,
            width_mm DOUBLE PRECISION,
            height_mm DOUBLE PRECISION,
            price_amount DOUBLE PRECISION,
            price_currency TEXT,
            attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS tenant_id TEXT;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS type TEXT;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS name TEXT;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS style_tags TEXT[] NOT NULL DEFAULT '{}';",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS material TEXT;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS brand TEXT;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS length_mm DOUBLE PRECISION;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS width_mm DOUBLE PRECISION;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS height_mm DOUBLE PRECISION;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS price_amount DOUBLE PRECISION;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS price_currency TEXT;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS attributes JSONB NOT NULL DEFAULT '{}'::jsonb;",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
        "ALTER TABLE assets ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
        f"""
        UPDATE assets
        SET tenant_id = '{DEFAULT_SHARED_INVENTORY_TENANT}'
        WHERE tenant_id IS NULL OR btrim(tenant_id) = '';
        """,
        """
        CREATE TABLE IF NOT EXISTS asset_files (
            id TEXT PRIMARY KEY,
            asset_id TEXT NOT NULL REFERENCES assets(id) ON DELETE CASCADE,
            file_kind TEXT NOT NULL,
            provider TEXT NOT NULL,
            storage_key TEXT NOT NULL,
            mime TEXT,
            width_px INTEGER,
            height_px INTEGER,
            bytes_size BIGINT,
            role TEXT,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS file_kind TEXT;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS provider TEXT;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS storage_key TEXT;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS mime TEXT;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS width_px INTEGER;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS height_px INTEGER;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS bytes_size BIGINT;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS role TEXT;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS meta JSONB NOT NULL DEFAULT '{}'::jsonb;",
        "ALTER TABLE asset_files ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ NOT NULL DEFAULT NOW();",
        "CREATE INDEX IF NOT EXISTS idx_assets_tenant ON assets (tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_asset_files_asset_id ON asset_files (asset_id);",
    ]


def get_runtime_knowledge_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS design_knowledge (
            id TEXT PRIMARY KEY,
            tenant_id TEXT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            category TEXT,
            tags TEXT[] NOT NULL DEFAULT '{}',
            source TEXT,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        "CREATE INDEX IF NOT EXISTS idx_knowledge_tenant ON design_knowledge (tenant_id);",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_tags ON design_knowledge USING GIN (tags);",
        "CREATE INDEX IF NOT EXISTS idx_knowledge_category ON design_knowledge (category);",
    ]


def get_runtime_user_content_schema_statements() -> list[str]:
    return [
        """
        CREATE TABLE IF NOT EXISTS user_accounts (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            display_name TEXT,
            tenant_id TEXT NOT NULL UNIQUE,
            password_salt TEXT NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS auth_sessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
            token_hash TEXT NOT NULL UNIQUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            revoked_at TIMESTAMPTZ
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS saved_layouts (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            floorplan_json JSONB NOT NULL,
            design_json JSONB,
            styled_result_json JSONB,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        CREATE TABLE IF NOT EXISTS generated_renders (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES user_accounts(id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            model_name TEXT NOT NULL,
            prompt TEXT NOT NULL,
            negative_prompt TEXT,
            storage_path TEXT,
            image_bytes BYTEA,
            mime_type TEXT NOT NULL,
            meta JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """,
        """
        ALTER TABLE generated_renders
        ADD COLUMN IF NOT EXISTS image_bytes BYTEA;
        """,
        """
        ALTER TABLE generated_renders
        ALTER COLUMN storage_path DROP NOT NULL;
        """,
        "CREATE INDEX IF NOT EXISTS idx_user_accounts_email ON user_accounts (email);",
        "CREATE INDEX IF NOT EXISTS idx_auth_sessions_user_id ON auth_sessions (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_saved_layouts_user_id ON saved_layouts (user_id);",
        "CREATE INDEX IF NOT EXISTS idx_generated_renders_user_id ON generated_renders (user_id);",
    ]


def get_runtime_schema_statements() -> list[str]:
    return [
        *get_runtime_asset_schema_statements(),
        *get_runtime_knowledge_schema_statements(),
        *get_runtime_user_content_schema_statements(),
    ]


def get_schema_notes() -> list[str]:
    return [
        "Change VECTOR_DIMENSIONS to match your embedding model.",
        "Use TEXT ids to keep the schema tool-agnostic; the app should provide ids.",
        "If you prefer UUIDs, switch id fields to UUID and add a UUID extension.",
        "design_knowledge.tenant_id is optional to support shared/global knowledge.",
    ]
