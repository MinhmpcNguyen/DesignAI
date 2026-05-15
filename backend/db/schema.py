from __future__ import annotations

import os

DEFAULT_SHARED_INVENTORY_TENANT = os.getenv(
    "TKNT_SHARED_INVENTORY_TENANT_ID", "demo_tenant"
)


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
        "CREATE INDEX IF NOT EXISTS idx_assets_tenant ON assets (tenant_id);",
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


def get_runtime_schema_statements() -> list[str]:
    return [
        *get_runtime_asset_schema_statements(),
        *get_runtime_knowledge_schema_statements(),
    ]
